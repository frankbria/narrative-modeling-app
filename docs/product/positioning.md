# Positioning

- **Status:** Signed 2026-10-02 (D1/D4); D2, D3, D5 signed 2026-09-18 (decisions D1–D5 of [#765](https://github.com/frankbria/narrative-modeling-app/issues/765); clearance in #793)
- **Date:** drafted 2026-09-16, signed 2026-10-02
- **Follows:** [public-surface-gtm.md](./public-surface-gtm.md) (§4 decisions D1–D8) and [ADR-003](../architecture/ADR-003-plan-limits-and-pricing.md)
- **Feeds:** #766 landing page, #475 pricing page, #770 onboarding copy, #772 trust pages
- **Location:** `docs/product/positioning.md`

Every claim below is either traceable to code (file or issue cited) or listed under "do not claim." Copy on any public page is written from this document, not from `USER_STORIES.md` or `PRODUCT_REQUIREMENTS.md`.

## 1. Product name (D1)

**SheetPredict.** Public site `sheetpredict.app`, product `app.sheetpredict.app`, serving surface `api.sheetpredict.app`.

Rationale: `narrativeml.com` is registered and in use by an unrelated ML consultancy; "NarrativeML" is an academic markup language; "narrative modeling" is a dbt data-modeling term; NARRATIVE SCIENCE (Reg. 5865083, Cl. 9/42) is a registered mark for AI software; and "narrative + data" reads as text generation, not prediction. SheetPredict says exactly what the product does and searches well. Foresheet was the evocative alternative, not taken. `sheetpredict.app` registered 2026-10-02; `sheetpredict.com` is registered (2025-12-30, Cloudflare) with no live site. `.app` is HSTS-preloaded, so every host on it is HTTPS-only in browsers.

Apply everywhere: `app/layout.tsx:18`, `Sidebar.tsx:92`, `onboarding_service.py:578`, `lib/legal/company.ts:23`, `auth/signin`, `auth/new-user`, `quickstart`, `dashboard`, `main.py:414`, `api_documentation.py` (remove `narrativeml.com` hosts and mail), `api_version.py` vendor media type, `auth/error/page.tsx:17` (`beta@narrativeml.com`), `onboarding_service.py` docs links (`docs.narrativemodeling.ai`).

Pre-commit checks: USPTO tmsearch for the exact word in Classes 9 and 42 (owner, pending); domain registered before the name appears in any commit (done, `.app`). Common-law search (2026-10-02): no active product using the name.

## 2. One-sentence value proposition

**SheetPredict turns a spreadsheet into a validated, explained, deployable model in minutes — and shows its work.**

Long form: For applied researchers and analysts who have to defend a prediction, SheetPredict takes a CSV or XLSX, cross-validates about ten algorithms, explains the winner with SHAP, keeps a reproducible history, exports the model as self-contained Python or Docker, and serves it from a secured prediction endpoint — on a free tier sized for one complete run.

Tagline for `<title>` and OG: **Explained predictions from your spreadsheet.**

## 3. Primary persona (D2)

**The applied researcher.** Doctoral student, postdoc, clinical or social-science research coordinator, institutional-research analyst. Has a flat tabular dataset; has a reviewer, committee or PI who will ask "why this model and what drives it?"; uses SPSS, JASP, Orange or copied R today; cannot write Python fluently; must not put identifiable rows into a chat window; pays $8–25/month from a grant or personal card.

**Secondary persona:** the analyst at a 50–2,000-person organisation with no data-science team who has been asked for a churn, attrition, renewal or demand model that a stakeholder will not accept as a black box. The shipped churn sample and existing screenshots tell this story.

**Growth persona (not on the landing page yet):** the AI-native builder who wants "train, explain, deploy a tabular model" as a primitive callable from an agent (`apps/mcp`, currently one EDA tool).

**Anti-personas:** enterprise data teams; merchants whose churn is bundled into Shopify/HubSpot; anyone whose data lives only in a warehouse.

## 4. Three proof points

| Proof point | Copy | Evidence |
|---|---|---|
| Validated, not vibes | "About ten algorithms, cross-validated, with an explanation of why the winner won." | `automl_engine.py`, `algorithm_selector.py` |
| Explained and reproducible | "SHAP explanations for every model, a full version history, and a self-contained Python or Docker export you own." | SHAP surface under `/api/v1/ml/`; #629 history/undo; #632 exports |
| Safe with real data | "PII is scanned and masked before anything reaches a language model; every AI feature works without an AI key; one-click erasure; AGPL source you can read and self-host." | #608/#490 PII; #461 fallbacks; #480/#497 erasure; `LICENSE`, `README.md` §License |

Supporting claims that may also be used, with evidence: eight guided stages (`lib/types/workflow.ts`); secured REST prediction endpoint with API keys and rate limits (#455); drift monitoring (#488); 14-day refund from first payment (#602); free tier sized for one complete run (ADR-003).

## 5. Contrast statements

- **vs. AI chat assistants (ChatGPT, Claude, Julius):** "They give you a script and a chart. SheetPredict gives you a validated model, its explanation, and an endpoint — and your rows never enter a chat window."
- **vs. cloud AutoML (SageMaker Canvas, Vertex):** "No cloud account, no hourly meter, no IAM."
- **vs. free stats tools (Orange, JASP, jamovi):** "Prediction with SHAP, a written report, an endpoint and export — hosted."
- **vs. enterprise platforms (DataRobot, Dataiku, Pecan):** "For one person with a spreadsheet, not a platform team with a procurement process."
- Do not name Akkio, Obviously AI, Graphite Note or other vendors that no longer sell to this buyer.

## 6. Do-not-claim list (binding; extends public-surface-gtm.md §6)

auto-scaling · auto-provisioning · global or low-latency infrastructure · per-request pricing · uploads above 100 MB · database or cloud-storage connectors · multi-file joins · a broad transformation library (four types execute, #499) · per-dataset chat (`POST /ai/chat/{file_id}` is 501) · guaranteed ONNX/PMML export · any sample-dataset row count until #770 lands · recipes, A/B testing or data-issues detection until #738, #502 and #635 are decided · "replaces your statistics package" (no inference testing) · "better than ChatGPT" · any comparative accuracy claim against a named vendor.

Additionally, publish a short **"What SheetPredict does not do yet"** section on the landing page (CSV/XLSX only, 100 MB cap, no connectors or joins). It is on-brand for a rigor product and filters the buyers we do not want yet.

## 7. Launch surface (D3, D5)

- Signup: **open, OAuth-only**, switched on only after #768 (backstops) and #769 AC1–AC3 (telemetry) are live in production. Invite mode remains available via `SIGNUP_MODE`.
- Hidden at launch: recipes navigation (#738), A/B testing (#502), data-issues UI (#635).
- Shown at launch: eight-stage workflow, leaderboard with baseline row, SHAP, version history, exports, endpoint, billing page with the ADR-003 table.

## 8. Pricing surface (for #475; numbers owned by ADR-003)

Proposed revision to ADR-003, for a separate decision: Free (unchanged) · Individual $24/mo ($19 annual) · Academic $8/mo with verified institution email · Team/API $99/mo · Enterprise contact. The user-facing value metric is **models per month and predictions**, with `ai_calls` as a hidden backstop. Until ADR-003 is amended, the pricing page states the current table (Free / Pro $49 / Enterprise) verbatim from `app/billing/plans.py`.

## 9. Where "narrative" lives now

Not in the name. It names one feature: the **Narrative** — a generated, exportable model report (data description, preprocessing steps, algorithms tried with CV scores, winner and why, SHAP drivers, caveats, reproducibility appendix). Tracked in #795; it is the primary conversion asset for the primary persona.

## 10. Owner sign-off

| Decision | Choice | Signed |
|---|---|---|
| D1 Name | SheetPredict | 2026-10-02 |
| D2 Persona | Applied researcher primary; defend-the-number analyst secondary | 2026-09-18 |
| D3 Signup | Open OAuth after #768/#769 | 2026-09-18 |
| D4 Hostname | sheetpredict.app / app.sheetpredict.app / api.sheetpredict.app | 2026-10-02 |
| D5 Hidden features | recipes, A/B, data-issues | 2026-09-18 |
