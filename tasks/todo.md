# #780 — Provision SIGNUP_MODE in .env.staging, then make compose require it (P1.54)

Plan follows the owner's steps on the issue. One decision made here: AC3 is closed
now, not at the `open` switch. Compose cannot say "required only in invite mode", so
`INVITE_ALLOWLIST` becomes `${…:-}` and the preflight keeps the guard: it refuses a
`SIGNUP_MODE` that is not `invite|open`, and refuses `invite` with an empty allowlist
(which would lock every user out, fail-closed but silent).

## Steps
1. Box: append `SIGNUP_MODE=invite` to `.env.staging`, `up -d --force-recreate backend
   frontend`, confirm the backend logs `Signup mode: invite`. Before the merge, because
   the merge deploy's preflight will require the value.
2. RED: `test_staging_signup_env.py` (both services guard `SIGNUP_MODE` with `:?`,
   neither guards `INVITE_ALLOWLIST`, `.env.staging.example` carries `SIGNUP_MODE=`);
   preflight `--self-check` cases for the mode rule.
3. GREEN: compose flip; preflight mode rule; `.env.staging.example`.
4. Docs: STAGING_DEPLOYMENT_GUIDE (variable list, invitee section, checklist), CLAUDE.md
   signup bullet.
5. After merge: deploy.yml green, box still logs the mode.

## Acceptance criteria
- [ ] AC1 `.env.staging` carries `SIGNUP_MODE`; recreated containers log it
- [ ] AC2 compose guards `SIGNUP_MODE` with `:?`; preflight lists it as required
- [ ] AC3 switching to `open` needs no dummy `INVITE_ALLOWLIST`
