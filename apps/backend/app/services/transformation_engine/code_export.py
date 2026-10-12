"""A pipeline as a pandas script (#860).

The Prepare stage's Export Code button, and a saved recipe's export, hand the user a
script that should do to their data what the app did. Each transformation class writes
its own statements (``BaseTransformation.code``) beside the ``apply`` they mirror, and
``tests/test_services/test_pipeline_code_export.py`` runs every generated script against
the engine, so the two cannot drift apart unnoticed.
"""

from typing import Any

from app.services.transformation_engine.transformation_engine import (
    BaseTransformation,
    TransformationEngine,
    TransformationType,
)

_HEADER = '''"""A data preparation pipeline, exported as code.

Run it on a CSV file:

    python transformation_pipeline.py input.csv output.csv

or import `transform` and call it on a pandas DataFrame.
"""
import sys

import pandas as pd


def transform(df: pd.DataFrame) -> pd.DataFrame:
    """Apply the pipeline's steps, in order, to a copy of `df`."""
    df = df.copy()
'''

_FOOTER = '''


if __name__ == "__main__":
    transform(pd.read_csv(sys.argv[1])).to_csv(sys.argv[2], index=False)
'''


def _transformation(number: int, kind: str, parameters: dict[str, Any]) -> BaseTransformation:
    """The step as the engine would run it; a ValueError naming the step if it cannot."""
    try:
        transformation_class = TransformationEngine.TRANSFORMATION_CLASSES[TransformationType(kind)]
    except (ValueError, KeyError):
        raise ValueError(f"Step {number} ({kind}): not a transformation the pipeline can run") from None
    try:
        return transformation_class(parameters)
    except ValueError as invalid:
        raise ValueError(f"Step {number} ({kind}): {invalid}") from None


def pipeline_script(steps: list[tuple[str, dict[str, Any]]]) -> str:
    """A Python module whose ``transform(df)`` applies ``steps`` in order.

    Raises:
        ValueError: a step's type is not one the engine executes, or its parameters are
            not valid for it. The message names the step by number and type.
    """
    body: list[str] = []
    for number, (kind, parameters) in enumerate(steps, start=1):
        transformation = _transformation(number, kind, parameters)
        body += ["", f"    # Step {number}: {transformation.LABEL}"]
        body += [f"    {line}" for line in transformation.code()]
    return _HEADER + "\n".join([*body, "", "    return df"]) + _FOOTER
