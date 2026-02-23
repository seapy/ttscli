import os
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore


DEFAULT_CONFIG_PATH = Path.home() / ".ttscli.toml"

ENV_KEYS = {
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "elevenlabs": "ELEVENLABS_API_KEY",
    "minimax": "MINIMAX_API_KEY",
}

ENV_EXTRA: dict[str, dict[str, str]] = {
    "minimax": {"group_id": "MINIMAX_GROUP_ID"},
}


def load_config(config_path: Path | None = None) -> dict:
    path = config_path or DEFAULT_CONFIG_PATH
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        return tomllib.load(f)


def resolve_api_key(
    provider: str,
    cli_key: str | None = None,
    config_path: Path | None = None,
) -> str | None:
    if cli_key:
        return cli_key
    env_var = ENV_KEYS.get(provider)
    if env_var:
        env_val = os.environ.get(env_var)
        if env_val:
            return env_val
    config = load_config(config_path)
    return config.get(provider, {}).get("api_key")


def resolve_extra(
    provider: str,
    key: str,
    cli_value: str | None = None,
    config_path: Path | None = None,
) -> str | None:
    if cli_value:
        return cli_value
    extra_envs = ENV_EXTRA.get(provider, {})
    env_var = extra_envs.get(key)
    if env_var:
        env_val = os.environ.get(env_var)
        if env_val:
            return env_val
    config = load_config(config_path)
    return config.get(provider, {}).get(key)
