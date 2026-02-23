from ttscli.providers.base import BaseTTSProvider


def get_provider(name: str) -> type[BaseTTSProvider]:
    if name == "gemini":
        from ttscli.providers.gemini import GeminiTTSProvider
        return GeminiTTSProvider
    elif name == "elevenlabs":
        from ttscli.providers.elevenlabs import ElevenLabsTTSProvider
        return ElevenLabsTTSProvider
    elif name == "minimax":
        from ttscli.providers.minimax import MiniMaxTTSProvider
        return MiniMaxTTSProvider
    else:
        raise ValueError(f"Unknown provider: {name}")
