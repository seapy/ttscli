import re
from pathlib import Path

from ttscli.models import ParsedTranscript, Segment, TranscriptMeta

SEGMENT_RE = re.compile(
    r'\*\*\[(\d{1,2}:\d{2}(?::\d{2})?) → (\d{1,2}:\d{2}(?::\d{2})?)\]\*\*'
    r'(?:\s+\*\*(\w+)\*\*)?\s+(.*)'
)


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

    segments: list[Segment] = []
    for line in lines:
        m = SEGMENT_RE.match(line.strip())
        if m:
            start = _parse_time(m.group(1))
            end = _parse_time(m.group(2))
            speaker = m.group(3) or None
            seg_text = m.group(4).strip()
            if seg_text:
                segments.append(Segment(start=start, end=end, speaker=speaker, text=seg_text))

    meta = TranscriptMeta(
        provider=provider,
        model=model,
        language=language,
        duration=duration,
        source_file=source_file,
    )
    return ParsedTranscript(meta=meta, segments=segments)
