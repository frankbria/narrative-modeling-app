"""user_safe_failure_reason maps job exceptions to safe, actionable text (#518)."""

import pytest

from app.utils.job_failures import _GENERIC, user_safe_failure_reason

pytestmark = pytest.mark.unit


class _WallClock(Exception):
    pass


_WallClock.__name__ = "TrainingWallClockExceeded"


@pytest.mark.parametrize(
    "exc, needle",
    [
        (_WallClock("Training exceeded the 300s limit for the FREE plan."), "300s limit"),
        (TimeoutError("operation timed out"), "timed out while the job"),
        (ValueError("This solver needs samples of at least 2 classes but the data has 1"), "only one distinct value"),
        (ValueError("The least populated class in y has only 1 member"), "too few examples"),
        (ValueError("n_splits=5 cannot be greater than the number of members in each class"), "too few examples"),
        (ValueError("Found array with 0 sample(s)"), "no usable rows"),
        (ValueError("could not convert string to float: 'abc'"), "non-numeric text"),
        (ZeroDivisionError("division by zero"), "prediction task"),
        (ValueError("Could not determine problem type"), "prediction task"),
    ],
)
def test_known_modes_get_specific_messages(exc, needle):
    reason = user_safe_failure_reason(exc)
    assert needle in reason
    assert reason != _GENERIC


def test_unknown_exception_gets_the_generic_message():
    assert user_safe_failure_reason(RuntimeError("kaboom xyzzy")) == _GENERIC


def test_no_internal_detail_leaks_into_the_reason():
    # An exception carrying an S3 key and an access-key-shaped token must never
    # surface any of it to the user (#518 AC2 / #269).
    exc = RuntimeError("s3://secret-bucket/datasets/u1/x.csv download failed for AKIAINTERNAL123")
    reason = user_safe_failure_reason(exc)
    assert "secret-bucket" not in reason
    assert "AKIAINTERNAL123" not in reason
    assert "s3://" not in reason
    assert reason == _GENERIC
