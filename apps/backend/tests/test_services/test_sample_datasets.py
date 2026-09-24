"""#770 AC1: the onboarding samples are real enough to train, and the catalogue
tells the truth about them.

Before #770 each sample was 14 rows while the catalogue advertised 10 000 rows /
2.5 MB and an 0.82 accuracy nobody had measured. Now every size figure is read
from the file, and the score the copy quotes is re-measured here, the way
`POST /ml/train` runs a quick-mode job.
"""

import asyncio
from pathlib import Path

import pandas as pd
import pytest

from app.billing.plans import PlanTier, training_ceilings_for
from app.services.model_training.automl_engine import AutoMLEngine
from app.services.model_training.training_mode import resolve_mode_config
from app.services.onboarding_service import OnboardingService

_SAMPLES = Path(__file__).resolve().parents[2] / "sample_datasets"


def _catalogue() -> list[dict]:
    return asyncio.run(OnboardingService().get_sample_datasets())


def test_there_are_three_samples_and_each_has_its_file():
    ids = {d["dataset_id"] for d in _catalogue()}
    assert ids == {"customer_churn", "house_prices", "marketing_response"}
    for dataset_id in ids:
        assert (_SAMPLES / f"{dataset_id}.csv").is_file()


@pytest.mark.parametrize("entry", _catalogue(), ids=lambda d: d["dataset_id"])
def test_catalogue_figures_are_read_from_the_file(entry):
    path = _SAMPLES / f"{entry['dataset_id']}.csv"
    df = pd.read_csv(path)

    assert 1_000 <= len(df) <= 5_000
    assert entry["rows"] == len(df)
    assert entry["columns"] == len(df.columns)
    assert entry["size_mb"] == round(path.stat().st_size / 1_000_000, 2)
    assert entry["target_column"] in df.columns
    assert entry["feature_columns"] == [c for c in df.columns if c != entry["target_column"]]
    assert entry["preview_data"] == df.head(5).to_dict("records")


@pytest.mark.parametrize("entry", _catalogue(), ids=lambda d: d["dataset_id"])
async def test_each_sample_trains_in_quick_mode_to_its_stated_score(entry):
    """The quoted score is a floor a real quick-mode run clears under FREE's ceilings.

    Accuracy for classification, R² for regression: whatever the engine reports as
    `test_score`, which is what the model page shows the user afterwards.
    """
    df = pd.read_csv(_SAMPLES / f"{entry['dataset_id']}.csv")
    quick = resolve_mode_config("quick")
    free = training_ceilings_for(PlanTier.FREE)
    assert quick["max_models"] <= free.max_models
    assert quick["time_limit"] <= free.time_limit_seconds

    # Mirrors train_model_task's engine for a quick-mode request with no overrides.
    engine = AutoMLEngine(
        max_models=quick["max_models"],
        time_limit=quick["time_limit"],
        cv_folds=5,
        test_size=0.2,
        random_state=42,
        enable_tuning=False,
        early_stop_score=quick["early_stop_score"],
    )
    result = await asyncio.wait_for(
        engine.run(df, entry["target_column"], None), timeout=free.wall_clock_seconds
    )

    assert result.problem_type.value == entry["problem_type"]
    assert result.best_model.test_score >= entry["expected_accuracy"]
