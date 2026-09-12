# Issue #527 — [P2.30] [security] /api/data/[id]/preview forwards the OAuth provider token as the backend bearer

Plan source: self-authored (no plan comment). No architectural fork; approved autonomously.

## Design

- **Every backend call carries the minted API JWT (`session.apiToken`) and nothing else.** The preview proxy route drops the `getToken` fallback and the `"default"` literal: no session or no `apiToken` → 401, nothing forwarded.
- **The provider token stops reaching the client at all.** `auth.ts` no longer copies `account.access_token` into the JWT or `session.accessToken`; the type is removed. Nothing legitimately needs a Google/GitHub credential in the browser, and removing the field is what makes the sweep durable.
- **Sweep (AC4)** found three more offenders: `app/api/store/route.ts` (placeholder `nextauth-<id>` bearer, wrong URL, **no callers** → deleted, plus its dead `NEXT_PUBLIC_BACKEND_URL` example line), `components/FeatureSelection.tsx` and `hooks/useDataIssues.ts` (provider token client-side → `apiToken`). A guard test greps the frontend for `session.accessToken`, `Bearer nextauth-` and `|| 'default'` so the class of bug cannot return.
- **AC3** is a backend unit test: `Bearer default` → 401 under `SKIP_AUTH=false` (pattern: `test_legacy_nextauth_prefix_token_rejected`).

## Steps

1. [ ] Tests first: preview route test (correct bearer; no session → 401 + no fetch; no apiToken → 401), auth session-callback test (apiToken present, accessToken absent, provider token not persisted in the JWT), FeatureSelection mock → `apiToken`, forwarding guard test, backend `default` rejection test.
2. [ ] Preview route: `session.apiToken` only.
3. [ ] Delete `app/api/store/route.ts`; drop `NEXT_PUBLIC_BACKEND_URL` from `.env.local.example`.
4. [ ] `FeatureSelection.tsx`, `useDataIssues.ts` → `session.apiToken`.
5. [ ] `auth.ts` + `types/next-auth.d.ts`: remove the provider access token from JWT and session.
6. [ ] Docs: CLAUDE.md frontend bullet.

## Acceptance criteria

- [ ] AC1 route sends the minted API JWT
- [ ] AC2 `"default"` fallback removed; missing session → 401
- [ ] AC3 backend rejects `default` under a production-like config (test)
- [ ] AC4 frontend swept (3 more sites fixed; guard test)
- [ ] AC5 tests: correct token sent; missing session → 401
