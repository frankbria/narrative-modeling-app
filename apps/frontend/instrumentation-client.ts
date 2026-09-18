import * as Sentry from '@sentry/nextjs'
import { sentryOptions } from '@/lib/observability/sentry'

// NEXT_PUBLIC_* is inlined at build time (Dockerfile build arg); unset ⇒ off.
const options = sentryOptions(process.env.NEXT_PUBLIC_SENTRY_DSN)
try {
  if (options) Sentry.init(options)
} catch (err) {
  // Monitoring must never stop the app from becoming interactive.
  console.error('Sentry init failed', err)
}
