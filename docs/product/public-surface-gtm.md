# Public surface and go-to-market: needs analysis and spec

- **Status:** Accepted as the scope of epic [#764](https://github.com/frankbria/narrative-modeling-app/issues/764)
- **Date:** 2026-09-16
- **Follows:** [ADR-003](../architecture/ADR-003-plan-limits-and-pricing.md) (prices and limits are decided; this is what carries them to a stranger)

## 1. The question

With real prices set, are there product pages to update? No, because there are none: `/` redirects to the dashboard, the middleware exempts only `/auth/` and `/legal/`, and the one upgrade button lives behind login. So the real question is what a public surface has to do for the product to *succeed* — acquire strangers, turn them into activated users, convert some to paying, and survive the cost and abuse that open doors bring. This document answers that against the code as it is, not as the older planning documents describe it.

## 2. Evidence: where the product stands, stage by stage

The funnel is discover → understand → trust → try → activate → convert → pay → stay, with measurement and protection underneath. Findings are from a read-only inventory of the repo on 2026-09-16; file references are the proof.

| Stage | What exists | What is missing or wrong |
|---|---|---|
| **Discover** | Favicons; a signed-out root layout that renders without app chrome (`app/layout.tsx:80-91`); a footer with Terms, Privacy and the AGPL source offer. | No public page (`middleware.ts:39-55`, matcher `:120-125`). No `metadataBase`, OG/twitter cards, robots, sitemap, manifest. No logo. No production hostname anywhere; every `NEXTAUTH_URL` example is localhost. Three product names in the UI (`layout.tsx:18`, `Sidebar.tsx:92`, `onboarding_service.py:578`). |
| **Understand** | One good tagline (`README.md:5`); four personas (`PRODUCT_REQUIREMENTS.md:13-32`); live in-product copy that describes AutoML honestly (visible in `model-ready.png`). | No competitor named anywhere; no differentiation written down. `USER_STORIES.md` and `APPLICATION_FUNCTIONALITY_GUIDE.md` promise 100 GB uploads, database connectors, multi-file joins and label shipped features "planned". |
| **Trust** | Terms and Privacy (#473); a sub-processor table traceable to code (`lib/legal/company.ts:47-76`); a 14-day refund enforced from `first_paid_at` (#602); PII scanned and masked before anything reaches a model (#608/#490); every AI feature has a rule-based fallback (#461); a thorough erasure cascade (#480/#497). | None of that is on a page a buyer can read. `/api/v1/docs/*` describes endpoints that do not exist (#512). |
| **Try** | Google and GitHub OAuth (`auth.ts:65-70`); invite allowlist on both halves (#261). | `INVITE_ALLOWLIST` empty means **open** (`lib/invite-allowlist.ts:42`, `nextauth_auth.py:88-89`); only the compose `${VAR:?}` guard keeps it closed. `/api/auth/*` is unthrottled at nginx, Next and FastAPI. No email provider; `/auth/verify-request` is dead UI. `/auth/new-user` is two buttons with no value proposition. Request-access is `mailto:beta@narrativeml.com` (`app/auth/error/page.tsx:17`), a test-fixture domain. |
| **Activate** | Forced six-step onboarding with sample loading that writes a real S3 object (#541); a working feedback widget (`/api/v1/feedback`); a quickstart reference page. | Sample CSVs are **14 rows** each (`apps/backend/sample_datasets/`) while the catalogue says 10 000 (`onboarding_service.py:246`); the required "train your first model" step runs cross-validated AutoML on 14 rows. Welcome `video_url` has no file (`:595`). Docs links point at `docs.narrativemodeling.ai`, which exists nowhere else. Dashboard empty state is one sentence. |
| **Convert** | The 402 body carries `metric`, `limit`, `used`, `resets_at`, `upgrade_available` (`enforcement.py:99-116`); the billing page has an 80 % amber bar and the Upgrade button. | Exactly one frontend call site reads a 402 (`app/api/chat/route.ts:73-74`). Fifteen hand-rolled fetch wrappers throw `HTTP 402` as a string. Nothing links a denial to `/settings/billing`. The Upgrade button states no price (#475). |
| **Pay** | Checkout, portal and webhook work end to end (#457/#597, test-mode rehearsal in #598). | `?checkout=success` is written by `lib/services/billing.ts:54` and read by nobody. Checkout sends six params: no `customer_email`, `allow_promotion_codes`, `automatic_tax`. No trial/annual/promo/tax decision recorded. |
| **Stay** | Stripe receipts and dunning mail. Portal cancel. | No job-completion or 80 %-quota mail (#494). Reconciliation script exists but is unscheduled (#606). |
| **Measure** | `OnboardingProgress`, `UsageRecord` (per-period aggregates), `PredictionEvent` (30-day TTL). Backend Sentry optional (`observability.py:118-131`). Prometheus `/metrics`. | No product or web analytics, no frontend error tracking, no event stream, no way to count users from the backend (accounts live only in NextAuth's `users`). Quota denials log at INFO only. The privacy policy (`privacy/page.tsx:175-183`) promises a consent mechanism before any analytics. |
| **Protect** | Per-user quotas on four metrics (ADR-003); per-key rate limits on the serving surface; circuit breaker on OpenAI. | No global or daily ceiling on anything; the post-upload summary is unmetered (`upload.py:205`, `secure_upload.py:291`); storage has no per-tenant cap and no retention (#529). Worst case ≈ $5 × N free accounts per month, N chosen by whoever scripts signups. |

## 3. Needs, derived

1. **Decide before writing.** Name, positioning, primary persona, signup model and hostname are owner decisions; every page and most copy depend on them. Recommended defaults are in #765.
2. **A public route mechanism that cannot leak.** The `/legal/` lesson stands: a prefix makes every future file under it public by construction. The landing page uses an exact-path allowlist.
3. **Copy that is provably true.** The product already lost credibility once on the deploy page (#511 removed five fabricated infrastructure claims and an invented price). Every proof point must be traceable to code, the way `SUB_PROCESSORS` rows are; the do-not-claim list in §6 is binding.
4. **A conversion path from the moment of denial.** The backend already says "upgrade available"; the frontend has to hear it. One error type, one dialog, every metered surface, plus a real confirmation after checkout.
5. **Backstops sized before the door opens.** An explicit signup mode that fails closed, a global daily AI-call ceiling that degrades to the rule-based fallbacks, edge rate limits on `/api/auth/`, a per-tenant storage ceiling, and a count of new accounts per day. ADR-003 bounded the per-account cost; these bound the aggregate.
6. **Measurement that respects the published policy.** Server-side product events (no client tag, no consent problem), frontend error tracking with PII scrubbed, and cookieless web analytics on the public pages only, with the sub-processor table and privacy paragraph updated in the same change.
7. **An honest first run.** Real sample datasets that actually train, no dead links, one name, an empty state that tells the user what to do.
8. **Production, then Stripe live.** #476 first; then the live-mode cutover with a first real charge and refund drill.

## 4. Decisions required (owner)

| # | Decision | Recommended default | Recorded in |
|---|---|---|---|
| D1 | One product name | pick one of the three; apply everywhere | #765 |
| D2 | Positioning and primary persona | the churn-prediction analyst; the shipped sample, both screenshots and the 0.82 score already tell that story | #765 |
| D3 | Signup model at launch | **open, OAuth-only**, switched on only after #768 lands; invite + request-access form is the alternative | #765, #476 AC7 |
| D4 | Production hostname | a subdomain of the company domain already carrying support mail | #765, #476 |
| D5 | Launch features: A/B testing, recipes, data-issues UI | hide until #502 / #738 / #635 are decided | #765 |
| D6 | Trial, annual price, promo codes, tax | none / not yet / yes / Stripe Tax if selling outside the US | #771 |
| D7 | Analytics approach | server-side events + cookieless public-page analytics; no tag inside the app | #769 |
| D8 | Email vendor | needed for welcome/quota/dunning; not a launch blocker under D3 = open | #494 |

## 5. Definition of success

Targets are hypotheses to instrument (#769) and revise, not promises.

| Metric | Target |
|---|---|
| Landing visitor → account | ≥ 3 % |
| Account → first trained model within 7 days | ≥ 40 % |
| Time from account to first model on the sample path | ≤ 10 minutes |
| Activated FREE → PRO within 30 days | ≥ 3 % |
| Worst-case cost per free user-month | ≤ ≈ $5 (ADR-003), aggregate bounded by the daily ceiling |
| Quota denials that show an upgrade path | 100 % of metered surfaces |
| Frontend errors with a stack trace in the tracker | 100 % (Sentry) |

## 6. Do-not-claim list

Binding on every public page. Each item is either removed code, a 501, or a documented gap:

auto-scaling · auto-provisioning · global or low-latency infrastructure · per-request pricing (all five removed in #511) · 100 GB uploads (cap is 100 MB) · database or cloud-storage connectors · multi-file joins · a broad transformation library (four types execute, #499) · per-dataset chat (`POST /ai/chat/{file_id}` is 501) · guaranteed ONNX/PMML export (ONNX is 501 in the image; PMML needs Java) · any sample-dataset row count · recipes, A/B testing or data-issues detection until #738, #502 and #635 are decided.

What can be claimed, and where the proof is: no-code end to end in eight guided stages (`lib/types/workflow.ts`); auto-detected problem type and about ten cross-validated algorithms with an explanation of the winner (`automl_engine.py`, `algorithm_selector.py`); SHAP explanations; PII scanned before anything reaches a model (#608); works fully without an AI key (#461); version history with undo/redo (#629); self-contained Python and Docker exports (#632); secured REST prediction endpoint with API keys and rate limits (#455); drift monitoring (#488); one-click data erasure (#480); 14-day refund (#602); a free tier sized for one complete run (ADR-003).

## 7. Risk register

| Risk | Mechanism | Mitigation |
|---|---|---|
| Free-tier farming | N OAuth accounts × ≈ $5 worst case | #768: global daily AI ceiling → fallbacks; per-day account count alert; storage cap |
| Credential-stuffing or callback abuse | `/api/auth/*` unthrottled | #768 AC3: nginx `limit_req_zone`; `RATE_LIMIT_TRUST_PROXY` set |
| False advertising | copy drifts from code (happened on the deploy page) | §6 list; traceable proof points; #475 reads limits from the ADR-003 source |
| Privacy-policy breach | adding a tag-based analytics tool | #769 AC5: cookieless, public pages only, policy + sub-processor row updated first |
| Paying without entitlement | live webhook misrouted (the #456 class) | #771 AC3–AC4: verify the deployed nginx file; first-charge drill |
| Activation failure | 14-row samples cannot train meaningfully | #770 AC1–AC2: real samples; e2e proves step 4 |
| Launching blind | no funnel data | #769 AC1–AC2 before flipping signup open |

## 8. Issue map and sequencing

New (this analysis): #764 epic · #765 decisions (P0.36) · #766 landing (P0.37) · #767 402 experience (P0.38) · #768 backstops (P0.39) · #769 telemetry (P1.51) · #770 onboarding (P1.52) · #771 Stripe go-live (P1.53) · #772 trust pages (P2.54).

Pre-existing, linked: #475 pricing page (P0.32) · #476 production environment (P0.33) · #299 backups (P0.34) · #598 Stripe test keys · #494 email · #529 S3 lifecycle · #512 API docs · #502 A/B fate · #738 recipes nav · #635 data-issues UI · #557 Atlas allowlist · #595 webhook edge cap · #606 reconciliation schedule · #728 cache-read `ai_calls`.

Order:

1. #765 (owner, days). Unblocks all copy.
2. Now, in parallel, no decision needed: #767, #769, #768 AC1–AC3, #476.
3. #766, #475, #770 once #765 lands; ship to staging behind the invite gate.
4. #771 once #476 and #598 are done; #772 once #766's route mechanism exists.
5. Switch `SIGNUP_MODE=open` (if D3 = open) only after #768 and #769 AC1–AC3 are live in production.

## 9. What this document is not

It is not a marketing plan (channels, content calendar, launch announcement) and not a pricing revision; ADR-003 owns the numbers. When D1–D8 are decided, the positioning document lands beside this file and the pages are written from it.
