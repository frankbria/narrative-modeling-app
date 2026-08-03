# Data Erasure & Backup Runbook (issue #259)

Covers the operational half of P0.9: **right-to-erasure** (implemented in code)
and the **backup/restore posture** (this runbook — cloud config + a tested
restore drill). The application code fulfills cascade-erasure; the backup and
S3-durability controls below are enabled in the cloud consoles / IaC and are not
part of the deployable image.

---

## 1. Right-to-erasure (implemented)

Erasure is a best-effort, idempotent cascade across both dataset id-spaces. See
`app/services/erasure_service.py`.

| Operation | Endpoint | Notes |
|---|---|---|
| Delete one dataset (now cascading) | `DELETE /api/v1/datasets/{dataset_id}` | Existing route; now sweeps all children + S3 + Redis. |
| Erase one dataset + audit + manifest | `POST /api/v1/datasets/{dataset_id}/erase` | Returns a `DeletionManifest`; writes an `ErasureAuditLog` entry. |
| Erase all data for the caller | `POST /api/v1/users/me/erase` | Sweeps every dataset the user owns + user-scoped records. |

**What is swept:** the S3 source object, per-model S3 artifacts
(`models/{user}/{model}/…` via `delete_model`), every child document keyed by
`dataset_id` (string id-space) or by a `Link[UserData]` DBRef (legacy id-space),
and the Redis viz-cache (`viz:{id}:*`). The parent document is deleted **last**,
so an interrupted run is re-discoverable; re-running the same erase clears any
residuals a partial failure left.

**Audit:** every erase appends one immutable `erasure_audit_log` document
(actor, subject, target, manifest snapshot, status). It is insert-only — nothing
in the app updates or deletes it.

