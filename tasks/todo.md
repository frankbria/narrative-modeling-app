# #475 — [P0.32] Build a pricing page (self-authored plan)

Branch: `feature/issue-475-pricing-page` (from `main` @ edb2625)

## Decisions (autonomous, no architectural fork)

- **Shared source = a static JSON, not a public backend route.** The issue offers either
  "a JSON built from plans.py/ADR-003" or a public `GET /billing/plans`. JSON wins on the
  ponytail ladder: no runtime dependency on the backend for a marketing page, no new
  unauthenticated route in an authenticated router, statically buildable (Docker build has
  no backend), and the landing page (#766) imports the same file. Drift guard: a backend
  pytest loads the JSON and compares every tier/metric to `plans.PLAN_LIMITS` and the price
  column to the ADR-003 table — the same cross-repo pattern as `test_refund_window.py`.
- **Public exemption is an exact-path allowlist** (`/pricing`), not a prefix (#766 AC1 wording,
  CLAUDE.md `/legal/` note). `/pricingx`, `/pricing/x` stay protected.
- **ENTERPRISE renders "Contact us"** (mailto `COMPANY.supportEmail`), never a price (ADR-003 AC3).
- Landing-page link (AC5 first half) lands with #766 — there is no landing page yet; footer link now.

## Steps

1. `apps/frontend/lib/billing/plans.json` + `lib/billing/plans.ts` (typed access, `priceLabel`, `limitLabel`).
   Test: `apps/backend/tests/test_billing/test_pricing_source_matches_plans.py` (limits == plans.py, prices == ADR-003).
2. `middleware.ts`: exact-path public set. Test: `__tests__/middleware.test.ts` (`/pricing` passes w/o token; lookalikes redirect).
3. `app/pricing/page.tsx` (server component, metadata, 3 tiers from the JSON, limit semantics: 402, no queue/overage,
   calendar-month reset; enterprise contact; CTA → `/auth/signin`). Test: `__tests__/app/pricing.page.test.tsx`
   asserts every number from the JSON appears (page can't hard-code).
4. `app/settings/billing/page.tsx`: price on the upgrade button + "Compare plans" link to `/pricing`.
   Test: `__tests__/app/settings/billing.page.test.tsx`.
5. `components/SiteFooter.tsx`: Pricing link. Test: `__tests__/components/SiteFooter.test.tsx`.
   (`routeReachability.test.ts` then sees `/pricing` via the href.)
6. `e2e/workflows/public-pricing.spec.ts` `@smoke`: anonymous `/pricing` → 200 + heading + price; `/pricingx` → 307 sign-in.
7. Docs: CLAUDE.md public-pages note; ADR-003 consequence line.

## Acceptance criteria

- [ ] AC1 public `/pricing`, anonymous-reachable, each tier + price + limits
- [ ] AC2 limits kept in sync with `plans.py` by a test
- [ ] AC3 billing settings shows the price before the Stripe redirect
- [ ] AC4 at-the-limit behaviour stated plainly (402, not queued, no overage)
- [ ] AC5 footer link (landing link → #766)
- [ ] (comment) one source shared with landing + billing; ENTERPRISE = contact us
