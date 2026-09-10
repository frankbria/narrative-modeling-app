# #459 (P0.16) — dataset-creating upload routes bypass the `uploads` quota

## The issue is partly stale — verified against the code, not the text

`secure_upload.py:360` (chunked completion) **already carries** `quota("uploads")`; #582
added it when it repaired that flow. The issue's "three of four" no longer holds. What
is actually unguarded today:

| Route | Mounted at | Guard | Creates a dataset? |
|---|---|---|---|
| `datasets.py:141` | `POST /api/v1/datasets/upload` | ✅ | yes |
| `secure_upload.py:41` | `POST /api/v1/upload/secure` | ✅ | yes |
| `secure_upload.py:358` | `POST /api/v1/upload/chunked/{id}/complete` | ✅ (#582) | yes |
| `secure_upload.py:194` | `POST /api/v1/upload/confirm-pii-upload` | ❌ | **yes** |
| `upload.py:38` | `POST /api/v1/upload/` | ❌ | **yes** |
| `store.py:19` | `POST /api/v1/` | ❌ | yes (but 500s always — #472) |
| `features.py:584` | `POST /api/v1/datasets/{id}/features/{fid}/apply` | ❌ | **yes, when `create_new_dataset=true`** |
| `onboarding.py:136` | `POST /api/v1/onboarding/sample-datasets/{id}/load` | ❌ | server-supplied — see below |

A fan-out exploration found the `features/apply` row, which the issue does not mention:
with `create_new_dataset=true` it calls the same `DatasetService.create_dataset` that
`/datasets/upload` does. A tenant at their cap can mint unlimited datasets through it.
The flag defaults to `false`, so a route-level dependency would over-charge every
in-place apply — this one needs a **conditional reserve** on the create branch instead.

The same exploration corrected two of my assumptions: `store.py`'s `UserData(...)` passes
`file_name`/`headers`/`data`, which are not model fields, so it raises `ValidationError`
before `.insert()` and **never creates a row** (which is #472's 500); and
`DatasetService.create_dataset` writes **two** rows per call (`DatasetMetadata` plus the
legacy `UserData` dual-write) — one dataset in two id-spaces, one quota unit, correct.

`app/api/routes/__init__.py`'s `api_router` aggregator is mounted nowhere (#530/#471), so
it adds no live routes; the four routers above are mounted directly in `main.py`.

The frontend calls `/upload/chunked/*`, `/upload/secure` and `/upload/confirm-pii-upload`.
It never calls `/datasets/upload` — which is the only route `TestUploadQuota` exercises,
confirming AC4.

## The one real design problem

`/secure` returns **200** with `status: "pii_detected"` when it finds high-risk PII, and
creates no dataset. `QuotaRefundMiddleware` refunds only on >= 400, so **that unit is
already being charged today for a dataset the tenant never received.**

`/confirm-pii-upload` then takes the file again and creates the dataset independently —
it does not require `/secure` to have run. So it must be guarded on its own, or it is an
unlimited free dataset factory. But guarding it naively makes the ordinary PII flow cost
**2 units for 1 dataset**.

Resolution: charge once per dataset actually created. `/secure`'s `pii_detected` branch
releases its reservation; `/confirm-pii-upload` gets its own guard. No response-contract
change, so the frontend's `requires_confirmation` handling is untouched.

## Plan (TDD — RED first per step)

### 1. `enforcement.release(request)` + a metric marker
- `release(request)` hands back every reservation on the request and clears it — the same
  list `QuotaRefundMiddleware._refund` walks, reusing its double-refund guard. For the
  case the middleware cannot see: a 2xx that did not do the work.
- `quota()` tags its closure with the metric (`dependency.__quota_metric__ = metric`) so a
  test can ask a route what it meters instead of digging through `__closure__`.

### 2. Guard the unguarded dataset-creating routes
- `confirm_pii_upload`, `upload.upload_file`, `store.store_data` get
  `dependencies=[Depends(quota("uploads"))]`.
- None of them calls `metering.record()` — confirmed none does today (AC2).
- `store.py` creates no row today, so this guard is a no-op there (reserve, then the 500
  refunds it). It goes on anyway rather than into the exempt list: the handler is *written*
  to create a dataset and only fails on a validation bug, so exempting it would make #472's
  fix silently reopen this hole. One line now beats a stale exemption later.

### 2b. Conditional reserve on `features/apply`
- `POST /datasets/{id}/features/{fid}/apply` reserves an `uploads` unit **only** when
  `create_new_dataset` is true, via `enforcement.reserve(...)` in the handler — the same
  primitive `quota()` uses, so `QuotaRefundMiddleware` still covers a later failure.
- Not a route dependency: the flag defaults to false and the in-place apply creates
  nothing, so a dependency would charge for work that is not an upload.

### 3. Release the reservation on `/secure`'s PII branch
- One `await release(request)` before the `pii_detected` return. Needs `request: Request`
  added to that handler's signature.

### 4. The enumerating test (AC3)
- Walk `app.routes` for every POST on the dataset-creating routers, compare against a
  declared registry in the test.
- A route not in the registry **fails** with an instruction to decide: meter it, or add it
  to the exempt set with a reason. That is what makes a fifth route fail rather than
  silently join the gap.
- Each registry entry marked metered asserts the route really carries a
  `quota("uploads")` dependency, via the marker from step 1.

### 5. Repoint the existing test (AC4)
- `TestUploadQuota` moves to `/upload/chunked/{id}/complete` — the route the UI uses.
- Keep a `/datasets/upload` case too; losing coverage of a guarded route to fix the test's
  aim would trade one gap for another.

### 6. Refund behaviour on the new paths (AC5)
- Assert a failed `confirm-pii-upload` and a failed legacy `upload` refund their unit, and
  that the PII-detected `/secure` leaves usage at 0.

## Deliberately out of scope

- **The onboarding sample-dataset loader.** It creates a `UserData` with an s3_url, but the
  content is *ours*, not the tenant's upload, and every new user is forced through
  onboarding (#470) — metering it would spend one of a free tenant's uploads before they
  have done anything, and 402 the onboarding flow for anyone at their cap. It is also
  currently broken: it fabricates an S3 URL for a file it never uploads (#541). Recorded in
  the test's exempt set **with that reason** so it cannot be forgotten, and the product
  question gets a follow-up issue rather than being decided silently here.
- The second `UserData(...)` in `onboarding_service.py` (~:846) is an onboarding-progress
  carrier with no s3_url and no rows — not a dataset, not metered.
- #472 (store.py's unconditional 500), #541, and the P0.19–P0.21 rewrites named in the
  issue's Dependencies section. This change only adds a dependency to those handlers; it
  does not touch their bodies, so it will not collide with a parallel rewrite.
