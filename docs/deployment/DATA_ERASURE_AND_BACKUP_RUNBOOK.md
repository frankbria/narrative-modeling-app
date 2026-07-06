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

## 2. MongoDB Atlas backups (enable in Atlas)

> No IaC in this repo manages Atlas — configure in the Atlas UI / Admin API.

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

> Configure on the app bucket (`AWS_BUCKET_NAME`) in the S3 console / IaC.

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

**S3 restore drill (quarterly):** delete a throwaway object, confirm the
delete-marker, then restore by deleting the delete-marker (`aws s3api
delete-object --version-id <marker>`); confirm the object is readable again.

---

## 4. Drill log

| Date | Drill | RTO | RPO | Operator | Notes |
|---|---|---|---|---|---|
| _pending first run_ | | | | | |

---

## Beta limitations / follow-up (ops issue)
- Atlas backup + S3 versioning/lifecycle enablement is **manual cloud config** —
  track live enablement + the first restore drill in the ops follow-up issue.
- Erasure is best-effort, not a distributed transaction (Mongo transactions need
  a replica set the local/CI tier lacks). Idempotent re-run is the recovery
  mechanism; the manifest records any residual failures.
- `POST /users/me/erase` erases the user's **data**, not the auth/account record
  (that lives in the auth provider).
