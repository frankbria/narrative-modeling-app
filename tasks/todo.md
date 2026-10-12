# Issue #725: MLModel.last_used_at is not refreshed by predictions

## Problem
`last_used_at` is written only when a model's artifacts are loaded from S3 (a cache
miss). A model that stays in the process-local cache keeps the stamp of its first load
after the last restart, however many predictions it serves. The monitor page shows that
value as "last prediction at". The comment at the write says the serving path updates it
per prediction; nothing on the serving path does.

## Decision (the issue offers two)
Stamp it from the serving paths, rather than relabel it "last loaded": the product shows
it as the time of the last prediction, so that is what it should be.

## Plan
- [ ] RED: `tests/test_services/test_model_last_used.py` (the helper) and a route test in
      `tests/test_api/test_production.py` with `load_model` stubbed, which is what a cached
      model looks like.
- [ ] `model_storage.stamp_last_used(ml_model)`: a targeted `$set`, skipped when the
      stored stamp is under five minutes old (the serving routes read the document fresh
      on every request, so that costs no extra read), never raising.
- [ ] Call it from the production serving route and the in-app predict route.
- [ ] Correct the comment in `load_model`. Remove `PredictionMonitoringService.log_prediction`'s
      stamp? Out of scope: that method has no caller; noted on the issue.
