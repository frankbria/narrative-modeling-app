"""Tests for the model export service (#468).

Written against the REAL `ModelStorageService.load_model(model_id, user_id)` signature and
its `(model, feature_engineer)` tuple return. The previous suite mocked `load_model` with a
one-argument, dict-returning shape the service never had — which is how a call that 500'd
on every export format stayed green — and one test patched the very method under test.
The trained model and feature engineer here are real scikit-learn objects, because the
Docker export pickles them into the ZIP.
"""
import pickle
import re
import zipfile
from io import BytesIO
from unittest.mock import AsyncMock, Mock, patch

import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from app.services.exceptions import NotFoundError
from app.services.model_export import ExportFormatUnavailable, ModelExportService
from app.services.model_storage import ModelStorageService

USER = "user123"
MODEL_ID = "test_model_123"


@pytest.fixture
def mock_model():
    """The MLModel document (metadata only)."""
    model = Mock()
    model.model_id = MODEL_ID
    model.name = "Test Model"
    model.version = "v1.0"
    model.algorithm = "logistic_regression"
    model.problem_type = "binary_classification"
    model.feature_names = ["feature1", "feature2", "feature3"]
    model.target_column = "target"
    model.created_at.isoformat.return_value = "2024-01-01T12:00:00Z"
    model.cv_score = 0.85
    model.test_score = 0.83
    model.n_features = 3
    model.model_path = f"s3://test-bucket/models/{USER}/{MODEL_ID}/model.pkl"
    return model


@pytest.fixture
def trained_model():
    rng = np.random.RandomState(0)
    return LogisticRegression().fit(rng.randn(20, 3), rng.choice([0, 1], 20))


@pytest.fixture
def feature_engineer():
    return StandardScaler().fit(np.random.RandomState(1).randn(20, 3))


@pytest.fixture
def export_service(trained_model, feature_engineer):
    """Export service whose storage returns the real tuple shape."""
    service = ModelExportService()
    service.model_storage = Mock(spec=ModelStorageService)
    service.model_storage.load_model = AsyncMock(return_value=(trained_model, feature_engineer))
    service.s3_service = Mock()
    return service


def _found(mock_model):
    return patch("app.services.model_export.MLModel.find_one", new=AsyncMock(return_value=mock_model))


def _missing():
    return patch("app.services.model_export.MLModel.find_one", new=AsyncMock(return_value=None))


class TestLoadOwned:
    """AC1/AC2: the tenant-scoped load, called with (model_id, user_id) and unpacked as a tuple."""

    @pytest.mark.asyncio
    async def test_load_model_gets_model_id_and_the_caller(self, export_service, mock_model):
        with _found(mock_model):
            await export_service.export_python_code(MODEL_ID, USER)
        export_service.model_storage.load_model.assert_awaited_once_with(MODEL_ID, USER)

    @pytest.mark.asyncio
    async def test_a_model_the_caller_does_not_own_is_not_found(self, export_service):
        with _missing():
            with pytest.raises(NotFoundError):
                await export_service.export_python_code(MODEL_ID, "someone-else")
        export_service.model_storage.load_model.assert_not_awaited()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method", ["export_python_code", "export_docker_container"])
    async def test_every_format_refuses_a_missing_model(self, export_service, method):
        with _missing():
            with pytest.raises(NotFoundError):
                await getattr(export_service, method)(MODEL_ID, USER)


