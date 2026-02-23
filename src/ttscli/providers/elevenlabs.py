from pathlib import Path

from ttscli.progress import StepProgress
from ttscli.providers.base import BaseTTSProvider

DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel


class ElevenLabsTTSProvider(BaseTTSProvider):
    def __init__(self, model: str | None = None, api_key: str | None = None, **kwargs):
        self.stability: float = kwargs.pop("stability", 0.5)
        self.similarity_boost: float = kwargs.pop("similarity_boost", 0.75)
        super().__init__(model=model, api_key=api_key, **kwargs)

    @property
    def default_model(self) -> str:
        return "eleven_multilingual_v2"

    @property
    def provider_name(self) -> str:
        return "elevenlabs"

    @property
    def supports_speed_param(self) -> bool:
        return False

    def synthesize(
        self,
        text: str,
        voice: str,
        speed: float,
        output_path: Path,
        step: StepProgress,
    ) -> float:
        from elevenlabs import ElevenLabs, VoiceSettings

        client = ElevenLabs(api_key=self.api_key)

        step.advance_to(10, f"Synthesizing ({self.provider_name} {voice[:8]}...)...")
        audio_generator = client.text_to_speech.convert(
            voice_id=voice,
            text=text,
            model_id=self.model,
            voice_settings=VoiceSettings(
                stability=self.stability,
                similarity_boost=self.similarity_boost,
            ),
            output_format="mp3_44100_128",
        )

        step.advance_to(60, "Writing audio...")
        with open(output_path, "wb") as f:
            for chunk in audio_generator:
                f.write(chunk)

        step.advance_to(95, "Measuring duration...")
        duration = _get_mp3_duration(output_path)
        step.finish()
        return duration

    def list_voices(self) -> list[str]:
        from elevenlabs import ElevenLabs
        client = ElevenLabs(api_key=self.api_key)
        try:
            voices_resp = client.voices.get_all()
            return [f"{v.voice_id}  ({v.name})" for v in (voices_resp.voices or [])]
        except Exception:
            return []


def _get_mp3_duration(path: Path) -> float:
    try:
        from mutagen.mp3 import MP3
        return MP3(str(path)).info.length
    except Exception:
        try:
            from pydub import AudioSegment
            return len(AudioSegment.from_mp3(str(path))) / 1000.0
        except Exception:
            return 0.0
