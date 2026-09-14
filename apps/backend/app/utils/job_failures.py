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

_GENERIC = (
    "The job failed due to an unexpected error. Quote this job's id to support "
    "and we can investigate."
)


def user_safe_failure_reason(exc: BaseException) -> str:
    """A plain, non-sensitive, actionable reason for a failed job (#518)."""
    name = type(exc).__name__
    low = str(exc).lower()

    def has(*needles: str) -> bool:
        return any(n in low for n in needles)

    # Plan wall-clock limit: already a controlled, user-facing message (#500).
    if name == "TrainingWallClockExceeded":
        return str(exc)

    if isinstance(exc, TimeoutError) or has("timed out", "timeout"):
        return (
            "The job ran longer than the allowed time and was stopped. Try a "
            "smaller dataset or a simpler configuration."
        )

    # Empty / unreadable input.
    if name == "EmptyDataError" or has("no columns to parse", "empty csv"):
        return "The uploaded file appears to be empty. Upload a non-empty CSV and try again."
    if name == "ParserError" or has("error tokenizing", "not valid csv", "could not be read as csv"):
        return (
            "The uploaded file could not be read as valid CSV. Check the "
            "delimiter and formatting, then re-upload."
        )

    # Target column has a single class / value — nothing to predict.
    if has(
        "least populated class",
        "number of classes",
        "at least 2 classes",
        "only one class",
        "needs samples of at least",
        "single value",
        "only one distinct",
    ):
        return (
            "The target column has only one distinct value, so there is nothing "
            "to predict. Choose a target column with at least two different outcomes."
        )

    # Too few rows / examples for cross-validation.
    if has(
        "n_splits",
        "greater than the number of members",
        "cannot have number of splits",
        "too few",
    ) or (has("minimum", "not enough") and has("row", "sample")):
        return (
            "The dataset has too few rows to train reliably (cross-validation "
            "needs more examples). Add more rows and try again."
        )

    # No usable rows after cleaning.
    if has("found array with 0 sample", "0 sample(s)", "no usable rows") or has("input contains nan"):
        return (
            "The dataset has no usable rows after cleaning (all rows were empty "
            "or invalid). Check for missing values and re-upload."
        )

    # A numeric column carried non-numeric text.
    if has("could not convert string to float", "invalid literal for"):
        return (
            "A column expected to be numeric contains non-numeric text. Clean "
            "those columns and try again."
        )

    # Could not determine a prediction task (AutoML 'unknown' / divide on a tiny
    # sample — the 6-row case the project notes record).
    if isinstance(exc, ZeroDivisionError) or has("could not determine") or (
        "unknown" in low and has("problem", "task", "type")
    ):
        return (
            "Could not determine a prediction task from the target column — it "
            "may have too few or too uniform values. Pick a different target "
            "and try again."
        )

    return _GENERIC
