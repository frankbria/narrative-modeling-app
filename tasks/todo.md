# #769 AC4 — Frontend Sentry (P1.51)

Scope: AC4 only. AC5 (web analytics) is blocked by #766. AC6 is the owner's to write.

## Steps
1. `lib/observability/sentry.ts`: `sentryOptions(dsn)` returns `undefined` when there is no DSN, which keeps a secret-less build and dev inert. Options: `sendDefaultPii: false`, `tracesSampleRate: 0`, no replay. `beforeSend` = `scrubSentryEvent`, which drops the query string, cookies, headers and user, mirroring the backend's `_scrub_sentry_event`.
2. `instrumentation-client.ts` initialises the browser SDK from `NEXT_PUBLIC_SENTRY_DSN`, which Next inlines at build time. `instrumentation.ts` initialises the server/edge SDK from `SENTRY_DSN` and sets `onRequestError = Sentry.captureRequestError`.
3. `app/global-error.tsx` catches every uncaught render error, since there is no segment-level `error.tsx`. It calls `Sentry.captureException` in an effect.
4. Deploy wiring: a Dockerfile `ARG NEXT_PUBLIC_SENTRY_DSN`. The compose frontend gets the build arg `NEXT_PUBLIC_SENTRY_DSN: ${SENTRY_DSN:-}` and the runtime `SENTRY_DSN: ${SENTRY_DSN:-}`. It reuses the backend's variable, and each half can be split into its own Sentry project later.
5. Legal: add a Sentry row to `SUB_PROCESSORS`, for error reports only when configured, with no dataset content.
6. Tests: a jest test on the real SDK with an in-memory transport. It renders `GlobalError` with a thrown error and asserts the event arrives, scrubbed. A second test asserts `sentryOptions('')` is `undefined`.

## Decisions (autonomous)
- No `withSentryConfig`. That means no source-map upload and no auth token, and it keeps build wiring at zero. Add it when minified stacks hurt.
- A single `global-error.tsx`, not an `error.tsx` per segment.
- The DSN is shared with the backend's `SENTRY_DSN`. Splitting it is a one-variable change.

## AC4 checklist
- [ ] Sentry in the Next.js app, DSN optional, secret-less build green
- [ ] PII scrubbing on
- [ ] SENTRY_DSN provisioned for frontend in staging compose with `${VAR:-}` (backend already)
- [ ] Test: thrown render error reaches the reporter
