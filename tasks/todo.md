# Issue #728: the feature lookups charge an ai_call for a cache read

## Problem
`GET …/features/suggestions/{id}`, `…/features/apply` and `…/features/apply-multiple`
carry `quota("ai_calls")` and never release it. On a warm cache they read the cached set
and are charged a unit each. On a cold cache they regenerate the set, model call included,
but suggestion ids are minted per generation (`uuid4` suffix), so the new set can never
hold the id asked for: a paid call that still answers not found.

## Plan
- [x] RED: three lookups on a warm cache leave `ai_calls` at 0; on a cold cache nothing is
      generated (404, 404, and "Suggestion not found" per id).
- [x] The lookups read `get_cached_suggestions` only, like feedback since #523, and carry no
      quota. Registry: the three move to `_EXEMPT`.
- [x] `suggest_features(read_cache=…)` has no caller left: remove it. The function is at
      cc 14, so it is split (`_model_suggestions`, `_shortlist`, `_response`).
- [x] `/suggest-more` never released its unit when no model ran. It does now, as `/suggest`
      does. At cc 11 it is split (`_another_batch`).
- [x] `apply_feature` (cc 9) and `apply_multiple_features` (cc 10) are split.

## Found, not done here
- `/suggest-more` filters "already shown" by id, and ids are new on every generation, so
  it returns the same rule-based suggestions again under new ids.
- The `/features` page fetches `GET /datasets/{id}/features/suggestions`, which no route serves.
