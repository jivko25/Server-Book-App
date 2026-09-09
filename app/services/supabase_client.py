from __future__ import annotations

from supabase import Client, create_client

from app.config import SUPABASE_SECRET_KEY, SUPABASE_URL

_client: Client | None = None


def get_supabase_client() -> Client:
    global _client
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SECRET_KEY must be configured")
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)
    return _client


def check_supabase_connection() -> tuple[str, str | None]:
    """Returns (status, detail) where status is ok | error | not_configured."""
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        return "not_configured", None

    try:
        client = get_supabase_client()
        client.table("rag_books").select("id", count="exact").limit(1).execute()
    except Exception as exc:
        return "error", str(exc)

    return "ok", None
