# SheetPredict Frontend

Next.js 16 (App Router) client for SheetPredict: TypeScript strict, Tailwind CSS v4,
NextAuth v5 (Google, GitHub, plus a credentials provider in development and test).
It talks to the FastAPI backend in `apps/backend`.

## Setup

Requires Node.js `^22.13.0 || >=24` (`engines` in `package.json`; CI uses 22) and npm.

```bash
cd apps/frontend
npm install
cp .env.local.example .env.local   # each variable is documented there
npm run dev                        # http://localhost:3000
```

The backend must be running at `NEXT_PUBLIC_API_URL`, which includes `/api/v1`
(`http://localhost:8000/api/v1`). `MONGODB_URI`, `MONGODB_DB` and `NEXTAUTH_SECRET` must
match the backend's. Full local setup, including MongoDB and LocalStack:
[docs/dev/LOCAL_DEVELOPMENT.md](../../docs/dev/LOCAL_DEVELOPMENT.md).

In development, sign in with the credentials provider as `test@narrativeml.com` /
`test-password-123`.

## Scripts

| Command | What |
|---|---|
| `npm run dev` | dev server |
| `npm run build` / `npm start` | production build and server |
| `npm test` | jest unit tests (`test:watch`, `test:coverage`) |
| `npm run type-check` | `tsc --noEmit` |
| `npm run lint` | eslint over the whole project, warning-capped |
| `npm run test:e2e:smoke` | Playwright `@smoke` specs on the real stack |
| `npm run test:e2e:full` | every Playwright spec on Chromium |

E2E setup and rules: [docs/dev/E2E_TESTING_GUIDE.md](../../docs/dev/E2E_TESTING_GUIDE.md).

## Layout

```
apps/frontend/
├── app/             # routes (App Router); app/api/** are server route handlers
├── components/      # UI, with a folder per large page (dashboard/, predict/, upload/, ...)
├── lib/             # services (API calls), types, auth helpers, billing, legal copy
├── hooks/
├── middleware.ts    # deny-by-default auth, /admin allowlist
├── auth.ts          # NextAuth config; mints the backend API token
├── __tests__/       # jest
└── e2e/             # Playwright
```

Conventions (public paths, dark-mode tokens, API URL construction, error handling) are in
the repo-root [CLAUDE.md](../../CLAUDE.md). This Next.js version differs from older ones;
read [AGENTS.md](AGENTS.md) before changing framework code.

## License

Apache 2.0. See [LICENSE](../../LICENSE) in the repo root.
