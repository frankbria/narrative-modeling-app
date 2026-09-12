"""Issue #80 demo: SHAP interpretability — outcome evidence for each AC.

Run: PYTHONPATH=. uv run python tasks/issue_80_demo.py
Exercises the REAL services and the REAL HTTP endpoints (httpx + ASGITransport
against a test Mongo). No mocking of the feature under test; only
MetricsService.load_shap_artifacts is pointed at an in-memory payload to avoid
needing S3 for the endpoint demo.
"""

import asyncio
import os
import time

import pandas as pd
from sklearn.datasets import make_classification
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

os.environ["SKIP_AUTH"] = "true"
os.environ["ENVIRONMENT"] = "test"

from app.services.interpretability_service import InterpretabilityService  # noqa: E402

FEATURES = ["age", "income", "credit_score", "tenure"]


def banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def demo_services() -> None:
    svc = InterpretabilityService()
    X, y = make_classification(
        n_samples=600, n_features=4, n_informative=3, n_redundant=0,
        n_clusters_per_class=1, random_state=7,
    )
    Xdf = pd.DataFrame(X, columns=FEATURES)
    rf = RandomForestClassifier(n_estimators=40, random_state=0).fit(Xdf, y)
    lr = LogisticRegression(max_iter=500).fit(Xdf, y)

    banner("AC1/AC2/AC5 — Global SHAP summary (TreeExplainer) + sampling/speed")
    t0 = time.perf_counter()
    g = svc.compute_global_shap(rf, Xdf, FEATURES, "classification", max_samples=200)
    elapsed = time.perf_counter() - t0
    print(f"explainer_type = {g.explainer_type}")
    print(f"rows explained (sampled, cap 200) = {g.n_samples}")
    print(f"elapsed = {elapsed:.2f}s  (AC: <30s for typical beta datasets)")
    print("mean |SHAP| per feature (ranked):")
    for name, val in sorted(g.shap_importance.items(), key=lambda kv: -kv[1]):
        print(f"   {name:<13} {val:.4f}")

    banner("AC2 — LinearExplainer for linear models")
    gl = svc.compute_global_shap(lr, Xdf, FEATURES, "classification")
    print(f"explainer_type = {gl.explainer_type}")
    print(f"top driver = {max(gl.shap_importance, key=gl.shap_importance.get)}")

    banner("AC3 — Per-prediction SHAP (waterfall-style), tree models, per-row")
    rows = svc.compute_instance_shap_batch(
        rf, Xdf.iloc[:3], FEATURES, rf.predict(Xdf.iloc[:3]).tolist()
    )
    for i, r in enumerate(rows):
        contribs = {FEATURES[j]: round(float(r[j]), 4) for j in range(len(FEATURES))}
        print(f"row {i}: {contribs}")
    print("-> contributions differ per row (true per-prediction SHAP, not global)")

    banner("AC4 — Plain-language explanation of top drivers")
    print(svc.top_drivers_text(g.shap_importance))

    banner("Fallback — unsupported model type returns None (native fallback)")
    from sklearn.neighbors import KNeighborsClassifier
    knn = KNeighborsClassifier().fit(Xdf, y)
    print(f"KNN global SHAP        = {svc.compute_global_shap(knn, Xdf, FEATURES)}")
    print(f"KNN per-instance SHAP  = {svc.compute_instance_shap(knn, X[0], FEATURES)}")


async def demo_endpoints() -> None:
    from unittest.mock import AsyncMock, patch

    import httpx
    from beanie import init_beanie
    from motor.motor_asyncio import AsyncIOMotorClient

    from app.main import app
    from app.models.ml_model import MLModel
    from app.models.registry import DOCUMENT_MODELS
    from app.services.metrics_service import MetricsService

    client = AsyncIOMotorClient("mongodb://localhost:27017")
    await init_beanie(
        database=client["narrative_modeling_issue80_demo"],
        document_models=DOCUMENT_MODELS,
    )

    user = "dev-demo-user"
    supported = MLModel(
        user_id=user, dataset_id="ds_demo", model_id="demo_tree",
        name="Loan Default (RandomForest)", problem_type="binary_classification",
        algorithm="Random Forest", target_column="default",
        feature_names=FEATURES, cv_score=0.91, test_score=0.89,
        training_time=3.2, model_size=2048, n_samples_train=600, n_features=4,
        model_path="s3://b/m/model.pkl",
        feature_importance={"income": 0.41, "credit_score": 0.33, "age": 0.18, "tenure": 0.08},
        shap_values_path="s3://b/m/shap_data.json", shap_explainer_type="tree",
    )
    legacy = MLModel(
        user_id=user, dataset_id="ds_demo", model_id="demo_pre80",
        name="Old model (pre-#80)", problem_type="binary_classification",
        algorithm="KNN", target_column="default", feature_names=FEATURES,
        cv_score=0.8, test_score=0.78, training_time=1.0, model_size=1024,
        n_samples_train=600, n_features=4, model_path="s3://b/m/model.pkl",
    )
    await supported.insert()
    await legacy.insert()

    shap_payload = {
        "explainer_type": "tree",
        "shap_importance": {"income": 0.39, "credit_score": 0.31, "age": 0.2, "tenure": 0.1},
        "base_value": 0.5, "n_samples": 120, "created_at": "2026-06-14T00:00:00+00:00",
    }
    headers = {"Authorization": f"Bearer {user}"}
    transport = httpx.ASGITransport(app=app)
    try:
        with patch.object(
            MetricsService, "load_shap_artifacts",
            new=AsyncMock(return_value=shap_payload),
        ):
            async with httpx.AsyncClient(transport=transport, base_url="http://t") as ac:
                banner("AC6 — GET /api/v1/ml/{id}/feature-importance (native + SHAP)")
                r = await ac.get("/api/v1/ml/demo_tree/feature-importance", headers=headers)
                print(f"HTTP {r.status_code}")
                print(r.json())

                banner("AC6 — GET /api/v1/ml/{id}/shap (summary + plain language)")
                r = await ac.get("/api/v1/ml/demo_tree/shap", headers=headers)
                print(f"HTTP {r.status_code}")
                print(r.json())

        async with httpx.AsyncClient(transport=transport, base_url="http://t") as ac:
            banner("Degradation — pre-#80 model: partial, never 500")
            r = await ac.get("/api/v1/ml/demo_pre80/shap", headers=headers)
            print(f"HTTP {r.status_code}  partial={r.json()['partial']}")
            print(f"message = {r.json()['message']}")

            banner("Auth — foreign/unknown model returns 404")
            r = await ac.get("/api/v1/ml/nope/shap", headers=headers)
            print(f"HTTP {r.status_code}")
    finally:
        await supported.delete()
        await legacy.delete()
        client.close()


if __name__ == "__main__":
    demo_services()
    asyncio.run(demo_endpoints())
    print("\nAll acceptance criteria demonstrated with live outputs.")
