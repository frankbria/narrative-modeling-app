'use client'

import * as Sentry from '@sentry/nextjs'
import { useEffect } from 'react'

/**
 * Last-resort boundary for any uncaught render error (no segment defines its
 * own `error.tsx`), and the one place a client crash is reported (#769 AC4).
 * It replaces the root layout, so it renders its own document without the
 * app's styles; `color-scheme` keeps it readable in either OS theme.
 */
export default function GlobalError({
  error,
  retry,
}: {
  error: Error & { digest?: string }
  retry: () => void
}) {
  useEffect(() => {
    Sentry.captureException(error)
  }, [error])

  return (
    <html lang="en" style={{ colorScheme: 'light dark' }}>
      <body style={{ fontFamily: 'system-ui, sans-serif', padding: '4rem 1rem', textAlign: 'center' }}>
        <title>Something went wrong</title>
        <h1>Something went wrong</h1>
        <p>The error has been recorded{error.digest ? ` (reference ${error.digest})` : ''}.</p>
        <button type="button" onClick={() => retry()}>
          Try again
        </button>
      </body>
    </html>
  )
}