class TestPythonExport:
    @pytest.mark.asyncio
    async def test_generates_inference_code_for_the_real_objects(self, export_service, mock_model):
        with _found(mock_model):
            code, filename = await export_service.export_python_code(MODEL_ID, USER, include_preprocessing=True)
        assert "class ModelInference:" in code
        assert "LogisticRegression" in code
        assert "StandardScaler" in code
        for feature in mock_model.feature_names:
            assert feature in code
        assert filename == "Test Model_v1.0_inference.py"

    @pytest.mark.asyncio
    async def test_include_preprocessing_false_leaves_the_engineer_out(self, export_service, mock_model):
        """claude-review: the flag was accepted and ignored."""
        with _found(mock_model):
            code, _ = await export_service.export_python_code(MODEL_ID, USER, include_preprocessing=False)
        # the engineer's class is not imported; the runtime path that loads an optional
        # feature_engineer.pkl stays in the template (it is a no-op when the file holds None)
        assert "import StandardScaler" not in code

    @pytest.mark.asyncio
    async def test_without_a_feature_engineer(self, export_service, mock_model, trained_model):
        export_service.model_storage.load_model = AsyncMock(return_value=(trained_model, None))
        with _found(mock_model):
            code, _ = await export_service.export_python_code(MODEL_ID, USER, include_preprocessing=False)
        assert "class ModelInference:" in code
        assert "StandardScaler" not in code


class TestDockerExport:
    """AC5: the ZIP carries every artifact its own Dockerfile COPYs, and they unpickle."""

    @pytest.mark.asyncio
    async def test_zip_contains_the_artifacts_the_dockerfile_copies(
        self, export_service, mock_model, trained_model
    ):
        with _found(mock_model):
            zip_bytes, filename = await export_service.export_docker_container(MODEL_ID, USER)

        assert filename == "Test_Model_v1.0_docker.zip"
        with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
            names = set(zf.namelist())
            dockerfile = zf.read("Dockerfile").decode()
            copied = {line.split()[1] for line in dockerfile.splitlines() if line.startswith("COPY ")}
            assert copied <= names, f"Dockerfile COPYs {copied - names} that the ZIP does not contain"
            assert {"model.pkl", "feature_engineer.pkl", "inference.py", "app.py", "requirements.txt", "README.md"} <= names

            restored = pickle.loads(zf.read("model.pkl"))
            assert restored.predict(np.zeros((1, 3))).shape == (1,)
            assert isinstance(pickle.loads(zf.read("feature_engineer.pkl")), StandardScaler)

            requirements = zf.read("requirements.txt").decode()
            import sklearn

            assert f"scikit-learn=={sklearn.__version__}" in requirements, "pins must match the pickling versions"
            assert f"numpy=={np.__version__}" in requirements
            assert "Test Model" in zf.read("README.md").decode()
            import sys

            assert f"FROM python:{sys.version_info.major}.{sys.version_info.minor}-slim" in dockerfile
            assert "class ModelInference:" in zf.read("inference.py").decode()

    @pytest.mark.asyncio
    async def test_generated_api_predicts_off_the_event_loop(self, export_service, mock_model):
        """codex: inference.py may asyncio.run() an awaitable transform; the generated FastAPI
        handler must therefore be a plain `def` (run in FastAPI's threadpool), not `async def`."""
        with _found(mock_model):
            zip_bytes, _ = await export_service.export_docker_container(MODEL_ID, USER)
        with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
            api = zf.read("app.py").decode()
        assert "def predict(request: PredictionRequest)" in api
        assert "async def predict(" not in api

    @pytest.mark.asyncio
    async def test_no_feature_engineer_ships_none(self, export_service, mock_model, trained_model):
        export_service.model_storage.load_model = AsyncMock(return_value=(trained_model, None))
        with _found(mock_model):
            zip_bytes, _ = await export_service.export_docker_container(MODEL_ID, USER)
        with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
            assert pickle.loads(zf.read("feature_engineer.pkl")) is None  # inference.py treats None as "no preprocessing"

    @pytest.mark.asyncio
    async def test_loads_the_model_once(self, export_service, mock_model):
        with _found(mock_model):
            await export_service.export_docker_container(MODEL_ID, USER)
        export_service.model_storage.load_model.assert_awaited_once_with(MODEL_ID, USER)


