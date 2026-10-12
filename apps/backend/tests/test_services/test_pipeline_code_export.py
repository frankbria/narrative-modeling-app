"""#860: the exported script does what the pipeline does.

The Prepare stage's Export Code button posted to a route that did not exist. The route
now returns a pandas script, and a script that drifts from the engine is worse than no
script: the user would run it and get different data. So every case here runs the
generated code and compares its result with the engine's own, frame for frame.
"""
import ast

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from app.services.transformation_engine.code_export import pipeline_script
from app.services.transformation_engine.transformation_engine import (
    TransformationEngine,
    TransformationType,
)

pytestmark = pytest.mark.unit


def _frame() -> pd.DataFrame:
    return pd.DataFrame({
        "id": [1, 2, 2, 4, 5, 5],
        "name": [" ann ", "bo", "bo", None, "  dee", "  dee"],
        "city": ["x ", None, None, "y", " z", " z"],
        "score": [1.5, np.nan, np.nan, 4.0, 5.5, 5.5],
        "age": [30, 41, 41, np.nan, 28, 28],
    })


def _exported(steps: list[tuple[str, dict]], frame: pd.DataFrame) -> pd.DataFrame:
    """Run the generated script's `transform` on `frame`, in a namespace of its own."""
    namespace: dict = {"__name__": "exported_pipeline"}
    exec(compile(pipeline_script(steps), "<exported pipeline>", "exec"), namespace)  # noqa: S102
    return namespace["transform"](frame)


def _engine(steps: list[tuple[str, dict]], frame: pd.DataFrame) -> pd.DataFrame:
    engine = TransformationEngine()
    for kind, parameters in steps:
        frame, result = engine.apply_transformation_frame(
            df=frame, transformation_type=TransformationType(kind), parameters=parameters
        )
        assert result.success, result.error
    return frame


CASES = [
    ("remove_duplicates", {}),
    ("remove_duplicates", {"keep": "last"}),
    ("remove_duplicates", {"subset": ["id"], "keep": "first"}),
    ("trim_whitespace", {}),
    ("trim_whitespace", {"columns": ["name"]}),
    ("trim_whitespace", {"columns": ["name", "no_such_column"]}),
    ("drop_missing", {}),
    ("drop_missing", {"how": "all"}),
    ("drop_missing", {"columns": ["score"]}),
    ("drop_missing", {"threshold": 40}),
    ("drop_missing", {"columns": ["name", "city"], "threshold": 100}),
    ("fill_missing", {"value": "unknown", "columns": ["name", "city"]}),
    ("fill_missing", {"value": 0}),
    ("fill_missing", {"method": "mean"}),
    ("fill_missing", {"method": "median", "columns": ["score", "name"]}),
    ("fill_missing", {"method": "mode"}),
    ("fill_missing", {"method": "ffill", "columns": ["city"]}),
    ("fill_missing", {"method": "bfill"}),
    ("fill_missing", {"method": "mode", "columns": ["no_such_column", "age"]}),
]


@pytest.mark.filterwarnings("ignore::FutureWarning")
class TestTheScriptMatchesTheEngine:
    @pytest.mark.parametrize("kind, parameters", CASES, ids=[f"{k} {p}" for k, p in CASES])
    def test_one_step(self, kind, parameters):
        steps = [(kind, parameters)]

        assert_frame_equal(_exported(steps, _frame()), _engine(steps, _frame()))

    def test_a_pipeline_of_every_kind_in_order(self):
        steps = [
            ("trim_whitespace", {}),
            ("fill_missing", {"method": "mean", "columns": ["score", "age"]}),
            ("drop_missing", {"columns": ["name"]}),
            ("remove_duplicates", {"subset": ["id"]}),
        ]

        assert_frame_equal(_exported(steps, _frame()), _engine(steps, _frame()))

    def test_the_callers_frame_is_left_as_it_was(self):
        frame = _frame()

        _exported([("fill_missing", {"value": 0}), ("trim_whitespace", {})], frame)

        assert_frame_equal(frame, _frame())

    def test_every_type_the_engine_executes_can_be_exported(self):
        """A type added to the engine without code export would make Export Code fail for
        any pipeline that uses it."""
        defaults = {"fill_missing": {"method": "mode"}}
        for kind in TransformationEngine.TRANSFORMATION_CLASSES:
            steps = [(kind.value, defaults.get(kind.value, {}))]
            assert_frame_equal(_exported(steps, _frame()), _engine(steps, _frame()))


class TestTheScriptItself:
    def test_it_is_a_python_module_with_a_transform_and_a_command_line(self):
        script = pipeline_script([("trim_whitespace", {"columns": ["name"]}), ("remove_duplicates", {})])

        tree = ast.parse(script)
        assert [n.name for n in tree.body if isinstance(n, ast.FunctionDef)] == ["transform"]
        assert "# Step 1: Trim Whitespace" in script and "# Step 2: Remove Duplicates" in script
        assert 'if __name__ == "__main__":' in script

    def test_an_empty_pipeline_returns_the_data_unchanged(self):
        assert_frame_equal(_exported([], _frame()), _frame())

    def test_a_column_name_cannot_write_code_into_the_script(self):
        """Parameters come from the request. A name is always emitted as a string literal,
        so text that looks like code stays a column name."""
        hostile = "x']); raise SystemExit('injected'); df = (['"
        frame = _frame().rename(columns={"name": hostile})
        steps = [("trim_whitespace", {"columns": [hostile]}), ("fill_missing", {"value": "'\\n\"", "columns": [hostile]})]

        assert_frame_equal(_exported(steps, frame), _engine(steps, frame))

    @pytest.mark.parametrize("steps, said", [
        ([("trim_whitespace", {}), ("fill_missing", {})], "Step 2 (fill_missing): Either 'value' or 'method'"),
        ([("drop_missing", {"how": "some"})], "Step 1 (drop_missing): how must be"),
        ([("one_hot_encode", {})], "Step 1 (one_hot_encode): not a transformation the pipeline can run"),
        ([("no_such_type", {})], "Step 1 (no_such_type): not a transformation the pipeline can run"),
    ])
    def test_a_step_that_cannot_run_is_refused_by_number_and_name(self, steps, said):
        with pytest.raises(ValueError, match=said.replace("(", r"\(").replace(")", r"\)")):
            pipeline_script(steps)
