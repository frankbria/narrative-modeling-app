'use client'

import { useEffect, useRef } from 'react'
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

  // document.referrer never changes on client-side navigation, so only the first counted
  // view carries it: sent again, the same outside site would be named on every page.
  const referrerSent = useRef(false)

  useEffect(() => {
    if (!counted) return
    const referrer = referrerSent.current ? '' : document.referrer
    referrerSent.current = true
    void sendPageview(pageviewEvent(domain, window.location.origin, pathname, referrer))
  }, [counted, domain, pathname])

  return null
}
