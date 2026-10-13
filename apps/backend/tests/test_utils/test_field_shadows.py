"""#762: five models have a field called `schema` or `count` on purpose, and say so.

Pydantic prints a notice for each at import. They opened every container log and were
once the entire body of an operations alert.
"""
import os
import subprocess
import sys
import warnings
from pathlib import Path

import pytest
from pydantic import create_model

from app.utils.field_shadows import expect_field_shadow

BACKEND = Path(__file__).resolve().parents[2]


def test_the_app_imports_with_no_warning_from_its_own_models():
    """A fresh interpreter in which a field-shadow notice is an error. Only those:
    `-W error:Field name` matches messages that start that way, so a warning from
    some dependency cannot fail this."""
    result = subprocess.run(
        [sys.executable, "-W", "error:Field name:UserWarning", "-c", "import app.main"],
        cwd=BACKEND,
        env={**os.environ, "PYTHONPATH": "."},
        capture_output=True,
        text=True,
        timeout=180,
    )

    assert result.returncode == 0, result.stderr[-1500:]
    assert "shadows an attribute" not in result.stderr


def test_only_the_field_and_model_named_are_expected():
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        expect_field_shadow("schema", "Declared")

        create_model("Declared", schema=(dict | None, None))  # expected: no warning

        with pytest.raises(UserWarning, match='Field name "schema" in "Undeclared"'):
            create_model("Undeclared", schema=(dict | None, None))
        with pytest.raises(UserWarning, match='Field name "copy" in "Declared"'):
            create_model("Declared", copy=(str | None, None))
