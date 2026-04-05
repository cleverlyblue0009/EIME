from __future__ import annotations

import os
from pathlib import Path

_ENV_LOADED = False


def load_env_file() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return

    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value

    _ENV_LOADED = True


def get_gemini_api_key(override: str | None = None) -> str | None:
    load_env_file()
    key = override or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if key:
        stripped = key.strip()
        if stripped and "your_gemini_api_key_here" not in stripped.lower():
            return stripped
    return None


def get_gemini_model() -> str:
    load_env_file()
    return os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
