from dataclasses import dataclass, field


@dataclass
class Segment:
    start: float
    end: float
    speaker: str | None
    text: str
    gender: str | None = field(default=None)

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
    gender: str | None = field(default=None)
    speaker_genders: dict[str, str] = field(default_factory=dict)


@dataclass
class ParsedTranscript:
    meta: TranscriptMeta
    segments: list[Segment]
