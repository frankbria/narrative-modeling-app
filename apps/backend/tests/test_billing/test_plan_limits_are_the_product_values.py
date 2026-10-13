"""#474: the plan limits are product decisions recorded in ADR-003, and the code,
the ADR and the deployed values cannot drift apart.

Three guards:

* ``plans.py`` defaults equal the table in ADR-003 (the ADR is what the operator
  and the pricing page cite, so a code edit without an ADR edit is a silent
  repricing).
* No deploy surface sets a ``PLAN_*`` override (AC4): the code defaults ARE the
  deployed values. The e2e runner is the one allowed exception (#550).
* The FREE tier's worst-case monthly cost stays under the acquisition budget
  (AC6), priced at the most expensive per-unit figures in ADR-003.
"""

import os
import re
from pathlib import Path

import pytest

from app.billing import plans
from app.models.subscription import PlanTier
from tests.adr_table import decision_rows

REPO = Path(__file__).resolve().parents[4]

_METRICS = ("training_runs", "predictions", "uploads", "ai_calls")


def _limit(cell: str) -> int:
    return plans.UNLIMITED if cell.lower() == "unlimited" else int(cell.replace(" ", "").replace(",", ""))


def _adr_limits(text: str | None = None) -> dict[PlanTier, dict[str, int]]:
    """The four limits of each tier in the decision table: `| FREE | $0 | 5 | 1 000 | 10 | 30 |`.
    The price is the first cell; the metrics follow in METERED_METRICS order."""
    return {
        tier: dict(zip(_METRICS, map(_limit, cells[1:5]), strict=True))
        for tier, cells in decision_rows(text).items()
    }


@pytest.fixture
def default_plans():
    """`plans.py` as imported, which is the defaults unless this process carries a
    PLAN_* override — in which case the comparison is meaningless, so skip rather
    than reload (a reload swaps the dataclass, breaking every by-name import)."""
    overrides = sorted(
        k for k in os.environ if re.match(r"PLAN_(FREE|PRO|ENTERPRISE)_", k)
    )
    if overrides:
        pytest.skip(f"PLAN_* overrides set in this process: {overrides}")
    return plans


@pytest.mark.unit
def test_code_defaults_match_adr_003(default_plans):
    expected = _adr_limits()
    for tier in PlanTier:
        for metric in _METRICS:
            assert (
                default_plans.PLAN_LIMITS[tier].limit_for(metric)
                == expected[tier][metric]
            ), (
                f"{tier.name}.{metric}: plans.py default differs from ADR-003; "
                "change the ADR and the code together (#474)."
            )


_SKIP_DIRS = {"node_modules", ".venv", ".next", "__pycache__", ".git"}
#: The one sanctioned override: every e2e test shares one user (#550).
_SANCTIONED = {"apps/frontend/test-e2e.sh"}


def _deploy_surfaces():
    """Every compose file, workflow, env file and shell script in the repo, recursively
    (a nested `apps/backend/docker-compose.test.yml` counts as much as a root one).
    Pruned walk: descending into `node_modules` first and filtering after cost 3s."""
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        in_workflows = Path(root).as_posix().endswith(".github/workflows")
        for name in files:
            if (
                (name.startswith("docker-compose") and name.endswith((".yml", ".yaml")))
                or (in_workflows and name.endswith((".yml", ".yaml")))
                or name.startswith(".env")
                or name.endswith(".sh")
            ):
                yield Path(root) / name


@pytest.mark.unit
def test_no_deploy_surface_overrides_the_plan_limits():
    """AC4: the deployed limits are the code defaults, so the two cannot diverge."""
    offenders = []
    sanctioned_seen = set()
    for path in _deploy_surfaces():
        rel = path.relative_to(REPO).as_posix()
        for i, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
            if re.search(r"\bPLAN_(FREE|PRO|ENTERPRISE)_[A-Z_]+\s*[:=]", line):
                if rel in _SANCTIONED:
                    sanctioned_seen.add(rel)
                else:
                    offenders.append(f"{rel}:{i}: {line.strip()}")
    assert not offenders, (
        "PLAN_* overrides belong nowhere in deployment — app/billing/plans.py is the "
        "single source (#474 AC4). Offenders:\n" + "\n".join(offenders)
    )
    # Anti-stale: the allowlist must still be needed, or it is hiding nothing.
    assert sanctioned_seen == _SANCTIONED


#: Worst-case cost of one unit, USD, from the ADR-003 unit-economics table. An
#: `ai_call` and an `upload` each fire one model completion; training is CPU
#: for at most the FREE wall clock; a prediction is microseconds of CPU.
_WORST_CASE_UNIT_USD = {
    "ai_calls": 0.12,
    "uploads": 0.12,
    "training_runs": 0.04,
    "predictions": 0.00001,
}
#: "≈ $5" in ADR-003; the components sum to $5.01, so allow a nickel of rounding.
FREE_TIER_MONTHLY_BUDGET_USD = 5.05


@pytest.mark.unit
def test_free_tier_worst_case_is_within_the_acquisition_budget(default_plans):
    """AC6: a free user cannot cost more than the owner agreed to spend on acquisition."""
    free = default_plans.PLAN_LIMITS[PlanTier.FREE]
    worst_case = sum(free.limit_for(m) * _WORST_CASE_UNIT_USD[m] for m in _METRICS)
    assert worst_case <= FREE_TIER_MONTHLY_BUDGET_USD, (
        f"FREE worst case is ${worst_case:.2f}/month against a "
        f"${FREE_TIER_MONTHLY_BUDGET_USD:.2f} budget (ADR-003)."
    )
    assert free.ai_calls > 0 and free.ai_calls != plans.UNLIMITED


@pytest.mark.unit
def test_adr_limit_parse_is_anchored_on_the_table_header():
    """Table order in the ADR must not matter (#776): a cost table whose rows start
    with the tier names, placed before the decision table, is not read as limits."""
    reordered = (
        "## Decision\n\n"
        "| Tier | ai_calls | uploads | training_runs | predictions |\n|---|---|---|---|---|\n"
        "| FREE | 7 | 7 | 7 | 7 |\n| PRO | 8 | 8 | 8 | 8 |\n| ENTERPRISE | 9 | 9 | 9 | 9 |\n\n"
        "| Tier | Price | training_runs | predictions | uploads | ai_calls |\n|---|---|---|---|---|---|\n"
        "| FREE | $0 | 5 | 1 000 | 10 | 30 |\n"
        "| PRO | $49 / month | 100 | 50,000 | 500 | 1 000 |\n"
        "| ENTERPRISE | contact us | unlimited | unlimited | unlimited | 20 000 |\n"
    )

    limits = _adr_limits(reordered)

    assert limits[PlanTier.FREE] == {"training_runs": 5, "predictions": 1000, "uploads": 10, "ai_calls": 30}
    assert limits[PlanTier.PRO]["predictions"] == 50000
    assert limits[PlanTier.ENTERPRISE]["uploads"] == plans.UNLIMITED
    assert limits[PlanTier.ENTERPRISE]["ai_calls"] == 20000
