# Model artifact integrity (#266)

Model estimators and feature transformers are persisted to S3 with `joblib`
(pickle), and some Redis-cached values are pickled. `joblib.load` / `pickle.loads`
**execute arbitrary code on deserialization**, so they are safe only on bytes we
know we wrote. If an attacker can write to the S3 bucket (e.g. the
now-removed unauthenticated presigned-PUT route, #252/#291) or tamper with Redis,
an unauthenticated deserialize becomes remote code execution.

Two controls, defense-in-depth. **Both should be in place for production.**

## 1. Code control — HMAC sign + verify (shipped in #266)

Every serialized artifact is signed with HMAC-SHA256 over a server-only secret and
verified before it is ever deserialized (`app/utils/artifact_signing.py`).

- **Model artifacts (S3).** `ModelStorageService.save_model` (`app/services/model_storage.py`) signs the exact bytes
  it uploads and stores the signature on the **MongoDB `MLModel` document**
  (`model_signature`, `feature_transformer_signature`). The artifact lives in
  less-trusted S3; the signature lives in trusted Mongo. `load_model` recomputes
  the HMAC over the downloaded bytes and **refuses to `joblib.load`** on a
  mismatch. A bucket tamperer can swap the pickle bytes but cannot forge a valid
  signature (no secret) nor alter the Mongo-stored signature.
  - Pre-#266 models have `model_signature = None` and load with a warning
    (backward compatible). Retrain to sign them; control #2 backstops them.
- **Redis values** (`app/services/redis_cache.py`). Simple values are stored as JSON (JSON cannot execute code).
  Complex objects fall back to a **signed pickle** — an HMAC prefix that is
  verified before `pickle.loads`. Unsigned or tampered blobs are refused (treated
  as a cache miss).

### Required configuration

The signing secret resolves as `ARTIFACT_SIGNING_KEY` → `NEXTAUTH_SECRET` → an
insecure dev fallback (logged as a warning). Any real deployment already sets
`NEXTAUTH_SECRET` (auth fails without it), so signing is secure by default. Set a
distinct `ARTIFACT_SIGNING_KEY` only if you want to rotate artifact trust
independently of the auth secret.

> **Staging:** `docker-compose.staging.yml` does not list `ARTIFACT_SIGNING_KEY`, and
> a variable reaches a container only if compose lists it. Setting it in
> `.env.staging` alone does nothing; add `ARTIFACT_SIGNING_KEY: ${ARTIFACT_SIGNING_KEY:-}`
> to the backend's `environment:` first, then recreate the backend.

> Rotating the signing secret invalidates existing signatures: previously-signed
> models will fail verification and must be retrained. Rotate deliberately.
>
> **Before rotating `NEXTAUTH_SECRET`** (e.g. responding to an auth-credential
> breach), first set `ARTIFACT_SIGNING_KEY` to the *current* `NEXTAUTH_SECRET`
> value. That decouples artifact trust from the auth secret so rotating auth does
> not silently invalidate every signed model and force a mass retrain.

## 2. Infrastructure control — restrict bucket writes to the backend's IAM principal

The code control assumes the attacker cannot forge the secret. Removing their
write access entirely is the complementary control and the strongest mitigation
for legacy (unsigned) artifacts.

Apply a bucket policy so that **only the backend's IAM principal** may `PutObject`
under the `models/` prefix. Staging authenticates with an IAM **user**
(`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` in compose), so the ARN is
`arn:aws:iam::<ACCOUNT>:user/<BACKEND_USER>`; use the `role/` form if the backend
runs under a role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyNonBackendWrites",
      "Effect": "Deny",
      "Principal": "*",
      "Action": ["s3:PutObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::<BUCKET>/models/*",
      "Condition": {
        "StringNotEquals": { "aws:PrincipalArn": "arn:aws:iam::<ACCOUNT>:user/<BACKEND_USER>" }
      }
    }
  ]
}
```

Also confirm the bucket blocks public ACLs and that no presigned-PUT route hands
out write URLs (removed in #252/#291).

## Out of scope

`app/services/model_export.py` emits a `pickle.load` inside a **generated inference
script** (and the inlined `model_export_assets/_standalone_fe.py`) that the user
downloads and runs on their own machine — client-side code, not a backend
deserialization sink, and outside this threat boundary.
