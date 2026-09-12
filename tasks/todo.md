# Issue #613 — [P3.27] [testing] Smoke-test that an authenticated non-admin gets HTTP 404 on /admin

Plan source: self-authored. Approved autonomously — the only design question is how one e2e run holds both a non-admin and an admin session; a second dev-credentials identity (test/dev only) is the smallest answer. No fork.

## Findings
- `middleware.ts` rewrites `/admin` to Next's internal `/_not-found` for emails not on `ADMIN_EMAILS`; the unit test can only see the rewrite header. Nothing in CI observes the final HTTP status.
- The dev credentials provider (`auth.ts`, dev/test only) accepts exactly one identity (`TEST_USER_EMAIL`), so the same run cannot be both a non-admin and an admin unless a second identity exists.
- `test-e2e.sh` does not export `ADMIN_EMAILS`; "nobody is admin" is incidental today.

## Design
1. `auth.ts` credentials provider (already gated to development/test) also accepts `TEST_ADMIN_EMAIL` / `TEST_ADMIN_PASSWORD` when both are set, returning a distinct user id. Unit-tested.
2. `test-e2e.sh` exports `TEST_ADMIN_EMAIL` (default `admin-e2e@narrativeml.com`), `TEST_ADMIN_PASSWORD`, and `ADMIN_EMAILS=${ADMIN_EMAILS:-$TEST_ADMIN_EMAIL}` — deliberately, with the comment the issue asks for; the ordinary test user is therefore not an admin by construction.
3. `e2e/workflows/admin-guard.spec.ts` (@smoke): (a) the default session (test user) → `page.request.get('/admin')` is 404 and the body has no "Admin Dashboard"; (b) a fresh context signs in through the real form as the admin identity → 200 and the heading is present.
4. CLAUDE.md `/admin` bullet: the smoke spec now repeats the hand check.

## Steps
- [ ] RED (spec fails: admin identity cannot sign in / no ADMIN_EMAILS)
- [ ] provider + launcher + spec + docs
- [ ] gate (jest, tsc, lint cap) → PR → CI e2e-smoke is the demo → merge
