# Issue #969: the Feature Engineering stage calls three routes that do not answer

## Problem
`app/features/page.tsx` fetches `GET /datasets/{id}/features` (404 for a UI upload's id, and
it is the feature-definition list, not the dataset's columns), `GET …/features/suggestions`
(no such route) and `POST …/features/generate` (no such route, and the only thing that
completes the stage). `MODEL_TRAINING` requires the stage, so the guided workflow stops here.
Nothing consumes the stage's `selectedFeatures` either: training uses every column.

## Decision
The page calls routes that exist; no "generate" route is added. The stage becomes what its
selection says: choose the columns the model may learn from. That choice reaches training
as a new `feature_config.exclude_columns`. The suggestions panel and the three generation
checkboxes had nothing behind them and go.

## Plan
Backend
- [x] RED: `FeatureEngineer(exclude_columns=[…])` leaves those columns out at fit, at serving
      and in the export, and reports them apart from identifiers, dates and empties.
- [x] `FeatureEngineeringConfig.exclude_columns`, `FeatureConfigRequest.exclude_columns`
      (the request dumps straight onto the config).
- [x] `training_config["excluded_user_columns"]`, the model report ("Left out by you").
- [x] Everything left out: a failure reason that says so.
Frontend
- [x] `lib/services/datasetColumns.ts`: the column loader the Model page already uses
      (both id-spaces), shared.
- [x] `/features`: the dataset's columns, at least two selected, a failed load shown with a
      retry, "Continue" completes the stage with `selectedFeatures`.
- [x] Model page: columns not selected (other than the target) go out as `exclude_columns`;
      the form says how many columns the model will see. The report lists them.
- [x] Contract: the train request the page builds is checked against `TrainModelRequest`'s
      schema, captured the way the Prepare stage's are (#855).
E2E
- [x] A spec walks upload → features → model on the real stack with no mocks for this page.
- [x] `beta-journey` and `stage-transitions` stop mocking the two routes that never existed.
