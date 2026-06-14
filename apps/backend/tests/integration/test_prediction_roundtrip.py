"""
Integration round-trip for issue #82: train -> predict single -> predict batch.

Persists a real trained model + fitted feature pipeline to S3 (LocalStack),
then exercises the live HTTP predict path and the batch prediction service end
to end against real MongoDB. Skips cleanly when LocalStack is unavailable, in
line with the rest of the S3-backed integration suite.
"""

import io

import pandas as pd
import pytest

from app.models.batch_job import JobStatus
from app.services.model_training.automl_engine import ModelCandidate
from app.services.model_training.feature_engineer import (
    FeatureEngineer,
    FeatureEngineeringConfig,
)


def _training_frame() -> pd.DataFrame:
    rows = []
    for i in range(60):
        churn = i % 2
        rows.append(
            {
                "age": 20 + i,
                "income": 30000 + i * 700,
                "gender": "m" if i % 3 else "f",
                "churned": churn,
            }
        )
    return pd.DataFrame(rows)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_train_predict_single_and_batch_roundtrip(
    async_authorized_client, setup_database, s3_client, test_s3_bucket, monkeypatch
):
    if s3_client is None or test_s3_bucket is None:
        pytest.skip("LocalStack S3 not available")

    import os

    endpoint = os.getenv("S3_ENDPOINT_URL", "http://localhost:4566")
    monkeypatch.setenv("AWS_ENDPOINT_URL", endpoint)
    monkeypatch.setenv("AWS_BUCKET_NAME", test_s3_bucket)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("AWS_REGION", "us-east-1")

    # Fresh services so they read the patched env (bucket + endpoint).
    from app.services.batch_prediction import BatchPredictionService
    from app.services.model_storage import ModelStorageService
    from sklearn.ensemble import RandomForestClassifier

    user_id = "test_user_123"
    df = _training_frame()
    X = df.drop(columns=["churned"])
    y = df["churned"]

    # Train: fit the feature pipeline, then a model on the engineered features.
    fe = FeatureEngineer(
        FeatureEngineeringConfig(select_features=False, create_interactions=False)
    )
    result = await fe.fit_transform(X, y, "binary_classification")
    clf = RandomForestClassifier(n_estimators=10, random_state=0)
    clf.fit(result.X_transformed, y)

    candidate = ModelCandidate(
        name="Random Forest",
        estimator=clf,
        hyperparameters={},
        training_time=0.1,
        cv_score=0.8,
        test_score=0.8,
    )
    ml_model = await ModelStorageService().save_model(
        model_candidate=candidate,
        feature_engineer=fe,
        user_id=user_id,
        dataset_id="ds_roundtrip",
        model_metadata={
            "problem_type": "binary_classification",
            "target_column": "churned",
            "feature_names": result.feature_names,
            "n_samples_train": len(df),
        },
    )
    model_id = ml_model.model_id

    # 1) Feature schema for the form lists the raw input columns.
    feats = await async_authorized_client.get(f"/api/v1/ml/{model_id}/features")
    assert feats.status_code == 200
    names = {f["name"] for f in feats.json()["features"]}
    assert {"age", "income", "gender"}.issubset(names)

    # 2) Single prediction via the live endpoint, reusing the fitted pipeline.
    record = {"age": 33, "income": 52000, "gender": "m"}
    single = await async_authorized_client.post(
        f"/api/v1/ml/{model_id}/predict",
        json={"data": [record], "include_probabilities": True},
    )
    assert single.status_code == 200, single.text
    body = single.json()
    assert len(body["predictions"]) == 1
    assert body["confidence"] is not None and len(body["confidence"]) == 1
    assert body["class_labels"] == ["0", "1"]

    # 3) Batch prediction round-trip through the service + S3.
    batch_df = pd.DataFrame([record, {"age": 60, "income": 80000, "gender": "f"}])
    svc = BatchPredictionService()
    job = await svc.create_batch_prediction_job(
        user_id=user_id,
        model_id=model_id,
        input_data=batch_df,
        auto_start=False,
    )
    await svc._process_batch_job(job)

    refreshed = await svc.get_job_status(job.job_id, user_id)
    assert refreshed.status == JobStatus.COMPLETED, refreshed.error_message
    assert refreshed.results["total_predictions"] == 2
    assert refreshed.results["success_count"] == 2
    assert "prediction_distribution" in refreshed.results

    content = await svc.download_results(job.job_id, user_id)
    assert content is not None
    out = pd.read_csv(io.BytesIO(content))
    assert len(out) == 2
    assert "prediction" in out.columns
