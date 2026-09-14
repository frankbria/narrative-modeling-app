"""#499: GET /transformations/available must advertise only what the engine can
execute. Previously it hand-listed ~22 types while the engine implemented 4, so ~18
menu entries failed or silently did nothing.

These lock the durable fix: the advertised list is derived from the engine registry,
every advertised type executes against a sample dataset, and a non-executable type
fails gracefully (not a 500) so an old saved recipe referencing one is handled.
"""

import pandas as pd
import pytest

from app.models.transformation import TransformationType
from app.services.transformation_engine.transformation_engine import (
    TransformationEngine,
    available_transformations,
)


def _sample() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "a": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            "b": ["x ", "y", "z ", "p", "q", "r", "s", "t", "u", "v"],
            "c": [1.0, 2.0, None, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0],  # one missing
        }
    )


# Minimal valid params to execute each advertised type against ``_sample``.
_PARAMS: dict[str, dict] = {
    "remove_duplicates": {},
    "trim_whitespace": {},
    "drop_missing": {},  # one missing row -> 10% loss, under the safety threshold
    "fill_missing": {"value": "0"},
}


def test_advertised_list_is_exactly_the_executable_registry():
    advertised = {m["type"] for m in available_transformations()}
    executable = {t.value for t in TransformationEngine.TRANSFORMATION_CLASSES}
    assert advertised == executable, (
        f"advertised {advertised} must equal executable {executable} — the list must be "
        "derived from the engine registry so it cannot drift (#499)"
    )


def test_every_advertised_type_carries_display_metadata():
    for m in available_transformations():
        assert m["label"] and m["category"] and m["description"], m
        assert isinstance(m["parameters_schema"], dict)
        assert isinstance(m["requires_columns"], bool)


def test_params_cover_every_advertised_type():
    # Guards the test itself: if a new executable type is added, this list must grow.
    assert set(_PARAMS) == {m["type"] for m in available_transformations()}


@pytest.mark.parametrize("ttype", sorted(_PARAMS))
def test_every_advertised_type_executes(ttype):
    engine = TransformationEngine()
    result = engine.apply_transformation(
        df=_sample(),
        transformation_type=TransformationType(ttype),
        parameters=_PARAMS[ttype],
    )
    assert result.success, f"advertised type {ttype!r} failed to execute: {result.error}"
    assert result.transformed_data is not None


def test_non_executable_type_fails_gracefully_not_500():
    """An old saved recipe referencing a type the engine never implemented (e.g. the
    one-hot 'encode') must return success=False, not raise (#499 AC4)."""
    non_exec = next(
        t for t in TransformationType if t not in TransformationEngine.TRANSFORMATION_CLASSES
    )
    engine = TransformationEngine()
    result = engine.apply_transformation(
        df=_sample(), transformation_type=non_exec, parameters={}
    )
    assert result.success is False
    assert result.error  # a message, not an exception
