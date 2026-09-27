from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException

from backend.app.core import config
from backend.app.schemas.personas import Persona

logger = logging.getLogger("app.routers.personas")
router = APIRouter(tags=["personas"])


@router.get("/personas", response_model=list[Persona])
async def list_personas() -> list[dict]:
    """Return every persona in Multi-Agent-Collaboration/personas/personas.json.

    This is the exact same file `week3_events._default_participant_ids()`
    reads when a `/week3/discuss` request omits `participant_ids` — so
    "participant_ids: null means all personas" (C4) is true by construction,
    not by convention: both read config.DEFAULT_PERSONAS_PATH.
    """
    path = config.DEFAULT_PERSONAS_PATH
    if not path.is_file():
        raise HTTPException(
            status_code=503,
            detail=f"personas.json not found at {path}. Check MAC_REPO_PATH.",
        )

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.error("personas.json is not valid JSON: %s", exc)
        raise HTTPException(
            status_code=500, detail=f"personas.json is not valid JSON: {exc}"
        ) from exc

    if not isinstance(data, list):
        raise HTTPException(
            status_code=500, detail="personas.json must contain a JSON array."
        )

    return data