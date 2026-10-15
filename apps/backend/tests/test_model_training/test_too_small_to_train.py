"""A dataset the problem detector cannot place stops before feature engineering,
and the job says why (#1055). It used to train anyway, fail inside feature selection
with numpy's divide error, and show the generic "unexpected error"."""

import pandas as pd
import pytest

from app.services.model_training.automl_engine import AutoMLEngine, TrainingNotPossible
from app.utils.job_failures import user_safe_failure_reason

# e2e/test-data/sample.csv: five rows, a text target.
FIVE_ROWS = pd.DataFrame(
    {"age": [25, 35, 45, 28, 52], "income": [40, 60, 80, 45, 90], "purchased": ["no", "yes", "yes", "no", "yes"]}
)


@pytest.mark.asyncio
async def test_too_few_rows_stops_with_the_row_count_and_the_minimum():
    with pytest.raises(TrainingNotPossible) as stopped:
        await AutoMLEngine().run(FIVE_ROWS, "purchased")

    reason = user_safe_failure_reason(stopped.value)
    assert "5 rows" in reason and "at least 10" in reason


@pytest.mark.asyncio
async def test_an_undetermined_task_keeps_the_existing_advice():
    with pytest.raises(TrainingNotPossible) as stopped:
        await AutoMLEngine().run(pd.concat([FIVE_ROWS] * 4, ignore_index=True), "missing_column")

    assert "Could not determine a prediction task" in user_safe_failure_reason(stopped.value)
