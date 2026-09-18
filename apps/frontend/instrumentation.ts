import * as Sentry from '@sentry/nextjs'
import { sentryOptions } from '@/lib/observability/sentry'

export function register() {
  // Server and edge runtimes read the runtime env; unset ⇒ off.
  const options = sentryOptions(process.env.SENTRY_DSN)
  if (options) Sentry.init(options)
}

export const onRequestError = Sentry.captureRequestError
