# Issue #477 — [P1.1] [security] /admin has no authorization check and no admin role exists

Plan source: self-authored (no plan comment). No architectural fork; approved autonomously.

## Design

- **Admin concept = `ADMIN_EMAILS` env allowlist**, checked server-side (`lib/admin-allowlist.ts`), mirroring `lib/invite-allowlist.ts` — but **fail closed**: an empty/unset list means *nobody* is admin (the invite gate's empty-means-open default is wrong for an admin check).
- **Server guard in `middleware.ts`**: after the session check, requests to `/admin` or `/admin/*` whose token email is not on the list are rewritten to a non-existent path so Next renders its 404 — no existence oracle, same answer as a page that isn't there. Middleware is already the auth chokepoint and covers future `/admin/*` routes automatically.
- **Sidebar link only for admins**: the client cannot read `ADMIN_EMAILS`, so the NextAuth `session` callback sets `session.isAdmin` server-side and `Sidebar` renders the link only when it is true. Type augmented in `types/next-auth.d.ts`.
- **Backend (AC3)**: the admin page calls only `/health/status` and `/health/metrics`, neither of which exists (#479). There is no live endpoint to guard; #479 must add an admin dependency when it creates them — comment there post-merge.
- Env plumbing: `.env.local.example`, `.env.staging.example`, and the frontend service in `docker-compose.staging.yml` (`${ADMIN_EMAILS:-}`, optional until provisioned per #457).

## Steps

1. [ ] `lib/admin-allowlist.ts` — `isAdminEmail(email, raw = process.env.ADMIN_EMAILS)`; tests in `__tests__/lib/admin-allowlist.test.ts`.
2. [ ] `middleware.ts` — admin prefix guard; tests in `__tests__/middleware.test.ts` (non-admin → 404 rewrite; admin → passes; unset list → 404 for everyone; `/administration` not affected).
3. [ ] `auth.ts` session callback sets `isAdmin`; `types/next-auth.d.ts` gains `isAdmin?: boolean`.
4. [ ] `components/Sidebar.tsx` renders the Admin link only when `session?.isAdmin`; tests in `__tests__/components/Sidebar.test.tsx`.
5. [ ] Env: `.env.local.example`, `.env.staging.example`, `docker-compose.staging.yml` (frontend service).
6. [ ] Docs: CLAUDE.md frontend section — the `/admin` guard and the fail-closed allowlist.

## Acceptance criteria

- [ ] AC1 admin concept exists (`ADMIN_EMAILS`, server-side)
- [ ] AC2 `/admin` server-guarded (middleware, not a client check)
- [ ] AC3 backend endpoints the UI calls enforce the check — none exist today; recorded + #479 comment
- [ ] AC4 sidebar link only for admins
- [ ] AC5 test: authenticated non-admin gets 404 on `/admin`

## Known limitation

`ADMIN_EMAILS` is not yet provisioned on staging; until the operator sets it, nobody is admin and `/admin` 404s for everyone — which is the safe direction. The tiles the page shows are fabricated (#478) and stay so; this issue only stops them being customer-visible.
