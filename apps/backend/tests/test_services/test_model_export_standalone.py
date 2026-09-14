"""#632: the Docker export must load and predict in a container that has no `app`
package — a model trained WITH feature engineering used to raise ModuleNotFoundError
on load because the pickled preprocessing was the platform's own FeatureEngineer.

These tests do not need Docker or S3: `_load_owned` is stubbed. AC3 (clean-env load
+ predict) is exercised by extracting the produced ZIP and running its inference.py in
a subprocess whose sys.path does NOT include the repo, so `import app` fails.
"""

import pickle
import subprocess
import sys
import textwrap
import zipfile
from io import BytesIO
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier

from app.services.model_export import ModelExportService
from app.services.model_export_runtime import feature_engineer_state
from app.services.model_training.feature_engineer import (
    FeatureEngineer,
    FeatureEngineeringConfig,
)

pytestmark = pytest.mark.asyncio


def _frame() -> pd.DataFrame:
    rng = np.random.RandomState(0)
    return pd.DataFrame(
        {
            "age": rng.randint(20, 70, 80),
            "tenure": rng.randint(1, 120, 80),
            "plan": rng.choice(["basic", "pro", "premium"], 80),  # categorical → encoded
            "churned": rng.choice([0, 1], 80),
        }
    )


async def _trained_model_with_fe():
    df = _frame()
    X, y = df.drop(columns=["churned"]), df["churned"]
    fe = FeatureEngineer(
        FeatureEngineeringConfig(select_features=False, create_interactions=False)
    )
    result = await fe.fit_transform(X, y, "binary_classification")
    clf = RandomForestClassifier(n_estimators=5, random_state=0).fit(result.X_transformed, y)
    model = SimpleNamespace(
        model_id="m-632",
        name="Churn Model",
        version="1.0.0",
        algorithm="RandomForestClassifier",
        problem_type="binary_classification",
        feature_names=list(X.columns),
        target_column="churned",
        created_at=pd.Timestamp("2026-01-01", tz="UTC").to_pydatetime(),
        cv_score=0.8,
        test_score=0.8,
    )
    return model, clf, fe, X


async def test_shipped_state_carries_no_app_class_reference():
    """The pickled preprocessing must reference no `app.*` class — that is exactly
    what made the container fail to load (#632)."""
    _, _, fe, _ = await _trained_model_with_fe()
    state = feature_engineer_state(fe)
    assert state is not None and state["transformers"]  # this model HAS preprocessing
    blob = pickle.dumps(state)
    assert b"app.services.model_training.feature_engineer" not in blob
    assert b"FeatureEngineer" not in blob  # not the class, only stock sklearn + data


async def test_empty_engineer_ships_none():
    fe = FeatureEngineer()  # never fitted → no transformers
    assert feature_engineer_state(fe) is None
    assert feature_engineer_state(None) is None


async def test_docker_zip_is_self_contained_with_inlined_preprocessing(monkeypatch):
    model, clf, fe, _ = await _trained_model_with_fe()
    svc = ModelExportService()

    async def fake_load(model_id, user_id):
        return model, clf, fe

    monkeypatch.setattr(svc, "_load_owned", fake_load)
    zip_bytes, filename = await svc.export_docker_container("m-632", "u1")
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        names = set(zf.namelist())
        assert {"feature_engineer.pkl", "inference.py"} <= names
        # every COPY in the Dockerfile is present in the ZIP
        copied = {
            line.split()[1]
            for line in zf.read("Dockerfile").decode().splitlines()
            if line.startswith("COPY ")
        }
        assert copied <= names, f"Dockerfile COPYs {copied - names} the ZIP lacks"
        inference_src = zf.read("inference.py").decode()
        # the preprocessing class is INLINED (no companion module to import), and
        # the inference path is synchronous — no asyncio.run of transform (AC2)
        assert "asyncio" not in inference_src
        assert "class StandaloneFeatureEngineer" in inference_src
        assert "load_feature_engineer" in inference_src
        assert "from feature_engineer import" not in inference_src


async def test_clean_environment_load_and_predict(monkeypatch, tmp_path):
    """AC3: unzip in an environment with no `app` on sys.path, load both pickles via
    the shipped standalone module, and predict."""
    model, clf, fe, X = await _trained_model_with_fe()
    svc = ModelExportService()

    async def fake_load(model_id, user_id):
        return model, clf, fe

    monkeypatch.setattr(svc, "_load_owned", fake_load)
    zip_bytes, _ = await svc.export_docker_container("m-632", "u1")
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        zf.extractall(tmp_path)

    sample = X.head(3).to_dict(orient="records")
    script = textwrap.dedent(
        f"""
        import sys
        # Prove the container-like env cannot import the platform module the old
        # pickle required (the export ships its own app.py, so `import app` is not
        # the right probe — this is the module that raised ModuleNotFoundError, #632).
        try:
            import app.services.model_training.feature_engineer  # noqa: F401
            print("APP_LEAKED"); sys.exit(2)
        except ModuleNotFoundError:
            pass
        from inference import ModelInference
        inf = ModelInference("model.pkl", "feature_engineer.pkl")
        out = inf.predict({sample!r})
        print(len(out["predictions"]))
        """
    )
    # cwd = the unzipped dir; a clean cwd (no repo root) so `import app` fails.
    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env={"PATH": "/usr/bin:/bin", "PYTHONPATH": ""},
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, f"stdout={proc.stdout}\nstderr={proc.stderr}"
    assert proc.stdout.strip().splitlines()[-1] == "3"


async def test_standalone_transform_matches_the_platform():
    """The container's preprocessing must produce the SAME matrix the platform's
    FeatureEngineer.transform does, or predictions silently diverge. Compares the
    source-of-truth StandaloneFeatureEngineer (inlined into every export) against
    the platform, driven by the shipped state dict."""
    import pickle

    from app.services.model_export_assets._standalone_fe import (
        StandaloneFeatureEngineer,
    )

    _, _, fe, X = await _trained_model_with_fe()
    state = feature_engineer_state(fe)
    # round-trip the state exactly as the export does (pickle → unpickle)
    engineer = StandaloneFeatureEngineer(pickle.loads(pickle.dumps(state)))
    got = engineer.transform(X.head(5))

    expected = await fe.transform(X.head(5))
    pd.testing.assert_frame_equal(
        got.reset_index(drop=True), expected.reset_index(drop=True), check_dtype=False
    )
