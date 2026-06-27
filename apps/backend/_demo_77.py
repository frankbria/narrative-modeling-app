import asyncio

import numpy as np  # noqa: F401
import pandas as pd
from sklearn.datasets import make_classification
from sklearn.ensemble import RandomForestClassifier

from app.services.model_training import AutoMLEngine, HyperparameterTuner, TuningConfig

print("=" * 70)
print("ISSUE #77 DEMO - Hyperparameter Tuning")
print("=" * 70)

Xn, yn = make_classification(n_samples=300, n_features=8, n_informative=5, random_state=7)
X = pd.DataFrame(Xn, columns=[f"f{i}" for i in range(8)])
y = pd.Series(yn)
t = HyperparameterTuner()

print("\n[AC1] Three strategies (grid / random / bayesian-optuna):")
for s in ("grid", "random", "bayesian"):
    cfg = TuningConfig(strategy=s, n_trials=12, cv_folds=3, scoring="roc_auc", n_jobs=-1)
    r = t.tune("Random Forest", RandomForestClassifier(random_state=0), X, y, cfg, True)
    print(
        f"  {s:9s}: best={r.best_score:.4f} default={r.default_score:.4f} "
        f"improvement={r.improvement_over_default:+.4f} trials={r.n_trials_completed} "
        f"strategy_used={r.strategy}"
    )

print("\n[AC2] Smart, data-driven, algorithm-specific search spaces:")
sp_small = t.get_search_space("XGBoost", n_samples=300, n_features=8)
sp_big = t.get_search_space("XGBoost", n_samples=80000, n_features=8)
print(f"  XGBoost params: {list(sp_small)}")
print(
    f"  n_estimators high: small-data={sp_small['n_estimators'].high}  "
    f"large-data(shrunk)={sp_big['n_estimators'].high}"
)
print(f"  KNN params (different algorithm): {list(t.get_search_space('K-Nearest Neighbors'))}")

print("\n[AC3] Tuning config (budget / trials / metric / cv folds):")
cfg = TuningConfig(strategy="random", time_budget=120, n_trials=15, cv_folds=4, scoring="f1_weighted")
print(f"  {cfg}")

print("\n[AC4] Parallel trials (n_jobs) + early stopping (optuna MedianPruner):")
cfg = TuningConfig(strategy="bayesian", n_trials=25, cv_folds=3, scoring="roc_auc", n_jobs=-1)
r = t.tune("Random Forest", RandomForestClassifier(random_state=0), X, y, cfg, True)
print(
    f"  n_jobs=-1 (all cores); started 25 trials, {r.n_trials_completed} completed, "
    f"{25 - r.n_trials_completed} pruned early"
)
print(f"  parameter_importance present: {r.parameter_importance is not None}")

print("\n[AC5] Results visualization (param importance, opt history, improvement):")
print(f"  parameter_importance: {dict(list((r.parameter_importance or {}).items())[:3])}")
print(f"  optimization_history[0:2]: {r.optimization_history[:2]}")
print(f"  improvement_over_default: {r.improvement_over_default:+.4f}")

print("\n[AC6] Best params automatically applied to the final model (AutoMLEngine):")
df = X.copy()
df["target"] = y
eng = AutoMLEngine(
    max_models=2,
    cv_folds=3,
    enable_tuning=True,
    tuning_config=TuningConfig(strategy="random", n_trials=10, cv_folds=3, n_jobs=-1),
)
res = asyncio.run(eng.run(df, "target"))
print(f"  best model: {res.best_model.name}")
print(f"  tuning_strategy persisted: {res.tuning_strategy}")
print(f"  improvement_from_tuning (applied gain): {res.improvement_from_tuning}")
print(f"  tuning_results recorded for: {list(res.tuning_results or {})}")
for name, p in (res.tuning_results or {}).items():
    print(
        f"    {name}: applied={p['applied']} improvement={p['improvement_over_default']:+.4f} "
        f"best_params={p['best_params']}"
    )
print(f"  best model hyperparameters now: {res.best_model.hyperparameters}")
print("\nALL 6 ACCEPTANCE CRITERIA DEMONSTRATED")
