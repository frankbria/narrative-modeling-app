"""What a metered request actually costs (#368, second review round).

Two holes a per-request charge leaves, both raised by `codex review`:

* A `predictions` limit of 1000 means 1000 predictions. Charging one unit per
  *request* lets a tenant send 1000 requests of 1000 records each and receive a
  million — the enforced number stops matching the metric's name.
* A reservation belongs to the period it was taken from. Recomputing the period at
  refund time means a request that fails across a month boundary refunds the new
  month and leaves last month's unit burned.
"""

import pytest
from starlette.datastructures import Headers
from starlette.requests import Request

from app.billing import enforcement, metering
from app.models.usage import UsageRecord

pytestmark = pytest.mark.asyncio


def _request(body: bytes = b"{}") -> Request:
    """A Request whose body is already cached, as it is behind a real server."""
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "path": "/x",
        "headers": Headers({"content-type": "application/json"}).raw,
        "query_string": b"",
        "state": {},
    }
    request = Request(scope)
    request._body = body
    return request


async def _units(user_id: str, metric: str, period: str | None = None) -> int:
    doc = await UsageRecord.find_one(
        UsageRecord.user_id == user_id,
        UsageRecord.period_key == (period or metering.period_key_for()),
        UsageRecord.metric == metric,
    )
    return doc.units if doc else 0


class TestPerRecordCharge:
    async def test_a_batch_of_records_costs_one_unit_each(self, setup_database):
        request = _request(b'{"data": [{"x": 1}, {"x": 2}, {"x": 3}]}')

        await enforcement.reserve_records(request, "u-recs", "predictions")

        assert await _units("u-recs", "predictions") == 3

    async def test_a_batch_larger_than_the_remaining_quota_is_refused(
        self, setup_database
    ):
        # 8 of 10 used; a 5-record request does not fit. All-or-nothing rather than
        # a partial fill, because a half-served prediction request is not a thing
        # the caller can use.
        await metering.consume("u-overflow", "predictions", limit=10, amount=8)
        request = _request(b'{"data": [{}, {}, {}, {}, {}]}')

        with pytest.raises(Exception) as exc:
            await enforcement.reserve_records(
                request, "u-overflow", "predictions", limit=10
            )

        assert getattr(exc.value, "status_code", None) == 402
        assert await _units("u-overflow", "predictions") == 8

    async def test_an_unreadable_body_still_costs_one(self, setup_database):
        # Enforcement must not 500 on a malformed body — that is the route's job to
        # report. It charges the floor and lets the route return its own 422, which
        # the refund middleware then gives back.
        request = _request(b"not json at all")

        await enforcement.reserve_records(request, "u-junk", "predictions")

        assert await _units("u-junk", "predictions") == 1

    async def test_an_empty_batch_still_costs_one(self, setup_database):
        request = _request(b'{"data": []}')

        await enforcement.reserve_records(request, "u-empty", "predictions")

        assert await _units("u-empty", "predictions") == 1


class TestRefundTargetsTheReservedPeriod:
    async def test_refund_uses_the_period_the_unit_was_taken_from(
        self, setup_database
    ):
        """A request that fails across a month rollover.

        The reservation is recorded against `2099-01`; by the time the refund runs
        the clock says `2099-02`. Recomputing the period there decrements a month
        that was never charged, and leaves the real one burned.
        """
        old_period = "2099-01"
        await UsageRecord(
            user_id="u-roll",
            period_key=old_period,
            metric="uploads",
            units=1,
        ).insert()

        await metering.refund("u-roll", "uploads", period_key=old_period)

        assert await _units("u-roll", "uploads", old_period) == 0

    async def test_the_reservation_carries_its_period(self, setup_database):
        request = _request()

        await enforcement.reserve(request, "u-carry", "uploads")

        reservation = getattr(request.state, enforcement._RESERVATION)
        assert reservation["period_key"] == metering.period_key_for()
        assert reservation["amount"] == 1

    async def test_the_middleware_refunds_what_was_reserved(self, setup_database):
        request = _request()
        await enforcement.reserve_records(
            request, "u-mw", "predictions", body_override=3
        )
        assert await _units("u-mw", "predictions") == 3

        await enforcement.QuotaRefundMiddleware._refund(request)

        # All three, not one. A middleware that assumed a unit per request would
        # leave two burned on every failed batch.
        assert await _units("u-mw", "predictions") == 0
