"""#542: the transformation engine keeps a DataFrame across steps instead of
serializing the whole frame to list-of-dicts on every step (memory was rows×cols×steps,
and each round-trip discarded dtypes/vectorization).
"""

import pandas as pd

from app.models.transformation import TransformationType
from app.services.transformation_engine.transformation_engine import (
    TransformationEngine,
)


def _frame(n=1000):
    return pd.DataFrame({"a": list(range(n)) + [0], "b": ["x "] * (n + 1)})


def test_frame_path_returns_a_dataframe_and_does_not_serialize():
    eng = TransformationEngine()
    frame, result = eng.apply_transformation_frame(
        _frame(), TransformationType.TRIM_WHITESPACE, {}
    )
    assert result.success is True
    assert isinstance(frame, pd.DataFrame)
    # The frame path must NOT materialize the whole frame as list-of-dicts (#542).
    assert result.transformed_data is None


def test_wrapper_still_returns_records_for_backward_compat():
    eng = TransformationEngine()
    result = eng.apply_transformation(_frame(3), TransformationType.TRIM_WHITESPACE, {})
    assert result.success is True
    assert isinstance(result.transformed_data, list)
    assert result.transformed_data and isinstance(result.transformed_data[0], dict)


def test_multistep_chain_preserves_behavior_and_dtypes():
    """Chaining steps on the DataFrame gives the same result as applying them in
    sequence — and the numeric dtype survives (a per-step list-of-dicts round-trip can
    silently re-infer/lose it)."""
    eng = TransformationEngine()
    df = _frame(500)  # has a duplicate row (the trailing 0/"x ")
    frame1, r1 = eng.apply_transformation_frame(df, TransformationType.TRIM_WHITESPACE, {})
    assert r1.success and frame1 is not None
    frame2, r2 = eng.apply_transformation_frame(
        frame1, TransformationType.REMOVE_DUPLICATES, {}
    )
    assert r2.success and frame2 is not None

    # Whitespace trimmed, duplicates removed, and 'a' is still an integer dtype.
    assert (frame2["b"] == "x").all()
    assert pd.api.types.is_integer_dtype(frame2["a"])
    assert len(frame2) < len(df)  # the duplicate row was dropped


def test_frame_path_failure_returns_none_frame():
    eng = TransformationEngine()
    frame, result = eng.apply_transformation_frame(
        pd.DataFrame(), TransformationType.TRIM_WHITESPACE, {}
    )
    assert frame is None and result.success is False
