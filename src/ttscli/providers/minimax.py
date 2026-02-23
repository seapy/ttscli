import binascii
from pathlib import Path

from ttscli.progress import StepProgress
from ttscli.providers.base import BaseTTSProvider

MINIMAX_TTS_URL = "https://api.minimax.chat/v1/t2a_v2"

MINIMAX_VOICES = [
    "male-qn-qingse",
    "male-qn-jingying",
    "male-qn-badao",
    "male-qn-daxuesheng",
    "female-shaonv",
    "female-yujie",
    "female-chengshu",
    "female-tianmei",
    "presenter_male",
    "presenter_female",
    "audiobook_male_1",
    "audiobook_male_2",
    "audiobook_female_1",
    "audiobook_female_2",
    "male-qn-qingse-jingpin",
    "male-qn-jingying-jingpin",
    "male-qn-badao-jingpin",
    "male-qn-daxuesheng-jingpin",
    "female-shaonv-jingpin",
    "female-yujie-jingpin",
    "female-chengshu-jingpin",
    "female-tianmei-jingpin",
]


class MiniMaxTTSProvider(BaseTTSProvider):
    def __init__(self, model: str | None = None, api_key: str | None = None, **kwargs):
        self.group_id: str | None = kwargs.pop("group_id", None)
        super().__init__(model=model, api_key=api_key, **kwargs)

    @property
    def default_model(self) -> str:
        return "speech-01-turbo"

    @property
    def provider_name(self) -> str:
        return "minimax"

    @property
    def supports_speed_param(self) -> bool:
        return True

    @property
    def speed_range(self) -> tuple[float, float]:
        return (0.5, 2.0)

    def synthesize(
        self,
        text: str,
        voice: str,
        speed: float,
        output_path: Path,
        step: StepProgress,
    ) -> float:
        import httpx

        speed = max(0.5, min(2.0, speed))

        if not self.group_id:
            raise ValueError("MiniMax group_id is required. Set --minimax-group-id or MINIMAX_GROUP_ID env var.")

        url = f"{MINIMAX_TTS_URL}?GroupId={self.group_id}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "text": text,
            "stream": False,
            "voice_setting": {
                "voice_id": voice,
                "speed": speed,
                "vol": 1.0,
                "pitch": 0,
            },
            "audio_setting": {
                "sample_rate": 32000,
                "bitrate": 128000,
                "format": "mp3",
                "channel": 1,
            },
        }

        step.advance_to(10, f"Synthesizing ({self.provider_name} {voice}, speed={speed:.2f}×)...")
        with httpx.Client(timeout=120.0) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()

        step.advance_to(70, "Decoding audio...")
        data = response.json()
        audio_raw = data["data"]["audio"]
        audio_bytes = _decode_audio(audio_raw)

        step.advance_to(85, "Writing audio...")
        output_path.write_bytes(audio_bytes)

        step.advance_to(95, "Measuring duration...")
        duration = _get_mp3_duration(output_path)
        step.finish()
        return duration

    def list_voices(self) -> list[str]:
        return MINIMAX_VOICES


def _decode_audio(raw: str) -> bytes:
    try:
        return binascii.unhexlify(raw)
    except (binascii.Error, ValueError):
        import base64
        return base64.b64decode(raw)


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
