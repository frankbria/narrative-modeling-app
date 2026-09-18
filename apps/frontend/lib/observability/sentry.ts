/**
 * Sentry options shared by the browser, server and edge runtimes (#769 AC4).
 *
 * Mirrors the backend's `app/observability.py`: no DSN means no SDK, so dev,
 * CI and a secret-less Docker build stay inert. This app handles PII (#259),
 * so nothing identifying is attached and URL query strings (dataset ids,
 * filenames) are stripped before an event leaves the process.
 */
import type { ErrorEvent, Event, Integration } from '@sentry/core'

const stripQuery = (url: unknown) => (typeof url === 'string' ? url.split('?', 1)[0] : url)

// Scrubs the fields the SDK and this app populate today, not every field an
// event can carry: a new Sentry call site (extra, tags, a custom breadcrumb) is
// held to review by __tests__/observability/sentryCallSites.test.ts.
export function scrubSentryEvent<T extends Event>(event: T): T {
  delete event.user
  if (event.request) {
    const url = stripQuery(event.request.url) as string | undefined
    event.request = url ? { url } : {}
  }
  // captureRequestError records the raw request path, query included.
  const nextjs = event.contexts?.nextjs
  if (nextjs) nextjs.request_path = stripQuery(nextjs.request_path)
  // Console lines can stringify data; fetch/navigation crumbs carry URLs.
  event.breadcrumbs = event.breadcrumbs
    ?.filter((b) => b.category !== 'console')
    .map((b) =>
      b.data
        ? {
            ...b,
            data: { ...b.data, url: stripQuery(b.data.url), from: stripQuery(b.data.from), to: stripQuery(b.data.to) },
          }
        : b,
    )
  return event
}

export function sentryOptions(dsn: string | undefined) {
  const trimmed = dsn?.trim()
  if (!trimmed) return undefined
  return {
    dsn: trimmed,
    // Build-time like the DSN, so the browser and server halves agree.
    environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || process.env.NODE_ENV,
    sendDefaultPii: false,
    // ponytail: errors only; add tracing when there's a perf question to answer.
    tracesSampleRate: 0,
    // With no tracing, the default browser-tracing integration only costs
    // bundle and web-vitals observers.
    integrations: (defaults: Integration[]) =>
      defaults.filter((i) => i.name !== 'BrowserTracing'),
    beforeSend: (event: ErrorEvent) => scrubSentryEvent(event),
  }
}