class TestOptionalFormats:
    """AC4: a converter that is not installed is a clear 'unavailable', never a 500."""

    @pytest.mark.asyncio
    @patch("app.services.model_export.ONNX_AVAILABLE", False)
    async def test_onnx_unavailable(self, export_service, mock_model):
        with _found(mock_model):
            with pytest.raises(ExportFormatUnavailable, match="export"):
                await export_service.export_model_onnx(MODEL_ID, USER)
        export_service.model_storage.load_model.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_pmml_unavailable(self, export_service, mock_model):
        real_import = __import__

        def no_pmml(name, *args, **kwargs):
            if name.startswith("sklearn2pmml"):
                raise ImportError("No module named 'sklearn2pmml'")
            return real_import(name, *args, **kwargs)

        with _found(mock_model), patch("builtins.__import__", side_effect=no_pmml):
            with pytest.raises(ExportFormatUnavailable, match="Java"):
                await export_service.export_model_pmml(MODEL_ID, USER)

    @pytest.mark.asyncio
    async def test_pmml_without_a_java_runtime_is_unavailable(self, export_service, mock_model):
        """codex: the package can be importable while the JRE it shells out to is missing."""
        import sys
        import types

        fake = types.ModuleType("sklearn2pmml")
        fake.sklearn2pmml = lambda *a, **k: None  # type: ignore[attr-defined]
        fake_pipeline = types.ModuleType("sklearn2pmml.pipeline")
        fake_pipeline.PMMLPipeline = object  # type: ignore[attr-defined]
        with _found(mock_model), patch.dict(sys.modules, {"sklearn2pmml": fake, "sklearn2pmml.pipeline": fake_pipeline}), \
             patch("app.services.model_export.shutil.which", return_value=None):
            with pytest.raises(ExportFormatUnavailable, match="Java runtime"):
                await export_service.export_model_pmml(MODEL_ID, USER)
        export_service.model_storage.load_model.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_onnx_export_when_installed(self, export_service, mock_model, trained_model):
        """Runs only where the `export` dependency group is installed."""
        pytest.importorskip("skl2onnx")
        export_service.model_storage.load_model = AsyncMock(return_value=(trained_model, None))
        with _found(mock_model), patch("app.services.model_export.ONNX_AVAILABLE", True):
            onnx_bytes, filename = await export_service.export_model_onnx(MODEL_ID, USER)
        assert filename.endswith(".onnx") and len(onnx_bytes) > 100

    @pytest.mark.asyncio
    async def test_pmml_is_advertised_only_with_a_java_runtime(self, export_service):
        """codex: the probe imported the package and ignored the JRE the export needs."""
        import sys
        import types

        fake = types.ModuleType("sklearn2pmml")
        with patch.dict(sys.modules, {"sklearn2pmml": fake}), \
             patch("app.services.model_export.shutil.which", return_value=None):
            formats = {f["name"]: f for f in await export_service.get_export_formats()}
        assert formats["PMML"]["available"] is False

    @pytest.mark.asyncio
    async def test_formats_report_availability(self, export_service):
        formats = {f["name"]: f for f in await export_service.get_export_formats()}
        assert formats["Python Code"]["available"] is True
        assert formats["Docker Container"]["available"] is True
        assert isinstance(formats["ONNX"]["available"], bool)
        assert isinstance(formats["PMML"]["available"], bool)


class TestGeneratedCode:
    def test_structure(self, export_service, mock_model, trained_model):
        code = export_service._generate_python_code(
            model=mock_model, trained_model=trained_model, feature_engineer=None, include_preprocessing=True
        )
        assert re.search(r"from sklearn\.linear_model[\w.]* import LogisticRegression", code)
        for needle in ("import pandas as pd", "import numpy as np", "import pickle", "class ModelInference:",
                       "def predict(self", "def predict_single(self", "def get_feature_importance(self",
                       "def validate_input(self", 'if __name__ == "__main__":', "ModelInference("):
            assert needle in code, needle
        for feature in mock_model.feature_names:
            assert feature in code
        for meta in (mock_model.name, mock_model.version, mock_model.algorithm, mock_model.target_column):
            assert meta in code

    def test_with_feature_engineer(self, export_service, mock_model, trained_model, feature_engineer):
        code = export_service._generate_python_code(
            model=mock_model, trained_model=trained_model, feature_engineer=feature_engineer,
            include_preprocessing=True,
        )
        assert re.search(r"from sklearn\.preprocessing[\w.]* import StandardScaler", code)
        assert "feature_engineer.transform" in code
