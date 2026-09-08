import os

from dotenv import load_dotenv

load_dotenv()


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite").strip()
MAX_OUTPUT_TOKENS: int = _env_int("MAX_OUTPUT_TOKENS", 512)
MAX_CHAPTER_CHARS: int = _env_int("MAX_CHAPTER_CHARS", 12000)
TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0"))

_allowed_origins_raw = os.getenv("ALLOWED_ORIGINS", "*").strip()
ALLOWED_ORIGINS: list[str] = (
    ["*"]
    if _allowed_origins_raw == "*"
    else [origin.strip() for origin in _allowed_origins_raw.split(",") if origin.strip()]
)