**GDPR/CCPA fulfillment:** to service a subject-erasure request, call
`POST /api/v1/users/me/erase` as the subject (or an operator invoking the
service with the subject's `user_id`), retain the returned manifest, and confirm
the `erasure_audit_log` entry exists.

### Verifying an erasure
```bash
# Residual check (should be zero across every dataset_id-keyed collection)
mongosh "$MONGODB_URI" --eval '
  ["transformation_configs","dataset_versions","transformation_lineages",
   "feature_definitions","workflow_states","bulk_transformation_jobs",
   "ml_models","model_configs","training_jobs","data_issues",
   "ai_recommendation_feedback"].forEach(c =>
    print(c, db[c].countDocuments({dataset_id: "<DATASET_ID>"})))'
```
Automated equivalent: `tests/test_integration/test_erasure_cascade.py`.

---

## 1b. Permissions the operator needs

The app's own IAM user (`fastapi-s3-uploader`) is deliberately object-scoped and
**cannot** configure the bucket — `s3:GetBucketVersioning` returns AccessDenied.
That is correct: the application should not be able to rewrite its own retention
policy. Backup configuration needs a separate principal.

`ops-backup-iam-policy.json` in this directory is the minimum set. Attach it to an
ops user/role (not to the app user):

```bash
aws iam create-policy --policy-name NMABackupPosture \
  --policy-document file://docs/deployment/ops-backup-iam-policy.json
aws iam attach-user-policy --user-name <ops-user> \
  --policy-arn arn:aws:iam::<account>:policy/NMABackupPosture
```

The second statement is scoped to `nma-restore-drill-*` buckets only, so the drill
can create and destroy its own throwaway buckets without any standing permission
over real data.

Atlas needs a separate API key (Project Owner for enabling backup; Project Read
Only is enough for `verify-backup-config.sh`).

---

## 2. MongoDB Atlas backups (enable in Atlas)

> Enabling is a console/Admin-API action needing real Atlas credentials, so it
> stays manual. **Verifying is not** — `./scripts/ops/verify-backup-config.sh`
> checks `backupEnabled`, `pitEnabled` and the hourly/daily/weekly snapshot policy
> over the Atlas Admin API when `ATLAS_PUBLIC_KEY` / `ATLAS_PRIVATE_KEY` /
> `ATLAS_GROUP_ID` / `ATLAS_CLUSTER_NAME` are set, and says SKIP rather than
> passing silently when they are not.

1. **Cloud Backup** → cluster → **Backup** → enable **Cloud Backup** (snapshots).
2. Snapshot policy: hourly (2-day retention) + daily (7-day) + weekly (4-week);
   enable **Point-in-Time Restore** (continuous oplog) for the production tier.
3. Set the backup **compliance policy** to prevent snapshot deletion below the
   retention window.
4. Record the cluster's backup status in `MONGODB_ATLAS_MIGRATION_STATUS.md`
   (its "backup: TODO" line is closed by this step).

**Restore drill (quarterly, tested):**
1. Atlas → **Backup** → pick a recent snapshot → **Restore** → **new cluster**
   (never restore over production).
2. Point a scratch backend (`MONGODB_URI` → restored cluster, `ENVIRONMENT=staging`)
   at it; run the read-only smoke: list datasets, fetch one, open its versions.
3. Record RTO (time to usable) and RPO (snapshot age) in the drill log below.
4. Tear down the scratch cluster.

---

## 3. S3 versioning + lifecycle (enable on the bucket)

> **Scripted (#299).** Do not click through the console:
>
> ```bash
> AWS_BUCKET_NAME=<prod-bucket> ./scripts/ops/configure-s3-backup.sh --dry-run
> AWS_BUCKET_NAME=<prod-bucket> ./scripts/ops/configure-s3-backup.sh
> ```
>
> Idempotent, and it refuses to run without credentials or a reachable bucket
> rather than half-applying. It covers steps 1 and 2 below; **MFA-delete (3.4)
> stays manual** because S3 requires the root account's MFA token on the request.
> The steps are kept here because a script is not a substitute for knowing what
> it does — and for the case where you are configuring by hand.

1. **Versioning:** enable **Bucket Versioning** — protects against accidental
   deletes/overwrites and makes the cascade-erasure's `DeleteObject`s create
   delete-markers (recoverable during the retention window) rather than
   destroying object history immediately.
2. **Lifecycle rule `expire-noncurrent`:** permanently delete **noncurrent**
   versions after 30 days, and abort incomplete multipart uploads after 7 days —
   bounds the storage growth versioning would otherwise create.
3. **Lifecycle rule `purge-erased` (optional, GDPR):** to guarantee erased PII is
   *permanently* gone (not just delete-markered), run a scheduled job that
   permanently deletes all versions of keys recorded in erasure manifests older
   than the legal retention window.
4. **MFA-delete** on the production bucket for tamper resistance.

**S3 restore drill (quarterly):** scripted — `./scripts/ops/drill-s3-restore.sh`.
It creates its own throwaway bucket (never the app bucket), enables versioning,
writes a canary, deletes it, asserts a delete-marker exists, restores by removing
the marker, and asserts the bytes come back identical. Tears the bucket down even
on failure.

Add `--endpoint http://localhost:4566` to validate the *procedure* against
LocalStack at no cost or risk; without it, it is a real drill against real S3.

> **`--version-id=<marker>`, with the equals sign.** Version IDs are base64-ish
> and can begin with `-`, at which point `--version-id <marker>` is parsed as
> another flag and the restore dies with "expected one argument". This runbook
> said the spaced form until the scripted drill hit it (#299) — exactly the kind
> of step you do not want to debug mid-incident.

---

## 4. Verifying the posture

**Automated (#299).** `.github/workflows/backup-verify.yml` runs the verifier on
the 1st of each month and posts the result to the workflow run's summary, and
reminds about the restore drill in January/April/July/October. It is secret-gated:
until the cloud credentials are added it reports "not configured" and passes,
deliberately, because a monthly red X on a repo that has not set this up yet is
noise and noise gets workflows disabled.

Manually, before and after every drill:

```bash
AWS_BUCKET_NAME=<prod-bucket> ./scripts/ops/verify-backup-config.sh
```

Read-only, and **exits non-zero when anything required is missing** — so it is
evidence, not reassurance. Paste its output into the drill log rather than
writing "backups verified". It reports `MANUAL` for MFA-delete and `SKIP` for
Atlas without API credentials instead of quietly counting them as passes.

---

## 5. Drill log

| Date | Drill | RTO | RPO | Operator | Notes |
|---|---|---|---|---|---|
| 2026-08-03 | S3 restore — **procedure validation** (LocalStack, not production) | n/a | n/a | automated | `drill-s3-restore.sh` end-to-end green. Found and fixed a real defect in the documented step: `--version-id <marker>` fails when the ID starts with `-`. **Not a production drill** — the real one still needs to run against the live bucket. |
| _pending_ | S3 restore — production | | | | |
| _pending_ | Atlas restore — production | | | | |

---

## Beta limitations / follow-up (ops issue)
- Atlas backup + S3 versioning/lifecycle enablement is **manual cloud config** —
  live enablement + the first restore drill are tracked in **issue #299**.
- Erasure is best-effort, not a distributed transaction (Mongo transactions need
  a replica set the local/CI tier lacks). Idempotent re-run is the recovery
  mechanism; the manifest records any residual failures.
- `POST /users/me/erase` erases the user's **data**, not the auth/account record
  (that lives in the auth provider).
