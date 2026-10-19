# Backend Scripts

Operational scripts. Run them from `apps/backend` with `PYTHONPATH=. uv run python scripts/<name>.py` (most import `app`, and `python scripts/x.py` puts only `scripts/` on the path),
with `MONGODB_URI` + `MONGODB_DB` (and the S3 settings where noted) for the environment
you mean. Scripts that change data are read-only unless given `--apply`; most accept
`--json` for machine-readable output. Each script's docstring is its full manual.

`scripts/` is not copied into the backend image; on staging, see
[docs/ops/STAGING_DEPLOYMENT_GUIDE.md](../../../docs/ops/STAGING_DEPLOYMENT_GUIDE.md).

## Index

| Script | What it does | Flags |
|---|---|---|
| `seed_e2e_data.py` | Seeds the e2e users, the admin's PRO subscription and the test bucket (below) | `--clear`, `--with-data` |
| `generate_sample_datasets.py` | Regenerates the onboarding samples in `app/sample_datasets/` | |
| `audit_dataset_file_types.py` | Finds dataset rows whose `file_type` disagrees with the extension of the object it points at | `--apply`, `--json` |
| `backfill_dataset_file_sizes.py` | Sets `file_size` on dataset rows written before it was recorded | `--apply`, `--json` |
| `check_s3_url_ownership.py` | Reports `UserData` rows whose `s3_url` points outside the deployment's bucket; exit 1 if any | |
| `check_ab_test_duplicates.py` | Pre-deploy check for the unique `experiment_id` index on `ab_tests` | `--drop-legacy-index`, `--json` |
| `dedupe_column_stats.py` | Pre-deploy dedupe for the unique `(dataset_id, column_name)` index on `column_stats` | `--apply`, `--drop-legacy-index`, `--json` |
| `fix_api_key_rate_limits.py` | Finds and corrects `APIKey` rows with an out-of-range `rate_limit` | `--apply` |
| `inventory_dataset_links.py` | Inventories dual-written dataset twins whose link is broken | `--json` |
| `inventory_orphaned_s3_objects.py` | Counts and sizes dataset/transformation S3 objects no row owns | `--dump`, `--json`, `--min-age-seconds` |
| `reconcile_model_artifacts.py` | Reports S3 objects under `models/` that no `MLModel` owns | `--dump`, `--json`, `--min-age-seconds` |
| `reconcile_subscriptions.py` | Re-reads every `Subscription` from Stripe and rewrites what drifted | `--apply` |
| `reconcile_unprefixed_s3_keys.py` | Moves bucket-root dataset objects under their owner's prefix (below) | `--apply` |
| `demo_*.py` | Evidence scripts for the issue in their name | |

## `seed_e2e_data.py`

Run by `apps/frontend/test-e2e.sh` before every e2e run; you rarely call it by hand.

- Creates the NextAuth test user (`users` collection) and puts the admin identity on an
  active PRO subscription, so `plan-limit.spec.ts` can hit a real limit.
- Creates the test bucket when `AWS_ENDPOINT_URL` is set (LocalStack/MinIO only, never
  real AWS); exits 1 if it cannot.
- `--clear` first deletes the test user from `users`; `--with-data` also seeds a sample dataset
  owned by `TEST_USER_ID`.

| Variable | Default |
|---|---|
| `MONGODB_URI` | `mongodb://localhost:27017` |
| `MONGODB_DB` | `narrative-modeling-test` |
| `TEST_USER_EMAIL` | `test@narrativeml.com` |
| `TEST_USER_ID` | `test-user-12345` (the credentials provider's id, the token's `sub`) |
| `TEST_ADMIN_ID` | `test-admin-12345` |
| `AWS_ENDPOINT_URL`, `AWS_BUCKET_NAME` | unset, `test-bucket` |

## `reconcile_unprefixed_s3_keys.py`

Moves dataset objects written at the bucket root as bare `{uuid}.{ext}` (every
non-chunked upload before #581) under their owner's `datasets/{user_id}/` prefix, where
the downloader, erasure and lifecycle rules can find them. Each move is copy, verify
(ETag + length), rewrite the owning `UserData`/`DatasetMetadata` rows, delete the
original. Objects with no owning row are reported and never touched. Output is counts
only.

```bash
MONGODB_URI=... MONGODB_DB=... AWS_BUCKET_NAME=... \
AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_REGION=... \
  PYTHONPATH=. uv run python scripts/reconcile_unprefixed_s3_keys.py           # dry run
# same environment:
  PYTHONPATH=. uv run python scripts/reconcile_unprefixed_s3_keys.py --apply   # move them
```

- Exit 1 while any object remains unreconciled (planned but not applied, orphaned,
  conflicting owners, or a failed step).
- Attribution scans every `user_data` and `dataset_metadata` row, so runtime scales with
  total rows; a dry run then `--apply` is two full scans.
- Run one instance at a time: there is no lock against a concurrent run.
- Unknown flags are an error, not a dry run.
- Tested against LocalStack in `tests/test_scripts/test_reconcile_unprefixed_s3_keys.py`.
