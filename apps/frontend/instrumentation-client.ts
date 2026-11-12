import { publicEnv } from '@/lib/runtimeEnv'
import * as Sentry from '@sentry/nextjs'
import { sentryOptions } from '@/lib/observability/sentry'

// Read from the page the server rendered, so each host reports to its own DSN; unset ⇒ off.
const options = sentryOptions(publicEnv('NEXT_PUBLIC_SENTRY_DSN'))
try {
  if (options) Sentry.init(options)
} catch (err) {
  // Monitoring must never stop the app from becoming interactive.
  console.error('Sentry init failed', err)
}
