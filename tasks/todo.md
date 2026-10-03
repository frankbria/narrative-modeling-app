# #697 — Label-encoded models skip encoding at serving (P0.38)

Plan self-authored (no plan on the issue). No architectural fork.

## Root cause
`FeatureEngineer.transform` nests the label branch under `if "encoder" in self.transformers`,
but label encoding stores only `"label_encoders"`. So serving (and AutoML's own test-set
transform, `automl_engine.py:331`) feeds raw strings to the estimator.

## Steps
1. RED: tests in `tests/test_model_training/test_feature_engineer.py`
   - AutoMLEngine run with `encoding_method="label"` (real models) → engine's
     `feature_engineer.transform(held_out)` equals the fit-time encoding; `model.predict` succeeds.
   - unseen category at serving → `-1`, no crash.
2. GREEN: `transform` gates on keys — `"encoder"` → one-hot, `"label_encoders"` → label.
   Label path casts to `str` (as fit does) and maps via `classes_`; unseen → `-1`.
3. Mirror in `_standalone_fe.py` (no `app` imports; keep everything after the class marker).
   Parametrize `test_standalone_transform_matches_the_platform` over onehot + label (+ unseen row).
4. Docs: CLAUDE.md #632 bullet ("preserves the label-encoding-under-encoder quirk") → updated.

## Decisions
- Unseen category → the column's training mode (what a blank is imputed to); `-1` only with no
  categorical imputer. Chosen by the user after the demo showed `-1` extrapolating (0.999
  confidence, unflagged). `LabelEncoder`s kept (no `OrdinalEncoder` switch).
- Both `transform`s split into step helpers for the CRAP gate.
- Flagging unseen/null inputs in responses + imputing JSON null → #838.

PR #839.

## Acceptance criteria
- [x] AC1 transform applies `label_encoders` (gated on that key)
- [x] AC2 real-model test: held-out encoding == training encoding; predict succeeds
- [x] AC3 StandaloneFeatureEngineer matches; parity test green (label case added)
- [x] AC4 unseen categories don't crash; behavior documented
