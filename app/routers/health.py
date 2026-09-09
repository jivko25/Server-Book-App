from fastapi import APIRouter

from app.config import GEMINI_MODEL
from app.schemas import HealthResponse
from app.services.supabase_client import check_supabase_connection

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    supabase_status, supabase_detail = check_supabase_connection()
    overall = "ok" if supabase_status == "ok" else "degraded"

    return HealthResponse(
        status=overall,
        model=GEMINI_MODEL,
        supabase=supabase_status,
        supabaseDetail=supabase_detail,
    )
