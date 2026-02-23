# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup & Commands

```bash
# Create venv and install
uv venv && uv pip install -e .

# Install from GitHub (distribution)
uv tool install git+https://github.com/seapy/ttscli.git

# Run
.venv/bin/ttscli convert transcript.md --provider elevenlabs --config ~/.ttscli.toml
.venv/bin/ttscli voices --provider elevenlabs

# Verify parser
.venv/bin/python -c "from ttscli.parser import parse; t = parse('transcript.md'); print(len(t.segments))"
```

System dependency: `ffmpeg` (required by pydub for audio assembly and time-stretching).

## Architecture

ttscli is a companion tool to [sttcli](https://github.com/seapy/sttcli). It reads sttcli's markdown transcript format and synthesizes audio via TTS providers.

### Data flow

```
transcript.md → parser.py → ParsedTranscript
                                 ↓
                          cli.py (convert)
                         /       |        \
               speed calc    provider.synthesize()   chunk_text()
               (audio.py)    → seg_N.mp3             (audio.py)
                         \       |        /
                          assemble_timed()  or  assemble_natural()
                                 ↓
                            output.mp3
```

### Key modules

**`parser.py`** — Parses sttcli markdown into `ParsedTranscript`. The regex `SEGMENT_RE` matches `**[MM:SS → MM:SS]** **speaker** text` lines. Both `MM:SS` and `HH:MM:SS` are supported.

**`audio.py`** — Two assembly strategies:
- `assemble_timed`: creates a silence buffer of `total_duration`, overlays each segment's audio at `segment.start` position (pydub overlay). Gaps between segments become natural silence.
- `assemble_natural`: concatenates audio files sequentially with a 300ms gap.
- `apply_time_stretch`: ffmpeg `atempo` filter, chained for ratios outside 0.5–2.0.
- `calculate_speed`: estimates natural speech duration from `len(text) / chars_per_sec`, returns the ratio needed to fit the segment window.

**`providers/`** — ABC `BaseTTSProvider` with `synthesize(text, voice, speed, output_path, step) -> float` (returns actual audio duration). Key property: `supports_speed_param` — if `False`, speed adjustment is done via ffmpeg post-processing in `cli.py` instead of API parameter.

**`cli.py`** — The `convert` command handles: speaker→voice resolution (CLI `--speaker-voice` > config `[speakers]` > `--voice` > config `default_voice`), per-segment speed calculation, chunk splitting for long texts, time-stretch fallback, and final assembly. Failed segments (e.g. Gemini rejecting very short texts) are warned and skipped rather than aborting.

### Provider notes

| Provider | `supports_speed_param` | Known limitation |
|---|---|---|
| `elevenlabs` | `False` | — |
| `gemini` | `False` | Rejects very short inputs ("Yeah.", "Um-") with `FinishReason.OTHER`; returns PCM audio (`audio/L16;rate=24000`) which is converted to MP3 via pydub |
| `minimax` | `True` | Requires `group_id` in addition to API key; audio returned as hex-encoded string |

### Config file (`~/.ttscli.toml`)

```toml
[elevenlabs]
api_key = "..."
default_voice_id = "..."

[gemini]
api_key = "..."
default_voice = "Kore"

[minimax]
api_key = "..."
group_id = "..."

[speakers]
speaker_0 = "<voice-id>"
speaker_1 = "<voice-id>"
```

Priority order for all settings: CLI flag > environment variable > `~/.ttscli.toml`.
