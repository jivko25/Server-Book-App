from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import ALLOWED_ORIGINS
from app.middleware.rate_limit import RulitRateLimitMiddleware
from app.routers import health, rulit, summary

app = FastAPI(
    title="FOLIO Backend API",
    description="Backend proxy for the FOLIO audiobook app (AI summaries + rulit catalog).",
    version="1.1.0",
)

app.add_middleware(RulitRateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(summary.router, prefix="/api")
app.include_router(rulit.router, prefix="/api")


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "folio-summary-api", "docs": "/docs"}
