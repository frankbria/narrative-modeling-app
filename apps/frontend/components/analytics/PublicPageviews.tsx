'use client'

import { useEffect } from 'react'
import { usePathname } from 'next/navigation'
import { useSession } from 'next-auth/react'
import { COUNTED_PATHS, pageviewEvent, sendPageview } from '@/lib/analytics/plausible'

/**
 * Counts a signed-out visit to a public marketing page (#769 AC5).
 *
 * The layout mounts this only where the server found no session, and the
 * session check here holds whatever the placement, so a signed-in page cannot
 * report to Plausible.
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
