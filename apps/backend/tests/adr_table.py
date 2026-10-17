"""ADR-003's decision table, read once for the tests that hold code and copy to it.

The table is found by its header row (`| Tier | Price | training_runs | …`), not by
the section it sits in: the worst-case cost tables in the same section also start
their rows with the tier names, so a parse scoped to the heading depends on which
table comes first in the file (#775, #776).
"""
import re
from pathlib import Path

from app.models.subscription import PlanTier

ADR = Path(__file__).resolve().parents[3] / "docs" / "adr" / "ADR-003-plan-limits-and-pricing.md"


def decision_rows(text: str | None = None) -> dict[PlanTier, list[str]]:
    """Each tier's cells in the decision table, after the tier name: price first,
    then the limits in the order of the header."""
    lines = (text if text is not None else ADR.read_text()).splitlines()
    header = next(i for i, line in enumerate(lines) if re.match(r"^\|\s*Tier\s*\|\s*Price\s*\|", line))
    rows: dict[PlanTier, list[str]] = {}
    for line in lines[header + 2 :]:  # skip the `|---|` separator row
        row = re.match(r"^\|\s*(FREE|PRO|ENTERPRISE)\s*\|(.*)\|\s*$", line)
        if not row:
            break  # the table ends at the first line that is not one of its rows
        rows[PlanTier[row.group(1)]] = [cell.strip() for cell in row.group(2).split("|")]
    assert set(rows) == set(PlanTier), f"ADR-003 decision table is missing a tier: {ADR}"
    return rows
