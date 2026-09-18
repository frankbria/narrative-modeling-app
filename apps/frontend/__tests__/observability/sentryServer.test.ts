/**
 * @jest-environment node
 *
 * #769 AC4, server half: what `instrumentation.ts`'s `onRequestError`
 * (Sentry.captureRequestError) sends for a failed server render. Real Node
 * SDK, in-memory transport — the request's raw headers (session cookie
 * included) and its query string must not leave the process.
 */
import * as Sentry from '@sentry/nextjs'
import type { Envelope, Event } from '@sentry/core'
import { sentryOptions } from '@/lib/observability/sentry'

const sent: Event[] = []
// Built at runtime: Sentry's context-lines attach this file's own source to the
// event, so a literal secret here would always "leak".
const [jwt, apiToken, ip, query] = ['secret.jwt', 'api.token', '113.9', 'abc123&file=customer'].map(
  (s) => `x${s}x`,
)

beforeAll(() => {
  Sentry.init({
    ...sentryOptions('https://public@o0.ingest.example.invalid/1'),
    transport: () => ({
      send: async (envelope: Envelope) => {
        for (const [header, payload] of envelope[1]) {
          if (header.type === 'event') sent.push(payload as Event)
        }
        return {}
      },
      flush: async () => true,
    }),
  })
})

afterAll(() => Sentry.close())

it('reports a server render error without cookies, headers or the query string', async () => {
  Sentry.captureRequestError(
    new Error('server render failed'),
    {
      path: `/explore?dataset=${query}`,
      method: 'GET',
      headers: {
        cookie: `authjs.session-token=${jwt}`,
        authorization: `Bearer ${apiToken}`,
        'x-real-ip': ip,
      },
    },
    { routerKind: 'App Router', routePath: '/explore', routeType: 'render' },
  )
  await Sentry.flush(2000)

  const event = sent.find((e) => e.exception?.values?.[0]?.value === 'server render failed')
  expect(event).toBeDefined()
  const serialised = JSON.stringify(event)
  for (const secret of [jwt, apiToken, ip, query]) {
    expect(serialised).not.toContain(secret)
  }
  expect(event!.contexts?.nextjs?.request_path).toBe('/explore')
})
