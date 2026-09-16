# #474 — Replace placeholder plan limits and set real prices

Plan source: self-authored (issue has ACs, no implementation plan). Status: decided (PRO $49, ENTERPRISE contact-us, FREE ≈ $5 budget, model default → gpt-4o-mini); implemented in PR #763.

## AC1 evidence — unit economics (worst case per unit, list prices of the models the code configures today)

Inputs (verified in code):
- `ai_calls` unit = one OpenAI completion. Defaults: `OPENAI_MODEL` → gpt-4 (`ai_summary.py:34`, feature suggestions `feature_engineering_service.py:60`) or gpt-4-turbo (`dataset_summarization.py:62`, chat, orchestration, report card). Prompts ship the full column list (+5 examples/column) or up to 5 sample rows; `max_tokens` 300–2500. Circuit breaker may retry 2–3x.
- `uploads` unit = parse + S3 put (≤100 MB) + **one unmetered gpt-4 summary in a background task** (`upload.py:205`, `secure_upload.py:291-298`). An upload costs an AI call that `ai_calls` does not count.
- `training_runs` unit = CPU only, no OpenAI. Hard wall clock FREE 3 600 s / PRO 7 200 s / ENT 14 400 s at `TRAINING_MAX_N_JOBS=2` cores. S3 artifacts: model, transformer, eval JSON, shap JSON (no byte cap; scales with `max_features`).
- `predictions` unit = vectorised sklearn predict + one `PredictionEvent` row (30-day TTL). No OpenAI.

| Unit | Driver | Worst case | Typical |
|---|---|---|---|
| ai_call (gpt-4, ~2k in / 1k out) | $30/M in, $60/M out | ~$0.12 (×2–3 on retry) | ~$0.05 |
| ai_call (gpt-4-turbo, ~3k in / 1k out) | $10/M in, $30/M out | ~$0.06 | ~$0.03 |
| upload | 1 unmetered gpt-4 summary + S3 (100 MB ≈ $0.002/mo) | ~$0.12 | ~$0.05 |
| training_run | 2 cores × wall clock at ~$0.02/core-hr shared VPS | FREE $0.04, PRO $0.08, ENT $0.16 | <$0.01 (minutes) |
| prediction | CPU µs + Mongo insert | ~$0.00001 | ~$0.000005 |

Worst-case monthly exposure per tenant at the **current placeholders**:

| Tier | ai_calls | uploads | training | predictions | Total/month |
|---|---|---|---|---|---|
| FREE (100 / 20 / 10 / 1k) | $12 | $2.40 | $0.40 | $0.01 | **≈ $15** |
| PRO (5 000 / 500 / 200 / 100k) | $600 | $60 | $16 | $1 | **≈ $680** |
| ENTERPRISE (50 000 / ∞ / ∞ / ∞) | $6 000 | unbounded | unbounded | unbounded | **unbounded** |

Conclusion: `ai_calls` dominates every tier. PRO's placeholder can cost ~10x any plausible PRO price; the AI-call ceilings must be sized from the price, not the other way round. The biggest cost lever is not a limit at all: the default models (gpt-4 / gpt-4-turbo) are 20–100x the price of a current small model. (#728 separately fixes 3 of the 5 feature-suggestion routes charging a unit for a cache read.)

## Fork for the owner (Phase 4 — genuine product decision, no safe default)

1. PRO monthly price.
2. ENTERPRISE at launch: "Contact us" (recommended — no self-serve UI exists, backend keeps the env-driven price so a sales-led deal can still be entitled) vs self-serve at a price.
3. FREE-tier acquisition budget per user-month (drives the FREE ceilings).
4. Whether to also switch the default OpenAI models to a cheaper one in this PR (recommended: yes, it is the lever that makes any PRO price work) or file it separately.

## Recommended numbers (pending the answers above)

| Tier | price | training_runs | predictions | uploads | ai_calls | worst case |
|---|---|---|---|---|---|---|
| FREE | $0 | 5 | 1 000 | 10 | 30 | ≈ $5 |
| PRO | $49/mo | 100 | 100 000 | 200 | 400 | ≈ $75 (≈ $25 typical) |
| ENTERPRISE | contact us | UNLIMITED | UNLIMITED | UNLIMITED | 5 000 (finite) | ≈ $600 + compute, priced per deal |

TrainingCeilings stay as-is (they already bound CPU per run; ENT wall clock 4 h × 2 cores is the worst case above).

## Implementation steps (after the decision)

1. `plans.py`: replace the placeholder docstring + defaults with the decided numbers; update `PLAN_LIMITS` and the ENTERPRISE comment.
2. AC4 guard: `tests/test_billing/test_plan_defaults_are_the_deployed_values.py` — no `PLAN_*=` assignment in any deploy surface (`docker-compose*.yml`, `.env*.example`, `ci.yml`, `deploy.yml`); only `apps/frontend/test-e2e.sh` may set them (e2e shared user). Update `test_training_ceilings.py` / any test pinning the old placeholders.
3. AC3: frontend billing page — ENTERPRISE row renders "Contact us" (mailto from `lib/legal/company.ts`), not a dead tier. Backend checkout for ENTERPRISE stays env-driven (503 when unset) so a sales-led price id works.
4. AC5: `docs/architecture/ADR-003-plan-limits-and-pricing.md` recording the numbers, the unit-economics table above and the reasoning; ADR-002's placeholder paragraph points at it.
5. AC2 (operator): create the Stripe Price objects and set `STRIPE_PRICE_PRO` / `STRIPE_PRICE_ENTERPRISE` (#598 provisions the keys on staging). Document the exact dashboard steps in the ADR.
6. Optional (fork 4): change the model defaults in `ai_summary.py`, `dataset_summarization.py`, `feature_engineering_service.py`, chat/orchestration/report-card services to one cheaper `OPENAI_MODEL`.
7. Update CLAUDE.md billing convention lines that quote the placeholder numbers.

## Acceptance criteria
- [x] AC1 real limits chosen against measured unit economics
- [ ] AC2 Stripe Price ids created and set (operator — dashboard steps in ADR-003; staging provisioning #598)
- [x] AC3 ENTERPRISE decision — contact-us vs self-serve, no dead tier
- [x] AC4 plans.py defaults == deployed values (guard test)
- [x] AC5 ADR-003 with numbers + reasoning; ADR-002 placeholder note replaced
- [x] AC6 FREE tier worst case ≤ the acquisition budget
