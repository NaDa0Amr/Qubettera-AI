from __future__ import annotations

from pydantic import BaseModel


class AnalyticsResponse(BaseModel):
    # Deliberately loose (dict passthrough) — the shape is documented and
    # owned by Analytics-Intelligence-Layer/src/analytics/engine.py. Mirroring
    # it field-by-field here would just be a second place to keep in sync.
    model_config = {"extra": "allow"}