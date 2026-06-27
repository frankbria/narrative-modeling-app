# Issue #201 — Honest calibration/eval split + out-of-sample calibration score

## Scope decision (deviates from the CodeRabbit plan)
- **Item 1 (honest split) + Item 2 (out-of-sample calibration score) only.**
- **Phase 3 (batch vectorization) EXCLUDED** — the issue body says it "was split to #202".
- The issue **title** asks for an *honest split*, and the body marks the **real fix** (Option 1:
  reserve a calibration slice from the training set) as **preferred**. CodeRabbit chose the
  weakest option (caveat-flag-only), which does not deliver the title. We do the real fix, and
  keep an honest in-sample flag only for the small-data fallback path.

## The fix
Today: one `train_test_split` → `X_test` is used for candidate test scores **and** calibration
fit **and** the #79 dashboard arrays. So dashboard metrics + `calibration_score` are in-sample
(optimistic).

New (classification only): carve a disjoint calibration slice from the **training** set.
- `X_train, X_test = split(X)`            <- clean holdout (dashboard eval + calibration scoring)
- `X_fit, X_cal = split(X_train)`         <- X_cal disjoint from base-model training
- base models fit/CV on `X_fit`; calibrate best on `X_cal`; **score calibration on `X_test`**
  (out-of-sample); capture #79 arrays on `X_test` (clean -> honest).
- **Fallback** (data too small / stratify fails): keep current behaviour (calibrate on `X_test`,
  in-sample) and set the honesty flags True.
- Regression: unchanged (no calibration; `X_test` already clean).

## Steps (TDD)
1. `confidence_service.calibrate_classifier` — optional `X_score`/`y_score`; brier measured on the
   score set when given (out-of-sample), else on `X_cal` (in-sample, backward-compatible 3-tuple).
2. `automl_engine.py` — carve cal slice for classification w/ size+stratify guard; FE fit on `X_fit`;
   `_calibrate_best_model` returns `(is_calibrated, method, score, is_insample)`; capture eval on
   `X_test`; `AutoMLResult` gains `calibration_score_is_insample` + `evaluation_on_calibration_set`.
3. `models/ml_model.py` — add `calibration_score_is_insample: bool = True`,
   `evaluation_on_calibration_set: bool = False`; update `calibration_score` docstring.
4. `model_storage.py` — persist the two new keys from `model_metadata`.
5. `api/routes/model_training.py` — populate the two keys; surface `evaluation_on_calibration_set`
   on full+partial eval responses; pass it to the report card.
6. `schemas/evaluation.py` — add `evaluation_on_calibration_set: bool = False` to `ModelEvaluationResponse`.
7. `services/evaluation_explanation_service.py` — optional flag -> prepend a `concerns` entry.
8. `lib/types/evaluation.ts` — mirror `evaluation_on_calibration_set`.
9. Tests: confidence (out-of-sample), automl (honest path flags False / fallback True),
   `sample_ml_model` mock fixture +2 fields (recurring gotcha), eval route + report-card concern.
10. Docs: CLAUDE.md #83 note -> record #201.
