"""Durable, shared prediction log (#488).

Replaces the process-local in-memory `PredictionLog`, which — with 2 gunicorn
workers — meant each dashboard saw only the ~half of traffic its worker served,
and every restart/deploy wiped all monitoring/drift history. Persisting to Mongo
makes every worker read and write the same events and survives restarts. A TTL
index bounds retention (the in-memory version trimmed quadratically and kept full
input rows per model forever — this must not carry that over).
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Annotated, Any

from beanie import Document, Indexed
from pydantic import Field
from pymongo import ASCENDING, DESCENDING, IndexModel

from app.utils.datetime import utcnow

# How long a prediction event is retained before Mongo's TTL monitor removes it.
# Bounded deliberately (AC2/AC5) so the collection can't grow without limit.
PREDICTION_EVENT_TTL_SECONDS = int(
    os.getenv("PREDICTION_EVENT_TTL_SECONDS", str(30 * 24 * 3600))
)


class PredictionEvent(Document):
    """One served prediction (or, when ``error`` is set, a failed request)."""

    model_id: Annotated[str, Indexed()]
    prediction_id: str
    timestamp: datetime = Field(default_factory=utcnow)
    input_data: dict[str, Any] = Field(default_factory=dict)
    prediction: Any = None
    probability: float | None = None
    latency_ms: float = 0.0
    api_key_id: str | None = None
    error: str | None = None

    class Settings:
        name = "prediction_events"
        indexes = [
            # Serves get_recent_predictions: newest-first for one model. `_id`
            # (a monotonic ObjectId) is the tiebreaker so same-millisecond events
            # keep a stable insertion order for the drift window split.
            IndexModel([("model_id", ASCENDING), ("_id", DESCENDING)]),
            # TTL: Mongo removes events older than the retention window.
            IndexModel([("timestamp", ASCENDING)], expireAfterSeconds=PREDICTION_EVENT_TTL_SECONDS),
        ]
