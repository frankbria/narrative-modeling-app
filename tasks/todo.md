# #458 (P0.15) + #510 (P1.32) — Stripe entitlement: `unpaid` and period expiry

**Scope**: both issues, together. #510 states explicitly *"Must land before or with
P0.15"* — and it is confirmed real: the installed SDK (stripe 15.4.0, default API
version `2026-07-29.dahlia`) has **no** `current_period_end` on `_subscription.py`;
it exists only on `_subscription_item.py:67`. So `_period_end()` returns `None` for
every real webhook today. Landing #458's expiry check alone would drop every paying
customer to FREE at once.

## Findings from exploration

- `app/models/subscription.py:66` maps `"unpaid" -> PAST_DUE`; `:161` `is_entitled`
  reads status only.
- `app/api/routes/billing_webhook.py:211` `_period_end()` reads the top-level field.
- Entitlement readers: `metering.effective_tier_for` -> `enforcement.quota()`,
  `billing.py:125` (UI), `api_keys.py:30` (rate-limit ceiling), webhook `_apply`.
- No scheduler exists in the app (BackgroundTasks only). Precedent for one-shot
  operator repair scripts: `scripts/fix_api_key_rate_limits.py` (#455).

## Plan (TDD — RED first for each step)

### 1. #510 — read `current_period_end` from the right place
- `_period_end(obj)`: top-level if present (older API versions / older webhook
  endpoint pins still send it), else `items.data[0].current_period_end`. Reuse
  `_epoch`. Still never raises — Stripe retries a non-2xx forever.
- Pin the API version explicitly: `STRIPE_API_VERSION` constant in
  `app/billing/stripe_client.py`, set on the client in `_client()`.
- Test: an SDK bump that changes the default version trips a test (guards the
  payload shape assumption); a dahlia-shaped payload populates `current_period_end`;
  a legacy top-level payload still works; unparseable values still yield `None`.

### 2. #458 AC1/AC2 — `unpaid` is terminal
- `"unpaid": cls.CANCELED`. Docstring explains `past_due` (Stripe still retrying —
  serve) vs `unpaid` (retries exhausted — terminal), so nobody re-merges them.

### 3. #458 AC3 — expiry in `is_entitled`
- `is_entitled` = status entitled **AND** not lapsed.
- Grace window: **3 days** past `current_period_end` (module constant
  `ENTITLEMENT_GRACE`). Covers webhook lag, clock skew and Stripe's own retry
  window without extending a free month.
- `current_period_end is None` -> **no known expiry, stay entitled by status**.
  Deliberate: a `checkout.session.completed` establishes ACTIVE before the
  tier-resolving `customer.subscription.created` arrives with the period end, and
  revoking on *missing* data downgrades a customer who has just paid. With step 1
  landed, every real paid subscription carries a period end.
- `as_utc()` on the stored value before comparing (Mongo reads back naive).

### 4. #458 AC4 + #510 AC4 — reconciliation / backfill
- `scripts/reconcile_subscriptions.py`: read-only by default, `--apply` re-fetches
  each row's subscription from Stripe and rewrites status + period end. Serves as
  both #510's backfill and #458's repair path.
- Record the decision in the model docstring: webhook delivery is the primary sync
  mechanism; the expiry check makes a missed *lapse* fail closed, and this script is
  the repair path for a missed *renewal*. No scheduler is introduced.
- File a follow-up issue: run/schedule the reconciliation on staging + production
  (operator task — SSH is not available from here).

### 5. Tests
- `tests/test_models/test_subscription.py`: `unpaid` not entitled; expired ACTIVE
  not entitled; `past_due` inside the period still entitled; within grace still
  entitled; past grace not; `None` period end still entitled.
- `tests/test_api/test_billing_webhook.py`: item-shaped payload populates the field.
- Existing test at `test_subscription.py:26` asserting `unpaid -> PAST_DUE` must
  flip (it encodes the bug).

## Non-goals
- No scheduler / cron infrastructure (AC4 permits the recorded decision).
- No change to `PAST_DUE` semantics.
