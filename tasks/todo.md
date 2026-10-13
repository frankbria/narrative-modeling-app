# Issue #751: the dataset routes confirm that a foreign id exists

## Problem
Seven routes in `datasets.py` look a dataset up and then answer 403 "Access denied" when
it is another tenant's. Every other owned surface answers 404 for unknown and foreign
alike, so that no response says which ids are real.

## Plan
- [x] RED: real documents; each of the seven routes answers a foreign id exactly like an
      unknown one.
- [x] `_owned_dataset(dataset_id, user_id)`: the lookup and the one 404, used by all seven.
- [x] The handlers were at cc 6 to 13. With the lookup out they are 4 or less;
      `get_dataset` and `update_dataset` share `_detail` for the response they both built.
- [x] The e2e isolation spec asserts 404 on every read surface.
- [ ] The same lookup-then-403 in `transformations.py` (12), `feature_store.py` (9),
      `features.py` (8), `plot.py` (3), `analytics_result.py` (3), `models.py` (1) and
      `feature_engineering.py` (1): filed separately.
