/**
 * #769 AC4: a thrown render error reaches the error reporter, scrubbed.
 *
 * Runs the real @sentry/nextjs browser SDK; only the network transport is
 * swapped for an in-memory one, so the envelope asserted on is exactly what
 * would have been sent to Sentry.
 */
import * as Sentry from '@sentry/nextjs'
import type { Envelope, Event } from '@sentry/core'
import { render, waitFor } from '@testing-library/react'
import GlobalError from '@/app/global-error'
import { sentryOptions, scrubSentryEvent } from '@/lib/observability/sentry'

const sent: Event[] = []

beforeAll(() => {
  // Sentry wraps global.fetch for breadcrumbs; jest.setup's per-test fetch
  // mock must stay a jest.fn, so put it back after init.
  const jestFetch = global.fetch
  const options = sentryOptions('https://public@o0.ingest.example.invalid/1')
  Sentry.init({
    ...options,
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
  global.fetch = jestFetch
})

afterAll(() => Sentry.close())

describe('frontend error reporting', () => {
  it('is off without a DSN, so a secret-less build ships an inert SDK', () => {
    expect(sentryOptions(undefined)).toBeUndefined()
    expect(sentryOptions('   ')).toBeUndefined()
  })

  it('sends a render error caught by the global error boundary', async () => {
    jest.spyOn(console, 'error').mockImplementation(() => {})
    window.history.pushState({}, '', '/explore?dataset=abc&file=salaries.csv')
    const error = Object.assign(new Error('boom from a render'), { digest: 'd1' })
    render(<GlobalError error={error} retry={() => {}} />)

    await waitFor(() =>
      expect(sent.map((e) => e.exception?.values?.[0]?.value)).toContain('boom from a render'),
    )
    const event = sent.find((e) => e.exception?.values?.[0]?.value === 'boom from a render')!
    expect(event.user).toBeUndefined()
    expect(event.request).toEqual({ url: 'http://localhost/explore' })
  })

  it('strips query strings, cookies, headers and user from an event', () => {
    const scrubbed = scrubSentryEvent({
      user: { email: 'a@b.c', ip_address: '1.2.3.4' },
      request: {
        url: 'https://app.example/explore?dataset=abc&file=salaries.csv',
        query_string: 'dataset=abc&file=salaries.csv',
        cookies: { 'authjs.session-token': 'secret' },
        headers: { Authorization: 'Bearer t', 'User-Agent': 'x' },
      },
    })
    expect(scrubbed.user).toBeUndefined()
    expect(scrubbed.request).toEqual({ url: 'https://app.example/explore' })
  })

  it('drops console breadcrumbs and strips query strings from URL breadcrumbs', () => {
    const scrubbed = scrubSentryEvent({
      breadcrumbs: [
        { category: 'console', message: 'row {"ssn":"123-45-6789"}' },
        { category: 'fetch', data: { url: '/api/v1/datasets?name=salaries.csv', method: 'GET' } },
        { category: 'navigation', data: { from: '/a?x=1', to: '/b?y=2' } },
      ],
    })
    expect(scrubbed.breadcrumbs).toEqual([
      { category: 'fetch', data: { url: '/api/v1/datasets', method: 'GET', from: undefined, to: undefined } },
      { category: 'navigation', data: { from: '/a', to: '/b', url: undefined } },
    ])
  })
})
