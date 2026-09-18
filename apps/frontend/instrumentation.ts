import * as Sentry from '@sentry/nextjs'
import { sentryOptions } from '@/lib/observability/sentry'

export function register() {
  // Server and edge runtimes read the runtime env; unset ⇒ off.
  const options = sentryOptions(process.env.SENTRY_DSN)
  try {
    if (options) Sentry.init(options)
  } catch (err) {
    // A monitoring failure must not stop the server from booting.
    console.error('Sentry init failed', err)
  }
}

export const onRequestError = Sentry.captureRequestError
