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


def _adr_prices(text: str | None = None) -> dict[PlanTier, int | None]:
    """The price cell of the ADR-003 decision table: `$0` → 0, `$49 / month` → 49,
    `contact us` → None (sales-led, ADR-003 AC3).

    Anchored on the table whose header row is `| Tier | Price | ... |`, not on the
    section it sits in: the worst-case cost tables in the same section also start
    their rows with the tier names, so a heading-scoped parse would depend on the
    tables' order in the file.
    """
    lines = (text if text is not None else ADR.read_text()).splitlines()
    header = next(
        i
        for i, line in enumerate(lines)
        if re.match(r"^\|\s*Tier\s*\|\s*Price\s*\|", line)
    )
    out: dict[PlanTier, int | None] = {}
    for line in lines[header + 2 :]:  # skip the `|---|` separator row
        m = re.match(r"^\|\s*(FREE|PRO|ENTERPRISE)\s*\|\s*([^|]*)\|", line)
        if not m:
            break  # the table ends at the first non-row line
        dollars = re.match(r"\$\s*(\d+)", m.group(2).strip())
        out[PlanTier[m.group(1)]] = int(dollars.group(1)) if dollars else None
    assert set(out) == set(PlanTier), f"ADR-003 decision table is missing a tier: {ADR}"
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


@pytest.mark.unit
def test_adr_price_parse_is_anchored_on_the_table_header():
    """Table order in the ADR must not matter: a cost table with tier-named rows
    placed *before* the decision table is ignored."""
    reordered = (
        "## Decision\n\n"
        "| Tier | ai_calls | uploads |\n|---|---|---|\n"
        "| FREE | $3.60 | $1.20 |\n| PRO | $48 | $24 |\n| ENTERPRISE | $600 | per deal |\n\n"
        "| Tier | Price | training_runs |\n|---|---|---|\n"
        "| FREE | $0 | 5 |\n| PRO | $49 / month | 100 |\n| ENTERPRISE | contact us | unlimited |\n"
    )
    assert _adr_prices(reordered) == {
        PlanTier.FREE: 0,
        PlanTier.PRO: 49,
        PlanTier.ENTERPRISE: None,
    }
