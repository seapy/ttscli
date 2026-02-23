import re
from pathlib import Path

from ttscli.models import ParsedTranscript, Segment, TranscriptMeta

SEGMENT_RE = re.compile(
    r'\*\*\[(\d{1,2}:\d{2}(?::\d{2})?) → (\d{1,2}:\d{2}(?::\d{2})?)\]\*\*'
    r'(?:\s+\*\*(\w+)\*\*)?\s+(.*)'
)

# Matches sttcli gender rows:
#   | Gender   | male |          → global gender (no diarization)
#   | speaker_0_gender | female | → per-speaker gender
_GENDER_RE = re.compile(r'^\|\s*([\w]+_gender|Gender)\s*\|\s*(\w+)\s*\|')


def _parse_time(ts: str) -> float:
    parts = ts.strip().split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    elif len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    return float(ts)


def parse(path: Path | str) -> ParsedTranscript:
    path = Path(path).expanduser()
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    source_file = ""
    provider = ""
    model = ""
    language = ""
    duration = 0.0
    global_gender: str | None = None
    speaker_genders: dict[str, str] = {}

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# Transcript:"):
            source_file = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("| Provider"):
            parts = stripped.split("|")
            if len(parts) >= 3:
                provider = parts[2].strip()
        elif stripped.startswith("| Model"):
            parts = stripped.split("|")
            if len(parts) >= 3:
                model = parts[2].strip()
        elif stripped.startswith("| Language"):
            parts = stripped.split("|")
            if len(parts) >= 3:
                language = parts[2].strip()
        elif stripped.startswith("| Duration"):
            parts = stripped.split("|")
            if len(parts) >= 3:
                duration = _parse_time(parts[2].strip())
        else:
            m = _GENDER_RE.match(stripped)
            if m:
                key, value = m.group(1), m.group(2).lower()
                if key.lower() == "gender":
                    global_gender = value
                elif key.endswith("_gender"):
                    speaker = key[: -len("_gender")]
                    speaker_genders[speaker] = value

    segments: list[Segment] = []
    for line in lines:
        m = SEGMENT_RE.match(line.strip())
        if m:
            start = _parse_time(m.group(1))
            end = _parse_time(m.group(2))
            speaker = m.group(3) or None
            seg_text = m.group(4).strip()
            if seg_text:
                # Resolve gender for this segment
                if speaker and speaker in speaker_genders:
                    seg_gender = speaker_genders[speaker]
                else:
                    seg_gender = global_gender
                segments.append(
                    Segment(
                        start=start,
                        end=end,
                        speaker=speaker,
                        text=seg_text,
                        gender=seg_gender,
                    )
                )

    meta = TranscriptMeta(
        provider=provider,
        model=model,
        language=language,
        duration=duration,
        source_file=source_file,
        gender=global_gender,
        speaker_genders=speaker_genders,
    )
    return ParsedTranscript(meta=meta, segments=segments)
