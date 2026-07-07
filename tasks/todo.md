# Issue #261 (P0.11) — Invite allowlist signup gate

**Plan source:** self-authored (no plan comment). No architectural fork → proceeding autonomously.

**Goal:** Restrict the invite-only beta so only allowlisted emails can sign in / consume compute.

## Design decision
- **Env allowlist** (`INVITE_ALLOWLIST`, comma-separated emails), NOT a Mongo `Invite` collection.
  AC permits either; env list is sufficient for a small beta cohort and far less code. (YAGNI)
- **Gate off when the var is empty** (preserves dev/test + un-configured deploys) — fail-closed is
  enforced at the *deploy* layer via `${INVITE_ALLOWLIST:?}` in staging compose, mirroring #256/#257.

## Steps (TDD)
1. **Frontend** `lib/invite-allowlist.ts` — pure `isEmailAllowed(email)` (case-insensitive, trimmed;
   empty list ⇒ allow). Test: `__tests__/lib/invite-allowlist.test.ts`.
2. **Frontend** `auth.ts` `signIn` callback → `isEmailAllowed(user.email)`; `mintApiToken(userId, email)`
   carries the email claim for the backend mirror.
3. **Frontend** `app/auth/error/page.tsx` — clear invite-only "request access" message for `AccessDenied`.
4. **Backend** `config.py` — pure `parse_invite_allowlist(raw)` + `is_email_allowed(email, allowlist)`.
   Test: `tests/test_security/test_invite_allowlist.py`.
5. **Backend** `nextauth_auth.py` `get_current_user_id` — when allowlist set AND token has `email`,
   403 if not allowed (defense-in-depth; absent email falls through — signIn is the real gate).
   Test: extend `tests/test_auth/test_nextauth.py`.
6. **Docs/config** — `.env` examples, staging compose `${INVITE_ALLOWLIST:?}` guard,
   and a "How to add invitees" section in the deployment guide.

## Non-goals
- No Mongo Invite collection / CRUD UI. No self-serve request-access form (message + email link only).
