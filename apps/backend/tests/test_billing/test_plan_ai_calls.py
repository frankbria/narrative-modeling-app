"""The `ai_calls` metric (#461): per-tier, per-period, and finite everywhere.

Unmetered model calls are the cost blow-up that shows up as an invoice, not an
outage. The ceiling is finite for *every* tier — including ENTERPRISE, which is
UNLIMITED on the other metrics — because AC5 wants a backstop a metering bug or a
config mistake cannot lift.
"""
import logging

from app.billing.plans import METERED_METRICS, PLAN_LIMITS, UNLIMITED, limits_for
from app.models.subscription import PlanTier


def test_ai_calls_is_metered():
    assert "ai_calls" in METERED_METRICS
    for limits in PLAN_LIMITS.values():
        assert limits.limit_for("ai_calls") == limits.ai_calls


def test_every_tier_has_a_finite_positive_ceiling():
    for tier in PlanTier:
        ceiling = limits_for(tier).limit_for("ai_calls")
        assert ceiling != UNLIMITED and ceiling > 0, f"{tier}: ai_calls must stay finite"


def test_ceilings_are_monotonic_by_tier():
    free, pro, ent = (limits_for(t).ai_calls for t in (PlanTier.FREE, PlanTier.PRO, PlanTier.ENTERPRISE))
    assert 0 < free <= pro <= ent


def test_an_unlimited_override_is_refused(monkeypatch, caplog):
    """`PLAN_*_AI_CALLS=-1` follows this module's convention and must not work here."""
    from app.billing.plans import _env_positive_int

    monkeypatch.setenv("PLAN_ENTERPRISE_AI_CALLS", "-1")
    with caplog.at_level(logging.WARNING):
        assert _env_positive_int("PLAN_ENTERPRISE_AI_CALLS", 50_000) == 50_000
    assert "PLAN_ENTERPRISE_AI_CALLS" in caplog.text
