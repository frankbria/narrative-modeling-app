"""#475: the public pricing page renders `apps/frontend/lib/billing/plans.json`, and
that file cannot drift from what enforcement allows (`app/billing/plans.py`) or from
the price column of ADR-003.

A page that advertises limits the code does not implement is the same defect as
P2.16, so the frontend's copy of the numbers is held equal to the backend's here —
the same cross-repo pattern as `test_refund_window.py` (company.ts vs refunds.py).
"""

import json
import os
import re
from pathlib import Path

import pytest

from app.billing import plans
from app.models.subscription import PlanTier

REPO = Path(__file__).resolve().parents[4]
PRICING_JSON = REPO / "apps" / "frontend" / "lib" / "billing" / "plans.json"
ADR = REPO / "docs" / "architecture" / "ADR-003-plan-limits-and-pricing.md"


def _adr_prices() -> dict[PlanTier, int | None]:
    """The price cell of the ADR-003 decision table: `$0` → 0, `$49 / month` → 49,
    `contact us` → None (sales-led, ADR-003 AC3)."""
    # The decision table sits directly under "## Decision"; the worst-case cost
    # table under "### The reasoning" also starts its rows with the tier names,
    # so stop at the first subsection as well as at the next section.
    decision = (
        ADR.read_text()
        .split("## Decision", 1)[1]
        .split("\n## ", 1)[0]
        .split("\n### ", 1)[0]
    )
    out: dict[PlanTier, int | None] = {}
    for line in decision.splitlines():
        m = re.match(r"^\|\s*(FREE|PRO|ENTERPRISE)\s*\|\s*([^|]*)\|", line)
        if not m or PlanTier[m.group(1)] in out:
            continue
        price = m.group(2).strip()
        dollars = re.match(r"\$\s*(\d+)", price)
        out[PlanTier[m.group(1)]] = int(dollars.group(1)) if dollars else None
    assert set(out) == set(PlanTier), f"ADR-003 table is missing a tier: {ADR}"
    return out


@pytest.fixture
def pricing_source():
    overrides = sorted(
        k for k in os.environ if re.match(r"PLAN_(FREE|PRO|ENTERPRISE)_", k)
    )
    if overrides:
        pytest.skip(f"PLAN_* overrides set in this process: {overrides}")
    data = json.loads(PRICING_JSON.read_text())
    return {PlanTier(t["tier"]): t for t in data["tiers"]}


@pytest.mark.unit
def test_every_tier_is_published_once(pricing_source):
    assert set(pricing_source) == set(PlanTier)


@pytest.mark.unit
def test_published_limits_equal_the_enforced_limits(pricing_source):
    """AC2: the page cannot advertise a limit enforcement does not implement."""
    for tier in PlanTier:
        published = pricing_source[tier]["limits"]
        assert set(published) == set(plans.METERED_METRICS), (
            f"{tier.name}: plans.json must publish exactly the metered metrics"
        )
        for metric in plans.METERED_METRICS:
            assert published[metric] == plans.PLAN_LIMITS[tier].limit_for(metric), (
                f"{tier.name}.{metric}: plans.json differs from app/billing/plans.py; "
                "change ADR-003, plans.py and plans.json together (#474/#475)."
            )


@pytest.mark.unit
def test_published_prices_equal_the_adr_003_prices(pricing_source):
    """The price is a product decision recorded in ADR-003; ENTERPRISE has none."""
    expected = _adr_prices()
    for tier in PlanTier:
        assert pricing_source[tier]["price_usd_per_month"] == expected[tier], (
            f"{tier.name}: plans.json price differs from the ADR-003 decision table."
        )
    assert expected[PlanTier.ENTERPRISE] is None, (
        "ENTERPRISE is sales-led (ADR-003 AC3)"
    )
