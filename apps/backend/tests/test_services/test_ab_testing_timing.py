"""Datetime-hygiene regression tests for A/B test duration math (issue #284).

``experiment.started_at`` comes back *naive* from MongoDB; the completion and
metrics paths subtract it from an aware ``now``. Without ``as_utc`` coercion that
raises ``TypeError``. Build experiments with naive timestamps and assert the
arithmetic works.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from app.models.ab_test import ABTest, ExperimentStatus, Variant
from app.services.ab_testing import ABTestingService

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("beanie_models_initialized")]


def _experiment(**over) -> ABTest:
    base = dict(
        experiment_id="exp1",
        name="t",
        user_id="u1",
        variants=[
            Variant(variant_id="v1", model_id="m1", name="Control", traffic_percentage=50.0),
            Variant(variant_id="v2", model_id="m2", name="Treatment", traffic_percentage=50.0),
        ],
        primary_metric="accuracy",
    )
    base.update(over)
    return ABTest(**base)


def test_metrics_duration_with_naive_running_start_does_not_raise():
    started = datetime(2026, 1, 1, 12, 0, 0)  # naive read-back
    exp = _experiment(status=ExperimentStatus.RUNNING, started_at=started)
    metrics = asyncio.run(ABTestingService.get_experiment_metrics(exp))
    assert metrics["duration"] is not None
    assert metrics["duration"] > 0


def test_metrics_duration_with_naive_completed_span():
    exp = _experiment(
        status=ExperimentStatus.COMPLETED,
        started_at=datetime(2026, 1, 1, 12, 0, 0),
        ended_at=datetime(2026, 1, 1, 13, 0, 0),
    )
    metrics = asyncio.run(ABTestingService.get_experiment_metrics(exp))
    assert metrics["duration"] == 3600.0


def test_check_completion_duration_limit_with_naive_start():
    started = datetime(2026, 1, 1, 12, 0, 0)  # far past, naive
    exp = _experiment(
        status=ExperimentStatus.RUNNING, started_at=started, test_duration_hours=1
    )
    done, reason = asyncio.run(ABTestingService.check_experiment_completion(exp))
    # aware now - naive start must not raise; elapsed >> 1h -> duration limit hit.
    assert done is True
    assert reason == "duration_limit"


def test_check_completion_within_duration_naive_start():
    started = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1)  # naive UTC (Mongo shape)
    exp = _experiment(
        status=ExperimentStatus.RUNNING, started_at=started, test_duration_hours=24
    )
    done, reason = asyncio.run(ABTestingService.check_experiment_completion(exp))
    assert done is False  # under the limit, not enough samples
