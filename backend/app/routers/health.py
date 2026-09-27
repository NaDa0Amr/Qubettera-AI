from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.app.core import config

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Liveness: the process is up. Lightweight, no dependencies touched."""
    return {"status": "ok"}


@router.get("/health/ready")
async def ready() -> JSONResponse:
    """Readiness: are the Week 1/3 and Week 4 repos actually reachable?

    200 when everything is found, 503 with the resolved paths when not, so a
    reviewer (or you) can see immediately why /week3 or /week4 would fail.
    """
    deps = config.repo_status()
    ok = all(d["found"] for d in deps.values())
    return JSONResponse(
        status_code=200 if ok else 503,
        content={"status": "ready" if ok else "degraded", "dependencies": deps},
    )
