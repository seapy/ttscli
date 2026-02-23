from abc import ABC, abstractmethod
from pathlib import Path

from ttscli.progress import StepProgress


class BaseTTSProvider(ABC):
    def __init__(self, model: str | None = None, api_key: str | None = None, **kwargs):
        self.model = model or self.default_model
        self.api_key = api_key
        for k, v in kwargs.items():
            setattr(self, k, v)

    @property
    @abstractmethod
    def default_model(self) -> str: ...

    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @property
    @abstractmethod
    def supports_speed_param(self) -> bool: ...

    @property
    def speed_range(self) -> tuple[float, float]:
        return (0.25, 4.0)

    @abstractmethod
    def synthesize(
        self,
        text: str,
        voice: str,
        speed: float,
        output_path: Path,
        step: StepProgress,
    ) -> float:
        """Synthesize text to audio. Returns actual audio duration in seconds."""
        ...

    def list_voices(self) -> list[str]:
        return []
