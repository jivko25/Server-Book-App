from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import ALLOWED_ORIGINS
from app.routers import health, summary

app = FastAPI(
    title="FOLIO Summary API",
    description="Thin proxy for AI chapter summaries in the FOLIO audiobook app.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(summary.router, prefix="/api")


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "folio-summary-api", "docs": "/docs"}
