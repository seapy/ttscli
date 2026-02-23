import io
from pathlib import Path

from ttscli.progress import StepProgress
from ttscli.providers.base import BaseTTSProvider

GEMINI_VOICES = ["Aoede", "Charon", "Fenrir", "Kore", "Puck"]


class GeminiTTSProvider(BaseTTSProvider):
    @property
    def default_model(self) -> str:
        return "gemini-2.5-flash-preview-tts"

    @property
    def provider_name(self) -> str:
        return "gemini"

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
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.api_key)

        step.advance_to(10, f"Synthesizing ({self.provider_name} {voice})...")
        response = client.models.generate_content(
            model=self.model,
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice,
                        )
                    )
                ),
            ),
        )

        step.advance_to(70, "Extracting audio...")
        audio_bytes = b""
        mime_type = "audio/L16;rate=24000"

        for candidate in response.candidates:
            if not candidate.content:
                continue
            for part in candidate.content.parts:
                if hasattr(part, "inline_data") and part.inline_data:
                    audio_bytes += part.inline_data.data
                    if part.inline_data.mime_type:
                        mime_type = part.inline_data.mime_type

        if not audio_bytes:
            raise ValueError(f"Gemini returned no audio for text: {repr(text[:50])}")

        sample_rate = _parse_sample_rate(mime_type)

        step.advance_to(85, "Converting to MP3...")
        from pydub import AudioSegment

        audio_segment = AudioSegment.from_raw(
            io.BytesIO(audio_bytes),
            sample_width=2,
            frame_rate=sample_rate,
            channels=1,
        )
        audio_segment.export(str(output_path), format="mp3")

        duration = len(audio_segment) / 1000.0
        step.finish()
        return duration

    def list_voices(self) -> list[str]:
        return GEMINI_VOICES


def _parse_sample_rate(mime_type: str) -> int:
    if "rate=" in mime_type:
        try:
            rate_str = mime_type.split("rate=")[1].split(";")[0].strip()
            return int(rate_str)
        except (IndexError, ValueError):
            pass
    return 24000
