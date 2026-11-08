/**
 * Site-wide footer strip.
 *
 * Carries two things that must be reachable from every page for both signed-in
 * and signed-out visitors: the licence and source link (Apache-2.0; the
 * machine-readable half is the backend `GET /`), and the Terms and Privacy
 * Policy links (issue #473) — plus every other public page in `PUBLIC_LINKS`
 * (pricing #475, security and how-it-works #772). The source link is a plain anchor
 * because it leaves the app; the legal links use next/link so they
 * client-navigate like every other internal link here.
 *
 * It sits in the page flow at the end of the main column, never `fixed`: a floating
 * strip covered cards and the sidebar's controls before the identity pass.
 */

import { Fragment } from 'react'
import Link from 'next/link'
import { PUBLIC_LINKS } from '@/lib/publicLinks'

const SOURCE_URL = 'https://github.com/frankbria/narrative-modeling-app'

export function SiteFooter({ className = '' }: { className?: string }) {
  return (
    <footer className={`flex w-full flex-wrap items-center gap-2 border-t border-border px-4 py-3 text-xs text-muted-foreground ${className}`}>
      <a
        href={SOURCE_URL}
        target="_blank"
        rel="noopener noreferrer"
        title="Licensed under the Apache License 2.0. Get the source code."
        className="hover:text-foreground hover:underline"
      >
        Apache-2.0 · Source
      </a>
      {PUBLIC_LINKS.map((link) => (
        <Fragment key={link.href}>
          <span aria-hidden="true">·</span>
          <Link href={link.href} className="hover:text-foreground hover:underline">
            {link.label}
          </Link>
        </Fragment>
      ))}
    </footer>
  )
}
