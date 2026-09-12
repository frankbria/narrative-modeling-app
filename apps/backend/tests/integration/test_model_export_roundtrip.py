"""#468 AC5: a model saved for real is exported as a Docker ZIP whose artifacts load and
predict. Real S3 (LocalStack), real `load_model` (HMAC-verified), the real route."""
import os
import pickle
import zipfile
from io import BytesIO

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier

from app.services.model_storage import ModelStorageService
from app.services.model_training.automl_engine import ModelCandidate
from app.services.model_training.feature_engineer import (
    FeatureEngineer,
    FeatureEngineeringConfig,
)
from tests.conftest import require_service

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _frame() -> pd.DataFrame:
    rng = np.random.RandomState(0)
    return pd.DataFrame({"age": rng.randint(20, 70, 60), "tenure": rng.randint(1, 120, 60),
                         "churned": rng.choice([0, 1], 60)})


async def test_docker_export_of_a_real_model_ships_working_artifacts(
    async_authorized_client, setup_database, s3_client, test_s3_bucket, monkeypatch
):
    if s3_client is None or test_s3_bucket is None:
        require_service("LocalStack S3 not available")
    monkeypatch.setenv("AWS_ENDPOINT_URL", os.getenv("S3_ENDPOINT_URL", "http://localhost:4566"))
    monkeypatch.setenv("AWS_BUCKET_NAME", test_s3_bucket)
    monkeypatch.setenv("AWS_S3_BUCKET", test_s3_bucket)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    from app.api.routes import model_export as routes

    storage = ModelStorageService()  # built now, with the LocalStack env in place
    monkeypatch.setattr(routes.export_service, "model_storage", storage)

    df = _frame()
    X, y = df.drop(columns=["churned"]), df["churned"]
    fe = FeatureEngineer(FeatureEngineeringConfig(select_features=False, create_interactions=False))
    result = await fe.fit_transform(X, y, "binary_classification")
    clf = RandomForestClassifier(n_estimators=5, random_state=0).fit(result.X_transformed, y)
    ml_model = await storage.save_model(
        model_candidate=ModelCandidate(name="Random Forest", estimator=clf, hyperparameters={},
                                       training_time=0.1, cv_score=0.8, test_score=0.8),
        feature_engineer=fe, user_id="test_user_123", dataset_id="ds_export",
        model_metadata={"problem_type": "binary_classification", "target_column": "churned",
                        "feature_names": result.feature_names, "n_samples_train": len(df)},
    )

    response = await async_authorized_client.get(f"/api/v1/models/{ml_model.model_id}/export/docker")
    assert response.status_code == 200, response.text  # was: 500 on every format

    with zipfile.ZipFile(BytesIO(response.content)) as zf:
        names = set(zf.namelist())
        copied = {line.split()[1] for line in zf.read("Dockerfile").decode().splitlines() if line.startswith("COPY ")}
        assert copied <= names, f"Dockerfile COPYs {copied - names} the ZIP lacks"
        model = pickle.loads(zf.read("model.pkl"))
        engineer = pickle.loads(zf.read("feature_engineer.pkl"))
    # the container's inference path: transform with the shipped engineer, predict with the shipped model
    import inspect

    transformed = engineer.transform(X.head(3)) if engineer is not None else X.head(3)
    if inspect.isawaitable(transformed):  # the app's FeatureEngineer.transform is async
        transformed = await transformed
    assert len(model.predict(transformed)) == 3
