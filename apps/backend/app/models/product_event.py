"""Funnel events (#769): account → first upload → first model → 402 → checkout.

One row per event, written server-side by the code path that already knows it
happened (`app/services/product_events.py`). No dataset content and no PII beyond
``user_id``. Erased with the user, and expired after 13 months either way.

``account_created`` is written by the frontend's NextAuth ``events.createUser``
straight into this collection (``apps/frontend/lib/product-events.ts``), so the
collection name and field names are a cross-language contract.
"""

from datetime import datetime
from typing import Annotated, Any

from beanie import Document, Indexed
from pydantic import Field
from pymongo import ASCENDING, IndexModel

from app.utils.datetime import utcnow

PRODUCT_EVENT_TTL_SECONDS = 395 * 24 * 3600  # 13 months: a year-on-year comparison


class ProductEvent(Document):
    user_id: Annotated[str, Indexed()]
    event: str
    timestamp: datetime = Field(default_factory=utcnow)
    properties: dict[str, Any] = Field(default_factory=dict)
    # Set for events that may happen at most once per key (first_*, a Stripe
    # session): the unique index below turns a repeat into a no-op.
    dedupe_key: str | None = None

    class Settings:
        name = "product_events"
        indexes = [
            IndexModel([("event", ASCENDING), ("timestamp", ASCENDING)]),
            IndexModel(
                [("user_id", ASCENDING), ("dedupe_key", ASCENDING)],
                name="user_dedupe_unique",
                unique=True,
                partialFilterExpression={"dedupe_key": {"$type": "string"}},
            ),
            IndexModel([("timestamp", ASCENDING)], expireAfterSeconds=PRODUCT_EVENT_TTL_SECONDS),
        ]
