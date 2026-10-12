# Issue #943: erasing a dataset leaves the models trained on it

## Problem
Training keys `MLModel.dataset_id` and `TrainingJob.dataset_id` on `str(UserData.id)`.
`_erase_one_dataset` runs the model cascade, the version artifacts and the string-keyed
sweep only when a `DatasetMetadata` parent exists, and only for the id it was called
with. So erasing a UI upload (no twin), or a `/datasets/upload` pair by its metadata id,
leaves the models, their S3 artifacts and their training jobs, and reports success.
Erasing such a pair by its `UserData` id also leaves the `DatasetMetadata` twin.

## Plan
- [ ] RED: `tests/test_services/test_erasure_reaches_trained_models.py`: a model and job
      stored the way the task stores them (under the upload's id), erased by each id for
      a twinless upload, a same-id twin (#850) and a different-id pair; a sibling
      dataset's model survives; the manifest counts.
- [ ] `_erase_one_dataset`: resolve both parents in both directions (`(user_id, s3_url)`),
      then sweep keyed children for every id the dataset is known by. Split it (cc 23)
      into helpers under the CRAP ceiling, keeping the order: models, version objects,
      keyed documents, files, parents last.
- [ ] Count orphaned models on staging (AC5), counts only.
- [ ] CLAUDE.md, gate, review, demo against real S3, PR.
