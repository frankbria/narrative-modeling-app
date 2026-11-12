'use client'

import { useEffect } from 'react'
import { usePathname } from 'next/navigation'
import { useSession } from 'next-auth/react'
import { COUNTED_PATHS, pageviewEvent, sendPageview } from '@/lib/analytics/plausible'

/**
 * Counts a signed-out visit to a public marketing page (#769 AC5).
 *
 * The session check lives here, not in where the layout mounts this, so no
 * placement can make a signed-in page report to Plausible.
 */
export function PublicPageviews({ domain }: { domain: string }) {
  const pathname = usePathname()
  const { status } = useSession()
  const counted = domain !== '' && status === 'unauthenticated' && COUNTED_PATHS.includes(pathname)

  useEffect(() => {
    if (counted) void sendPageview(pageviewEvent(domain, window.location.origin, pathname, document.referrer))
  }, [counted, domain, pathname])

  return null
}
