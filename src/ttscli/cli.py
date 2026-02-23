import shutil
import tempfile
from pathlib import Path

import click
from rich.console import Console

from ttscli import audio as audio_module
from ttscli.audio import (
    MAX_CHUNK_SIZES,
    apply_time_stretch,
    assemble_natural,
    assemble_timed,
    calculate_speed,
    chunk_text,
    concat_audio,
    estimate_chars_per_sec,
    get_audio_duration,
)
from ttscli.config import load_config, resolve_api_key, resolve_extra
from ttscli.parser import parse
from ttscli.progress import StepProgress, make_progress
from ttscli.providers import get_provider

err_console = Console(stderr=True)

# Default voices to use when gender is known but no explicit voice is configured.
# Users can override per-provider via `male_voice` / `female_voice` in ~/.ttscli.toml.
_GENDER_VOICES: dict[str, dict[str, str]] = {
    "elevenlabs": {
        "male": "ErXwobaYiN019PkySvjV",   # Antoni
        "female": "21m00Tcm4TlvDq8ikWAM",  # Rachel
    },
    "gemini": {
        "male": "Charon",
        "female": "Kore",
    },
    "minimax": {
        "male": "male-qn-qingse",
        "female": "female-shaonv",
    },
}


def _resolve_gender_voice(
    provider_name: str, gender: str | None, provider_cfg: dict
) -> str | None:
    """Return a voice ID/name matching *gender*, respecting config overrides."""
    if not gender:
        return None
    config_key = f"{gender}_voice"
    if config_key in provider_cfg:
        return provider_cfg[config_key]
    return _GENDER_VOICES.get(provider_name, {}).get(gender)


def _fmt_time(seconds: float) -> str:
    total = int(seconds)
    m, s = divmod(total, 60)
    return f"{m:02d}:{s:02d}"


def _fmt_duration(seconds: float) -> str:
    total = int(seconds)
    m, s = divmod(total, 60)
    if m >= 60:
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _parse_speaker_voices(entries: tuple[str, ...]) -> dict[str, str]:
    result = {}
    for entry in entries:
        if "=" in entry:
            speaker, voice = entry.split("=", 1)
            result[speaker.strip()] = voice.strip()
    return result


@click.group()
def main():
    """TTS CLI: Convert sttcli transcripts to audio."""
    pass


@main.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.option("-p", "--provider", "provider_name",
              type=click.Choice(["gemini", "elevenlabs", "minimax"]),
              default="elevenlabs", show_default=True,
              help="TTS provider to use.")
@click.option("-o", "--output", type=click.Path(path_type=Path), default=None,
              help="Output file path (default: <input>_tts.mp3).")
@click.option("--mode", type=click.Choice(["timed", "natural"]),
              default="timed", show_default=True,
              help="timed: fit speech in segment time windows; natural: no timing constraints.")
@click.option("-m", "--model", default=None, help="Provider model name.")
@click.option("--voice", default=None, help="Default voice ID/name for all segments.")
@click.option("--speaker-voice", "speaker_voices", multiple=True,
              metavar="SPEAKER=VOICE",
              help="Map speaker label to voice (e.g. speaker_0=nova). Repeatable.")
@click.option("--speaker", "speakers", multiple=True,
              help="Only convert specified speaker(s). Repeatable.")
@click.option("--format", "fmt", type=click.Choice(["mp3", "wav"]),
              default="mp3", show_default=True,
              help="Output audio format.")
@click.option("--speed-range", default="0.75,1.4", show_default=True,
              help="Allowed speed range min,max for timed mode.")
@click.option("--api-key", default=None, help="API key (overrides env and config).")
@click.option("--config", "config_file", type=click.Path(path_type=Path), default=None,
              help="Config file path (default: ~/.ttscli.toml).")
@click.option("--voice-id", default=None,
              help="Voice ID (alias for --voice, useful for ElevenLabs).")
@click.option("--stability", type=float, default=None,
              help="ElevenLabs voice stability (0.0–1.0).")
@click.option("--minimax-group-id", default=None,
              help="MiniMax group ID.")
