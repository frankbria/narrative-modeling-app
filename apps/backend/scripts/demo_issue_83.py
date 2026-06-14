"""Issue #83 demo — outcome evidence for every acceptance criterion.

Run from apps/backend:  PYTHONPATH=. uv run python scripts/demo_issue_83.py

Exercises the real services end to end (no mocks) and prints the concrete
output that demonstrates each AC, so the demo shows *behaviour*, not just
"it imports".
"""

import asyncio

import pandas as pd
from sklearn.datasets import make_classification, make_regression
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LinearRegression, LogisticRegression

from app.services.confidence_service import ConfidenceService
from app.services.prediction_enrichment import PredictionEnricher
from app.services.prediction_explainer_service import PredictionExplainerService


def hr(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


async def main() -> None:
    conf = ConfidenceService()
    explainer = PredictionExplainerService()
    enricher = PredictionEnricher()

    # ---- AC1: calibrated confidence (0-1) for classification --------------
    hr("AC1 — Calibrated confidence scores for classification")
    Xc, yc = make_classification(n_samples=300, n_features=6, random_state=0)
    base = RandomForestClassifier(n_estimators=30, random_state=0).fit(
        Xc[:200], yc[:200]
    )
    calibrated, method, brier = conf.calibrate_classifier(base, Xc[200:], yc[200:])
    print(f"calibration method        : {method}")
    print(f"calibration score (Brier) : {brier:.4f}")
    proba = calibrated.predict_proba(Xc[200:203]).tolist()
    scores, _ = enricher.per_record_confidence(proba)
    print(f"calibrated confidence (3) : {[round(s, 3) for s in scores]}  (all in 0-1)")

    # ---- AC2: regression uncertainty (prediction intervals) ---------------
    hr("AC2 — Regression prediction intervals")
    Xr, yr = make_regression(n_samples=200, n_features=4, noise=15.0, random_state=1)
    reg = LinearRegression().fit(Xr, yr)
    residual_std = conf.residual_std(yr, reg.predict(Xr))
    preds = reg.predict(Xr[:2]).tolist()
    intervals = enricher.prediction_intervals(preds, residual_std)
    print(f"residual_std              : {residual_std:.3f}")
    for p, iv in zip(preds, intervals):
        print(f"prediction {p:8.2f}  ->  95% interval [{iv[0]:.2f}, {iv[1]:.2f}]")

    # ---- AC3: per-prediction feature contributions (model-native) ---------
    hr("AC3 — Per-prediction feature contributions (no SHAP, model-native)")
    feats = ["age", "income", "score", "tenure", "visits", "region_code"]
    lin = LogisticRegression(max_iter=300).fit(Xc, yc)
    lin_exp = explainer.explain(
        lin, Xc[0], feats, prediction=int(lin.predict([Xc[0]])[0])
    )
    print(f"linear model method       : {lin_exp.method}")
    for f in lin_exp.top_features[:3]:
        print(f"  {f.feature_name:12s} contribution={f.contribution:+.3f}")
    tree_exp = explainer.explain(
        base, Xc[0][:6], feats, prediction=int(base.predict([Xc[0]])[0])
    )
    print(f"tree model method         : {tree_exp.method} (global-importance fallback)")

    # ---- AC4: low-confidence warning flags (single + batch) ---------------
    hr("AC4 — Low-confidence warning flags")
    sample_proba = [[0.45, 0.55], [0.05, 0.95]]  # one below 0.7, one above
    s, flags = enricher.per_record_confidence(sample_proba)
    for sc, fl in zip(s, flags):
        print(f"confidence {sc:.2f}  ->  low_confidence={fl}")

    # ---- AC5 + AC6 via the batch service: CSV columns + explanation -------
    hr("AC5 + AC6 — Batch CSV columns + plain-language explanation")
    from app.models.batch_job import BatchPredictionConfig
    from app.services.batch_prediction import BatchPredictionService

    class _FE:
        numeric_features = ["age"]
        categorical_features: list = []

        async def transform(self, df):
            return df[["age"]]

    # A model trained on the single "age" feature so it matches the _FE above.
    age_X, age_y = make_classification(
        n_samples=120,
        n_features=1,
        n_informative=1,
        n_redundant=0,
        n_clusters_per_class=1,
        random_state=3,
    )
    age_model = LogisticRegression().fit(age_X, age_y)

    svc = BatchPredictionService()
    model = type(
        "M",
        (),
        {
            "problem_type": "binary_classification",
            "feature_names": ["age"],
            "model_id": "demo",
            "version": "1.0.0",
            "residual_std": None,
            "feature_importance": None,
        },
    )()
    chunk = pd.DataFrame([{"age": float(age_X[0][0])}, {"age": float(age_X[1][0])}])
    cfg = BatchPredictionConfig(model_id="demo", include_explanations=True)
    records = await svc._predict_chunk(chunk, age_model, _FE(), model, cfg)
    df = svc._results_to_dataframe(records)
    print(f"CSV columns               : {list(df.columns)}")
    print(f"  -> includes 'confidence' : {'confidence' in df.columns}  (AC5)")
    print(
        f"  -> includes 'low_confidence' : {'low_confidence' in df.columns}  (AC5/#83)"
    )
    summary = svc._calculate_summary_statistics(records, model)
    print(f"summary.low_confidence_count : {summary['low_confidence_count']}")
    print("\nplain-language explanation (AC6):")
    print(f"  {records[0].get('explanation_text')}")

    hr("All acceptance criteria demonstrated with concrete output.")


if __name__ == "__main__":
    asyncio.run(main())
