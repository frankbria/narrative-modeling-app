# ADR-001: Launch as a free invite-only beta; defer billing

- **Status:** Superseded by [ADR-002](./ADR-002-billing-implemented.md) (2026-08-02)
- **Date:** 2026-07-23
- **Resolves:** [#289](https://github.com/frankbria/narrative-modeling-app/issues/289) (P2.12 — Billing / subscription / metering epic)
- **Related:** #261 (invite-only beta gate, shipped)

> **Superseded.** The deferral below was correct for the free invite-only beta, and
> the reasoning is kept for the record. Billing was subsequently scheduled and built
> under epic #370; see ADR-002 for what shipped and which parts of this decision it
> reverses. Do not cite this ADR as a reason not to build billing.

## Context

The SaaS launch-readiness audit (2026-06-27) flagged that the product is intended
to become a *paid* multi-tenant SaaS but has **no billing system**: no payment
provider, no subscription/plan-tier model, no usage metering, and no
plan-enforcement gate. Every tenant therefore has unlimited access to unbounded
compute (AutoML training, SHAP, batch prediction).

Issue #289 offered two explicit paths:

- **(a)** Build billing now — Stripe Checkout + customer portal, a
  `Subscription`/`plan_tier` model scoped to `user_id`, a webhook to sync
  subscription state, and a plan-enforcement dependency on the metered endpoints
  (train / predict / upload).
- **(b)** Make an explicit, documented decision to launch as a **free
  invite-only beta** with signup gated, and file the billing build as a separate
  post-launch epic.

## Decision

**We choose (b): launch as a free, invite-only beta and defer billing to a
post-launch epic.**

Billing is **not a launch blocker** because the launch does not charge anyone.
Building Stripe integration, a subscription model, and plan enforcement for a
product that collects no revenue is premature — it would ship an unused billing
surface (attack surface, maintenance, and test burden) with no offsetting value.
Billing is built when — and only when — paid conversion is actually scheduled.

## Why this is safe: abuse control is already in place

The audit's underlying concern (unbounded compute exposed to anyone) is
mitigated today by the **invite-only beta gate shipped in #261**, not by billing:

- **Frontend (primary control):** the NextAuth `signIn` callback rejects any
  email not on `INVITE_ALLOWLIST` *before* a session or backend JWT is minted
  (`apps/frontend/auth.ts`, `apps/frontend/lib/invite-allowlist.ts`).
- **Backend (defense-in-depth):** `get_current_user_id` mirrors the same
  `INVITE_ALLOWLIST` check, so a revoked allowlist entry is rejected even if a
  stale token is presented (`apps/backend/app/auth/nextauth_auth.py`,
  `apps/backend/app/config.py`).
- **Fail-closed in production:** staging/production compose requires
  `INVITE_ALLOWLIST` via `${INVITE_ALLOWLIST:?}` (same guard pattern as the
  CORS/S3 deploy guards, #256/#257). An empty/unset list disables the gate only
  for local dev, tests, and CI.

So compute is bounded by *who can sign in*, not by *who has paid*. That is the
correct control for a free beta.

## Consequences

- No payment provider, subscription model, metering, or plan-enforcement code is
  added at launch. `grep -riE 'stripe|billing|subscription|plan_tier|metering'`
  over `apps/` continues to return only domain-modeling vocabulary.
- **Charging money is blocked until the billing epic ships.** The invite gate
  controls access; it does not meter or bill usage. Converting to paid is a
  deliberate, tracked project — see the child issues below.
- If the beta's compute cost becomes a problem *before* paid conversion, the
  lever is tightening the allowlist (or adding coarse per-user rate limits on the
  metered endpoints), not standing up billing.

## Follow-up: the billing build (post-launch epic)

The billing epic is tracked by **#370** ("Paid conversion — billing,
subscriptions & metering"), split into atomic issues to be scheduled when paid
conversion is planned:

1. #365 — Payment provider integration (Stripe Checkout + customer portal)
2. #366 — `Subscription` / `plan_tier` model scoped to `user_id`
3. #367 — Stripe webhook endpoint to sync subscription state (signature-verified)
4. #368 — Plan-enforcement FastAPI dependency on the metered endpoints (train / predict / upload)
5. #369 — Usage metering store (for plan limits and abuse control)
