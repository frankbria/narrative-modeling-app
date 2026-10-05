"""Map a background-job exception to a user-safe failure reason (#518).

Training and batch jobs run in ``BackgroundTasks`` and previously stored the raw
``str(exc)`` as the job's user-facing error — a #269-style leak on the job path
(S3 keys, internal paths, library internals) AND unactionable prose for a paying
customer. This classifies the common, recoverable failure modes into a plain,
actionable sentence; the raw exception stays server-side (``logger.exception`` at
the call site, correlated by the job id). Anything unrecognised falls back to a
generic message that tells the user what to quote to support (AC4).

The known modes are matched by exception type where reliable and by message
substring for the sklearn/pandas ValueErrors raised deep in the training path —
heuristic by nature (AC5: "start with the ones the AutoML path already detects").
"""

from __future__ import annotations

from collections.abc import Callable

_GENERIC = (
    "The job failed due to an unexpected error. Quote this job's id to support "
    "and we can investigate."
)


def _has(low: str, *needles: str) -> bool:
    return any(n in low for n in needles)


def _is_identifier_only(exc: BaseException, low: str) -> bool:
    # First of the substring buckets, which could otherwise match a column name.
    return _has(low, "per-row identifier")


def _is_timeout(exc: BaseException, low: str) -> bool:
    # A transient infra hiccup (e.g. a slow S3 read), NOT the plan's wall-clock
    # limit (TrainingWallClockExceeded). Keep the two distinct: never say
    # "wall-clock" in this message.
    return isinstance(exc, TimeoutError) or _has(low, "timed out", "timeout")


def _is_empty(exc: BaseException, low: str) -> bool:
    return type(exc).__name__ == "EmptyDataError" or _has(low, "no columns to parse", "empty csv")


def _is_unparseable(exc: BaseException, low: str) -> bool:
    return type(exc).__name__ == "ParserError" or _has(
        low, "error tokenizing", "not valid csv", "could not be read as csv"
    )


def _is_single_class(exc: BaseException, low: str) -> bool:
    # NOTE: "least populated class ... only N member" is NOT this: that is a
    # multi-class target where one class is too rare for stratified CV (next rule).
    return _has(
        low,
        "number of classes",
        "at least 2 classes",
        "only one class",
        "needs samples of at least",
        "single value",
        "only one distinct",
    )


def _is_too_few(exc: BaseException, low: str) -> bool:
    # Too few rows overall, or too few examples of some target value, for
    # cross-validation (incl. sklearn's "least populated class ... only N member").
    return _has(
        low,
        "n_splits",
        "least populated class",
        "greater than the number of members",
        "cannot have number of splits",
        "too few",
    ) or (_has(low, "minimum", "not enough") and _has(low, "row", "sample"))


def _is_no_rows(exc: BaseException, low: str) -> bool:
    return _has(low, "found array with 0 sample", "0 sample(s)", "no usable rows", "input contains nan")


def _is_non_numeric(exc: BaseException, low: str) -> bool:
    return _has(low, "could not convert string to float", "invalid literal for")


def _is_undetermined_task(exc: BaseException, low: str) -> bool:
    # AutoML 'unknown' / divide on a tiny sample (the 6-row case the project notes record).
    return (
        isinstance(exc, ZeroDivisionError)
        or _has(low, "could not determine")
        or ("unknown" in low and _has(low, "problem", "task", "type"))
    )


# First match wins, so order matters.
_RULES: tuple[tuple[Callable[[BaseException, str], bool], str], ...] = (
    (
        _is_identifier_only,
        "Every column other than the target looks like a per-row identifier "
        "(such as a customer ID), so there is nothing to learn from. Add the "
        "columns that describe each row and try again.",
    ),
    (
        _is_timeout,
        "A storage or network operation timed out while the job was running. "
        "This is usually temporary — please try again.",
    ),
    (_is_empty, "The uploaded file appears to be empty. Upload a non-empty CSV and try again."),
    (
        _is_unparseable,
        "The uploaded file could not be read as valid CSV. Check the "
        "delimiter and formatting, then re-upload.",
    ),
    (
        _is_single_class,
        "The target column has only one distinct value, so there is nothing "
        "to predict. Choose a target column with at least two different outcomes.",
    ),
    (
        _is_too_few,
        "The dataset has too few examples to train reliably — either too few "
        "rows overall, or too few examples of some target value (cross-"
        "validation needs several of each). Add more rows and try again.",
    ),
    (
        _is_no_rows,
        "The dataset has no usable rows after cleaning (all rows were empty "
        "or invalid). Check for missing values and re-upload.",
    ),
    (
        _is_non_numeric,
        "A column expected to be numeric contains non-numeric text. Clean "
        "those columns and try again.",
    ),
    (
        _is_undetermined_task,
        "Could not determine a prediction task from the target column — it "
        "may have too few or too uniform values. Pick a different target "
        "and try again.",
    ),
)


def user_safe_failure_reason(exc: BaseException) -> str:
    """A plain, non-sensitive, actionable reason for a failed job (#518)."""
    # Plan wall-clock limit: already a controlled, user-facing message (#500).
    if type(exc).__name__ == "TrainingWallClockExceeded":
        return str(exc)
    low = str(exc).lower()
    return next((message for matches, message in _RULES if matches(exc, low)), _GENERIC)
