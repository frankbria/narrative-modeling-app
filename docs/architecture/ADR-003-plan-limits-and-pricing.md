# ADR-003: Plan limits and prices (replaces the ADR-002 placeholders)

- **Status:** Accepted
- **Date:** 2026-09-16
- **Amends:** [ADR-002](./ADR-002-billing-implemented.md) — its tier numbers were declared placeholders; this records the product values.
- **Implements:** [#474](https://github.com/frankbria/narrative-modeling-app/issues/474)

## Context

ADR-002 shipped the billing mechanism with limits "chosen so the invite-only beta
stays usable" and said so: *they are placeholders and should be replaced with real
numbers before charging anyone*. Nothing measured what a unit of each metric costs,
so nothing could say whether the free tier was affordable or whether a PRO price
covered a PRO tenant.

## Unit economics (the measurement AC1 asked for)

What one unit of each metered metric costs to serve, worst case, at the list price
of the models and the host in use when this was decided. Compute is a shared VPS
priced at roughly $0.02 per core-hour; S3 is $0.023/GB-month.

| Unit | What it does | Worst case | Typical |
|---|---|---|---|
| `ai_calls` | one model completion; prompts carry the full column list (+5 examples per column) or up to 5 sample rows, `max_tokens` 300–2 500; the circuit breaker may retry 2–3x | $0.12 on gpt-4 (~2k in / 1k out) | $0.03 on gpt-4-turbo; ~$0.002 on gpt-4o-mini |
| `uploads` | parse + S3 put (≤ 100 MB) **plus one model summary in a background task that `ai_calls` does not count** (`upload.py`, `secure_upload.py`) | $0.12 | $0.05 |
| `training_runs` | CPU only, no model call; hard wall clock per tier (FREE 1 h / PRO 2 h / ENTERPRISE 4 h) at 2 cores; four S3 artifacts | FREE $0.04, PRO $0.08, ENTERPRISE $0.16 | < $0.01 |
| `predictions` | vectorised sklearn predict + one `PredictionEvent` row (30-day TTL) | $0.00001 | $0.000005 |

Model calls dominate every tier. At the placeholders, worst-case exposure per
tenant-month was ≈ $15 FREE, ≈ $680 PRO and unbounded ENTERPRISE — a PRO tenant
could cost more than ten times any plausible PRO price.

## Decision

| Tier | Price | training_runs | predictions | uploads | ai_calls |
|---|---|---|---|---|---|
| FREE | $0 | 5 | 1 000 | 10 | 30 |
| PRO | $49 / month | 100 | 100 000 | 200 | 400 |
| ENTERPRISE | contact us | unlimited | unlimited | unlimited | 5 000 |

`tests/test_billing/test_plan_limits_are_the_product_values.py` parses this table and
fails if `app/billing/plans.py` disagrees, so the code cannot be repriced without
this record moving with it.

Worst-case cost per tenant-month at these limits, still priced at gpt-4:

| Tier | ai_calls | uploads | training | predictions | Total |
|---|---|---|---|---|---|
| FREE | $3.60 | $1.20 | $0.20 | $0.01 | **≈ $5** (the acquisition budget; AC6, guarded by the same test) |
| PRO | $48 | $24 | $8 | $1 | **≈ $81 worst case, ≈ $25 typical** against $49 revenue |
| ENTERPRISE | $600 | per deal | per deal | per deal | priced per deal |

### The reasoning

**The model default is the real lever, and it moved.** Every call site now reads the
model through `app/utils/openai_client.py::openai_model()`, whose default is
`gpt-4o-mini` (`OPENAI_MODEL` / `OPENAI_FEATURE_SUGGESTION_MODEL` still override it).
That is 20–100x cheaper per call than the gpt-4 / gpt-4-turbo defaults it replaces,
so the limits above — sized so they hold even at gpt-4 prices — carry a wide margin
in practice. The limits are sized at the expensive price on purpose: an operator
setting `OPENAI_MODEL=gpt-4` back must not silently make PRO loss-making.

**`ai_calls` stays finite on every tier, ENTERPRISE included** (#461). It is the
backstop against an unbounded model invoice; 5 000 calls is ≈ $600 worst case at
gpt-4, an amount an enterprise contract can carry and a runaway script cannot exceed.

**ENTERPRISE is sales-led at launch (AC3).** There is no self-serve purchase path in
the UI and adding one would mean publishing a price for a tier whose real cost is
per-deal. The billing page shows a contact link for it. The backend keeps the
env-driven checkout (`STRIPE_PRICE_ENTERPRISE`) so a negotiated deal can still be
entitled through Stripe without new code.

**FREE is sized to a ≈ $5/month acquisition budget (AC6)**, not to be a teaser: 5
training runs, 10 uploads and 30 model calls are enough to load a dataset, get it
summarised, ask for feature suggestions and train a model end to end. The two
AI-carrying units (`ai_calls` and `uploads`) are what the budget actually buys.

**The deployed values are the code defaults (AC4).** No deploy surface sets a
`PLAN_*` override — `docker-compose.staging.yml` says so and the test above greps
every compose file, workflow, `.env*` and deploy script to keep it that way. The one
sanctioned override is `apps/frontend/test-e2e.sh`, where every e2e test shares one
user (#550).

**`TrainingCeilings` are unchanged.** They bound CPU per run (the wall clock is what
the training cost above is priced from) and FREE's must stay ≥ the `comprehensive`
preset (#500); nothing in the measurement argued for moving them.

## Operator steps (AC2)

Stripe objects are created in the dashboard, not by code:

1. Products → **Pro**, recurring price **$49.00 USD / month** → copy the `price_…`
   id into `STRIPE_PRICE_PRO`.
2. Optionally an **Enterprise** product with a placeholder recurring price; its id goes
   in `STRIPE_PRICE_ENTERPRISE` only when a deal is to be entitled through checkout.
   Unset, the backend answers 503 for an ENTERPRISE checkout, which nothing in the UI
   requests.
3. Provision both on staging per #598 (`docker-compose.staging.yml` already passes
   them through, optional until set).

## Consequences

- The pricing page (#475) states this table from `apps/frontend/lib/billing/plans.json`,
  which `tests/test_billing/test_pricing_source_matches_plans.py` holds equal to
  `plans.py` and to the price column above.
- Reverting `OPENAI_MODEL` to a gpt-4-class model is safe for margin at these limits
  but not free; the worst-case table above is the bill.
- #728 (three feature-suggestion routes charge an `ai_calls` unit for a cache read)
  matters more now that FREE has 30 calls; it is the next thing to fix on this surface.
