"""
DevPulse API.

Two route groups, matching the two data paths in the architecture:
  - /live/*      fast reads from Redis, backing the real-time dashboard widgets
  - /analytics/* heavier aggregate queries against the warehouse (Snowflake/Postgres)
    for historical trend views
"""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import analytics, live

app = FastAPI(
    title="DevPulse API",
    description="Fleet build/test analytics for a simulated device build farm.",
    version="0.1.0",
)

# Comma-separated list, e.g. "http://localhost:5173,https://devpulse.example.com"
_origins = os.environ.get("CORS_ALLOW_ORIGINS", "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(live.router, prefix="/live", tags=["live"])
app.include_router(analytics.router, prefix="/analytics", tags=["analytics"])


@app.get("/healthz")
def healthz():
    """Liveness/readiness probe target for Kubernetes."""
    return {"status": "ok"}
