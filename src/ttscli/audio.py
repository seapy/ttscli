import re
import subprocess
from pathlib import Path

from ttscli.models import Segment

# Approximate speech rate in chars/second per language
CHARS_PER_SEC: dict[str, float] = {
    "en": 13.0,
    "ko": 7.0,
    "ja": 8.0,
    "zh": 7.0,
}
DEFAULT_CHARS_PER_SEC = 12.0

# Max text length per API call
MAX_CHUNK_SIZES: dict[str, int] = {
    "openai": 4096,
    "gemini": 30000,
    "elevenlabs": 2500,
    "minimax": 10000,
}

_SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?。！？])\s+')


def estimate_chars_per_sec(language: str) -> float:
    lang = language.lower()[:2]
    return CHARS_PER_SEC.get(lang, DEFAULT_CHARS_PER_SEC)


def calculate_speed(
    text: str,
    target_duration: float,
    chars_per_sec: float,
    speed_min: float,
    speed_max: float,
) -> tuple[float, bool]:
    """Return (clamped_speed, is_within_range)."""
    if target_duration <= 0:
        return 1.0, True
    estimated_duration = len(text) / chars_per_sec
    required_speed = estimated_duration / target_duration
    clamped = max(speed_min, min(speed_max, required_speed))
    return clamped, (speed_min <= required_speed <= speed_max)


def chunk_text(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    sentences = _SENTENCE_SPLIT_RE.split(text)
    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        if len(current) + (1 if current else 0) + len(sentence) <= max_chars:
            current = (current + " " + sentence).lstrip() if current else sentence
        else:
            if current:
                chunks.append(current)
            if len(sentence) <= max_chars:
                current = sentence
            else:
                # Hard split at max_chars
                while len(sentence) > max_chars:
                    chunks.append(sentence[:max_chars])
                    sentence = sentence[max_chars:]
                current = sentence

    if current:
        chunks.append(current)

    return chunks


def concat_audio(audio_paths: list[Path], output_path: Path) -> None:
    from pydub import AudioSegment

    combined = AudioSegment.empty()
    for path in audio_paths:
        if path.exists():
            combined += AudioSegment.from_file(str(path))
    combined.export(str(output_path), format="mp3")


def get_audio_duration(path: Path) -> float:
    try:
        from mutagen.mp3 import MP3
        return MP3(str(path)).info.length
    except Exception:
        try:
            from pydub import AudioSegment
            return len(AudioSegment.from_file(str(path))) / 1000.0
        except Exception:
            return 0.0


def apply_time_stretch(input_path: Path, target_duration: float, output_path: Path) -> bool:
    """Time-stretch audio to target_duration using ffmpeg atempo filter."""
    current = get_audio_duration(input_path)
    if current <= 0 or target_duration <= 0:
        return False

    ratio = current / target_duration
    filter_chain = _build_atempo_filter(ratio)

    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", str(input_path), "-filter:a", filter_chain, str(output_path)],
            capture_output=True,
            timeout=60,
        )
        return result.returncode == 0 and output_path.exists()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _build_atempo_filter(ratio: float) -> str:
    if 0.5 <= ratio <= 2.0:
        return f"atempo={ratio:.4f}"
    elif ratio > 2.0:
        filters: list[str] = []
        r = ratio
        while r > 2.0:
            filters.append("atempo=2.0")
            r /= 2.0
        filters.append(f"atempo={r:.4f}")
        return ",".join(filters)
    else:
        filters = []
        r = ratio
        while r < 0.5:
            filters.append("atempo=0.5")
            r *= 2.0
        filters.append(f"atempo={r:.4f}")
        return ",".join(filters)


def assemble_timed(
    segments: list[Segment],
    audio_files: list[Path],
    total_duration: float,
    output_path: Path,
    fmt: str,
) -> None:
    from pydub import AudioSegment

    output = AudioSegment.silent(duration=int(total_duration * 1000))
    for segment, audio_path in zip(segments, audio_files):
        if not audio_path.exists():
            continue
        try:
            audio = AudioSegment.from_file(str(audio_path))
            position_ms = int(segment.start * 1000)
            output = output.overlay(audio, position=position_ms)
        except Exception:
            pass
    output.export(str(output_path), format=fmt)


def assemble_natural(
    audio_files: list[Path],
    output_path: Path,
    fmt: str,
    gap_ms: int = 300,
) -> float:
    from pydub import AudioSegment

    output: AudioSegment = AudioSegment.empty()
    gap = AudioSegment.silent(duration=gap_ms)

    for i, audio_path in enumerate(audio_files):
        if not audio_path.exists():
            continue
        try:
            audio = AudioSegment.from_file(str(audio_path))
            if i > 0:
                output += gap
            output += audio
        except Exception:
            pass

    output.export(str(output_path), format=fmt)
    return len(output) / 1000.0
