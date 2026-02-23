from dataclasses import dataclass, field


@dataclass
class Segment:
    start: float
    end: float
    speaker: str | None
    text: str

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class TranscriptMeta:
    provider: str
    model: str
    language: str
    duration: float
    source_file: str


@dataclass
class ParsedTranscript:
    meta: TranscriptMeta
    segments: list[Segment]
