"""Timezone-aware datetime helpers.

The codebase standard is **timezone-aware UTC** datetimes (``datetime.now(UTC)``),
not the deprecated naive ``datetime.utcnow()``. Two hazards this module guards:

1. FastAPI serializes naive datetimes without an offset, breaking the ISO-8601
   API contract.
2. MongoDB/Beanie **drops tzinfo on read-back**, so a stored datetime comes back
   naive. Subtracting a naive stored value from an aware ``now`` raises
   ``TypeError``. Coerce stored values with :func:`as_utc` before arithmetic.
"""

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Timezone-aware current UTC time.

    Prefer over ``datetime.utcnow()`` (deprecated, naive). Usable as a Pydantic
    ``default_factory`` callable.
    """
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    """Coerce a possibly-naive datetime to UTC-aware.

    A naive value (e.g. a MongoDB round-trip that dropped tzinfo) is assumed to
    already be UTC and tagged as such; an already-aware value is returned as-is.
    """
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value
