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

        reservations = getattr(request.state, enforcement._RESERVATION)
        assert len(reservations) == 1
        assert reservations[0]["period_key"] == metering.period_key_for()
        assert reservations[0]["amount"] == 1

    async def test_two_metrics_on_one_request_are_both_refunded(
        self, setup_database
    ):
        """No route composes two metrics today. One will.

        A single reservation slot loses whichever charge is written second — and
        accumulating into it only rescues the case where both are the *same*
        metric. Either way the loss is silent, and the symptom is a slow leak of
        quota nobody can trace. A list has no case to get wrong.
        """
        request = _request()
        await enforcement.reserve(request, "u-two", "uploads")
        await enforcement.reserve(request, "u-two", "predictions", 4)

        assert await _units("u-two", "uploads") == 1
        assert await _units("u-two", "predictions") == 4

        await enforcement.QuotaRefundMiddleware._refund(request)

        assert await _units("u-two", "uploads") == 0
        assert await _units("u-two", "predictions") == 0

    async def test_release_hands_back_a_reservation_the_middleware_cannot_see(
        self, setup_database
    ):
        """A 2xx that did not do the work (#459).

        The middleware refunds on >= 400, which covers failures. It cannot see a
        route that returns 200 having decided *not* to do the thing — and
        `/upload/secure` does exactly that when it finds high-risk PII: 200,
        `requires_confirmation`, no dataset. Without this the tenant pays for a
        dataset they never received, and pays again at `/confirm-pii-upload`.
        """
        request = _request()
        await enforcement.reserve(request, "u-release", "uploads")
        assert await _units("u-release", "uploads") == 1

        await enforcement.release(request)

        assert await _units("u-release", "uploads") == 0

    async def test_release_is_idempotent(self, setup_database):
        """It clears the list, so a later middleware refund on the same request
        cannot hand back a second unit — quota minted from nothing."""
        request = _request()
        await enforcement.reserve(request, "u-twice", "uploads")

        await enforcement.release(request)
        await enforcement.release(request)
        await enforcement.QuotaRefundMiddleware._refund(request)

        assert await _units("u-twice", "uploads") == 0

    async def test_release_on_a_request_that_reserved_nothing_is_a_no_op(
        self, setup_database
    ):
        await enforcement.release(_request())

    async def test_quota_marks_its_dependency_with_the_metric(self):
        """So a route table can be asked what it meters (#459's registry test).

        Reading `__closure__` positionally would work today and break the first
        time `dependency` grows another free variable.
        """
        assert enforcement.quota("uploads").__quota_metric__ == "uploads"
        assert enforcement.quota("predictions").__quota_metric__ == "predictions"

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
