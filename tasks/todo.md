# Issue #733: visualizations and the feature store read every dataset as CSV

## Problem
Five readers parse a stored dataset without looking at what it is:
- `app/services/visualization_cache.py`, three places, and `app/api/routes/visualizations.py`
  (`_load_dataframe`): `pd.read_csv(get_file_from_s3(url))`.
- `FeatureStoreService._load_dataset_frame`: csv and Excel only.
A transformation rewrites the dataset as Parquet, so every chart and every feature-store
check fails for a dataset that has been transformed once. A workbook or JSON upload
fails in the charts from the start.

## Plan
- [ ] RED: LocalStack tests with a real Parquet object behind a `UserData` / a
      `DatasetMetadata`, through the histogram, the route's loader and the feature store.
- [ ] `s3_service.read_dataframe_from_bytes(content, file_type=None)`: the shared reader
      for bytes already in memory (the readers take a path).
- [ ] The four chart readers read by content (no declared type needed; the route's
      loader is given only a URL). The feature store reads by its declared type.
- [ ] `generate_and_cache_histogram` is at cc 7: its cache lookup moves to a helper.
- [ ] Update the tests that stubbed `get_file_from_s3` with a string and `pandas.read_csv`.
