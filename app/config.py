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

RULIT_BASE_URL: str = os.getenv("RULIT_BASE_URL", "https://www.rulit.me").rstrip("/")
RULIT_USER_AGENT: str = os.getenv(
    "RULIT_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 FOLIO/1.0",
).strip()
RULIT_CACHE_TTL_SECONDS: int = _env_int("RULIT_CACHE_TTL_SECONDS", 1800)
RULIT_RATE_LIMIT_PER_MINUTE: int = _env_int("RULIT_RATE_LIMIT_PER_MINUTE", 30)
RULIT_REQUEST_TIMEOUT_SECONDS: float = float(
    os.getenv("RULIT_REQUEST_TIMEOUT_SECONDS", "10")
)

SUPABASE_URL: str = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_SECRET_KEY: str = os.getenv("SUPABASE_SECRET_KEY", "").strip()

RAG_LOCAL_EMBED_MODEL: str = os.getenv(
    "RAG_LOCAL_EMBED_MODEL",
    "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
).strip()
RAG_CHUNK_SIZE: int = _env_int("RAG_CHUNK_SIZE", 1500)
RAG_CHUNK_OVERLAP: int = _env_int("RAG_CHUNK_OVERLAP", 150)
RAG_EMBED_BATCH_SIZE: int = _env_int("RAG_EMBED_BATCH_SIZE", 64)
RAG_MAX_BATCH_CHARS: int = _env_int("RAG_MAX_BATCH_CHARS", 120_000)