def convert(
    input_file: Path,
    provider_name: str,
    output: Path | None,
    mode: str,
    model: str | None,
    voice: str | None,
    speaker_voices: tuple[str, ...],
    speakers: tuple[str, ...],
    fmt: str,
    speed_range: str,
    api_key: str | None,
    config_file: Path | None,
    voice_id: str | None,
    stability: float | None,
    minimax_group_id: str | None,
):
    """Convert a sttcli markdown transcript to audio."""

    # Parse speed range
    try:
        speed_min, speed_max = map(float, speed_range.split(","))
    except ValueError:
        raise click.UsageError("--speed-range must be two floats: min,max (e.g. 0.75,1.4)")

    # Resolve output path
    if output is None:
        output = input_file.with_name(input_file.stem + "_tts." + fmt)

    # Resolve API key and extras
    resolved_key = resolve_api_key(provider_name, api_key, config_file)
    resolved_group_id = resolve_extra("minimax", "group_id", minimax_group_id, config_file)

    # Load config defaults
    cfg = load_config(config_file)
    provider_cfg = cfg.get(provider_name, {})

    # Effective default voice: --voice-id > --voice > config default
    effective_voice: str | None = voice_id or voice
    if not effective_voice:
        effective_voice = provider_cfg.get("default_voice") or provider_cfg.get("default_voice_id")

    # Merge speaker→voice maps: config < CLI
    config_speaker_map: dict[str, str] = cfg.get("speakers", {})
    cli_speaker_map = _parse_speaker_voices(speaker_voices)
    full_speaker_map: dict[str, str] = {**config_speaker_map, **cli_speaker_map}

    # Build provider kwargs
    provider_kwargs: dict = {}
    if resolved_group_id:
        provider_kwargs["group_id"] = resolved_group_id
    if stability is not None:
        provider_kwargs["stability"] = stability

    ProviderClass = get_provider(provider_name)
    provider = ProviderClass(model=model, api_key=resolved_key, **provider_kwargs)

    # Parse transcript
    transcript = parse(input_file)

    # Filter segments by speaker
    segs_to_process = list(transcript.segments)
    if speakers:
        segs_to_process = [s for s in segs_to_process if s.speaker in speakers]
    if not segs_to_process:
        raise click.UsageError("No segments to process. Check --speaker filter.")

    # Determine language for speed estimation
    language = transcript.meta.language or "en"
    chars_per_sec = estimate_chars_per_sec(language)

    # Determine total duration for timed assembly
    total_duration = transcript.meta.duration
    if total_duration <= 0:
        total_duration = transcript.segments[-1].end if transcript.segments else 0.0

    max_chars = MAX_CHUNK_SIZES.get(provider_name, 4096)

    err_console.print(
        f"\n[bold]ttscli[/bold] [dim]▶[/dim] {input_file.name} → {output.name}  "
        f"[dim]({len(segs_to_process)} segments, {provider_name}, {mode} mode)[/dim]"
    )

    audio_pairs: list[tuple] = []  # (segment, Path)

    with tempfile.TemporaryDirectory() as _tmpdir:
        tmpdir = Path(_tmpdir)

        with make_progress() as progress:
            main_task = progress.add_task(
                f"Converting...", total=len(segs_to_process)
            )

            for i, segment in enumerate(segs_to_process):
                # Resolve voice for this segment:
                # 1. explicit speaker→voice map (CLI or config)
                # 2. global --voice / config default_voice
                # 3. gender-based default (from transcript metadata)
                # 4. first available voice from provider
                seg_voice = (
                    full_speaker_map.get(segment.speaker or "")
                    or effective_voice
                    or _resolve_gender_voice(provider_name, segment.gender, provider_cfg)
                )
                if not seg_voice:
                    available = provider.list_voices()
                    seg_voice = available[0] if available else "default"

                # Calculate speed for timed mode
                speed = 1.0
                if mode == "timed" and segment.duration > 0:
                    speed, in_range = calculate_speed(
                        segment.text, segment.duration, chars_per_sec, speed_min, speed_max
                    )
                    if not in_range:
                        req = len(segment.text) / chars_per_sec / segment.duration
                        if req > speed_max:
                            progress.console.print(
                                f"[yellow]⚠  [{_fmt_time(segment.start)}] text too long "
                                f"({req:.2f}× > {speed_max}×), clamping to {speed_max}×[/yellow]"
                            )
                        else:
                            progress.console.print(
                                f"[yellow]⚠  [{_fmt_time(segment.start)}] text too short "
                                f"({req:.2f}× < {speed_min}×), clamping to {speed_min}×[/yellow]"
                            )

                seg_path = tmpdir / f"seg_{i:04d}.mp3"

                seg_step = StepProgress(
                    progress,
                    f"[{_fmt_time(segment.start)} → {_fmt_time(segment.end)}]"
                    + (f" {segment.speaker}" if segment.speaker else ""),
                    total=100,
                )

                # Split text if it exceeds API limit
                chunks = chunk_text(segment.text, max_chars)

                try:
                    if len(chunks) == 1:
                        actual_duration = provider.synthesize(
                            segment.text, seg_voice, speed, seg_path, seg_step
                        )
                    else:
                        chunk_paths: list[Path] = []
                        for j, chunk in enumerate(chunks):
                            chunk_path = tmpdir / f"seg_{i:04d}_c{j:02d}.mp3"
                            provider.synthesize(chunk, seg_voice, speed, chunk_path, seg_step)
                            chunk_paths.append(chunk_path)
                        concat_audio(chunk_paths, seg_path)
                        actual_duration = get_audio_duration(seg_path)
                except Exception as e:
                    seg_step.finish()
                    progress.console.print(
                        f"[yellow]⚠  [{_fmt_time(segment.start)}] skipped: {e}[/yellow]"
                    )
                    progress.advance(main_task, 1)
                    continue

                # Timed mode: time-stretch if provider doesn't support speed param
                final_path = seg_path
                if mode == "timed" and seg_path.exists() and segment.duration > 0:
                    tolerance = 0.5
                    if not provider.supports_speed_param and abs(actual_duration - segment.duration) > tolerance:
                        stretched = tmpdir / f"seg_{i:04d}_stretched.mp3"
                        if apply_time_stretch(seg_path, segment.duration, stretched):
                            final_path = stretched

                # Copy to a stable path so tmpdir cleanup doesn't matter during assembly
                stable_path = tmpdir / f"final_{i:04d}.mp3"
                if final_path.exists():
                    shutil.copy2(final_path, stable_path)
                    audio_pairs.append((segment, stable_path))
                else:
                    progress.console.print(
                        f"[red]✗ [{_fmt_time(segment.start)}] failed, skipping[/red]"
                    )

                progress.advance(main_task, 1)

            # Assembly
            asm_step = StepProgress(progress, "Assembling final audio...", total=100)
            segs_only = [s for s, _ in audio_pairs]
            paths_only = [p for _, p in audio_pairs]

            if mode == "timed":
                assemble_timed(segs_only, paths_only, total_duration, output, fmt)
            else:
                assemble_natural(paths_only, output, fmt)

            asm_step.finish("Assembled")

    duration = get_audio_duration(output)
    err_console.print(f"[green]✓[/green] Output: {output} ({_fmt_duration(duration)})")


@main.command()
@click.option("-p", "--provider", "provider_name",
              type=click.Choice(["gemini", "elevenlabs", "minimax"]),
              default="elevenlabs", show_default=True,
              help="TTS provider to list voices for.")
@click.option("--api-key", default=None, help="API key.")
@click.option("--config", "config_file", type=click.Path(path_type=Path), default=None,
              help="Config file path (default: ~/.ttscli.toml).")
def voices(provider_name: str, api_key: str | None, config_file: Path | None):
    """List available voices for a TTS provider."""
    resolved_key = resolve_api_key(provider_name, api_key, config_file)
    ProviderClass = get_provider(provider_name)
    provider = ProviderClass(api_key=resolved_key)

    voice_list = provider.list_voices()
    if not voice_list:
        err_console.print(f"[yellow]No voices returned for {provider_name}.[/yellow]")
        return

    err_console.print(f"\n[bold]{provider_name}[/bold] voices ({len(voice_list)}):\n")
    for v in voice_list:
        click.echo(v)


if __name__ == "__main__":
    main()
