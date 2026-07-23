"""Tests for app.utils.datetime timezone helpers (issue #284)."""

from datetime import UTC, datetime, timedelta, timezone

from app.utils.datetime import as_utc, utcnow


def test_utcnow_is_aware_utc():
    now = utcnow()
    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)


def test_as_utc_tags_naive_as_utc():
    # Simulates a MongoDB read-back that dropped tzinfo.
    naive = datetime(2026, 1, 1, 12, 0, 0)
    coerced = as_utc(naive)
    assert coerced.tzinfo is not None
    assert coerced.utcoffset() == timedelta(0)
    # Wall-clock unchanged — naive was already UTC, just untagged.
    assert coerced.replace(tzinfo=None) == naive


def test_as_utc_passes_through_aware():
    aware = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    assert as_utc(aware) == aware


def test_as_utc_preserves_non_utc_offset():
    # Already-aware values are returned untouched (not force-shifted to UTC).
    other = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone(timedelta(hours=5)))
    assert as_utc(other) is other


def test_as_utc_enables_arithmetic_against_aware_now():
    naive_stored = utcnow().replace(tzinfo=None)  # Mongo round-trip shape
    # Raw subtraction would TypeError; as_utc makes it work.
    delta = utcnow() - as_utc(naive_stored)
    assert delta.total_seconds() >= 0
