# ADR-002: Build the billing surface (supersedes ADR-001)

- **Status:** Accepted
- **Date:** 2026-08-02
- **Supersedes:** [ADR-001](./ADR-001-billing-deferred-free-invite-beta.md)
- **Implements:** [#370](https://github.com/frankbria/narrative-modeling-app/issues/370) (epic) and its children #365–#369

## Context

ADR-001 deferred billing on the grounds that the launch was a free invite-only beta,
that abuse control was already handled by the invite gate (#261), and that building
payments before anyone could pay for anything was work without a customer.

That reasoning was sound for the beta. It stopped being the operative decision once
paid conversion was scheduled: the epic was explicitly written as "post free-beta",
and that point has arrived.

Leaving ADR-001 as the only record would be worse than either decision. An ADR that
says billing is deferred, sitting beside shipped billing code, is a stale record that
misleads the next reader — so ADR-001 is marked superseded rather than edited to
pretend it always said this.

## Decision

Build the billing surface as scoped in #370:

| Concern | Where |
|---|---|
| Subscription state | `app/models/subscription.py` |
| Plan limits | `app/billing/plans.py` |
| Usage metering | `app/billing/` (#369) |
| Stripe sync | webhook (#367) |
| Checkout / portal | (#365) |
| Enforcement | FastAPI dependency (#368) |

### Decisions worth recording, because they are not obvious

**Plan limits are configuration, not schema.** They live in `app/billing/plans.py`
with env overrides, not on the `Subscription` document. A limit is a product decision
that changes without a migration; the document records what a tenant actually bought.

**The tier numbers are an assumption.** #365–#369 specify the mechanism and never the
tiers, limits or pricing. The defaults (free 10 training runs / 1,000 predictions /
20 uploads per period; pro 200 / 100,000 / 500; enterprise unlimited) were chosen so
the invite-only beta stays usable the moment enforcement is switched on. **They are
placeholders and should be replaced with real numbers before charging anyone.**

**Entitlement is derived, not stored.** `Subscription.effective_tier` returns FREE
unless the subscription is entitled, so a canceled subscription stops granting the
tier it records without anything having to write to it.

**Past-due keeps access.** Stripe retries a failed payment for days. Cutting a paying
customer off at the first failure is worse than serving them through a card that is
about to be updated. Canceled does not.

**Unknown Stripe statuses fail closed.** Stripe can add statuses; a new one maps to
INCOMPLETE (no access) rather than defaulting to entitled.

**No subscription document means FREE.** Enforcement never depends on a backfill
having run.

## Consequences

- The invite gate (#261) and rate-limit middleware (#151) stay. Plan enforcement
  composes with them rather than replacing them, as #368 requires.
- Stripe secrets are env-provided and the client is lazy-initialised, so secret-less
  Docker builds stay green — the trap recorded in the frontend Docker note.
- Anything not paid for still works: with no Stripe keys configured, the app runs
  exactly as it does today, on FREE limits.
