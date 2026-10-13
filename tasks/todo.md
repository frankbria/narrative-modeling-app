# Issues #761 and #762: what importing the backend loads and prints

## #761: the health probe imports the whole routes package
Already fixed, by #530: the routes package's init is empty, so importing the probe
loads `app.api.routes.health` and nothing heavy. What the issue still asks for is a
guard, so it stays that way.
- [x] A test imports `app.health_probe` in a fresh interpreter and fails if scikit-learn,
      SHAP, pandas, numpy, scipy or optuna is loaded, or any route module but `health`.
      Mutation-checked with an import of the training routes added to `health.py`.

## #762: five field-shadow warnings at every import
`UserData.schema`, `ColumnStats.count`, `UserDataResponse.schema`, and two the issue did
not list: `DatasetSummaryRequest.schema`, `DatasetSchemaResponse.schema`.
- [x] The names are the stored key or a public response key, so they stay. An alias would
      rename the attribute for every reader with no change in behaviour.
- [x] `expect_field_shadow(field, model)` declares each one above its class.
- [x] A test imports `app.main` in a fresh interpreter with UserWarning as an error.
