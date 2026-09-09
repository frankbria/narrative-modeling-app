/**
 * Site-wide footer strip.
 *
 * Carries two things that must be reachable from every page for both signed-in
 * and signed-out visitors: the AGPL-3.0 §13 offer of Corresponding Source
 * (issue #260 — the machine-readable half is the backend `GET /`), and the
 * Terms and Privacy Policy links (issue #473). The source offer is a plain
 * anchor because it leaves the app; the legal links use next/link so they
 * client-navigate like every other internal link here.
 *
 * Positioning is not cosmetic. `Sidebar` is `fixed left-0 w-64 z-30` with
 * `justify-between`, so its API Keys / Admin / theme controls sit in this exact
 * corner when signed in. This strip therefore clears the sidebar's width at
 * `lg+` (where the sidebar is pinned rather than a drawer) and stays *below* it
 * on z, so an open mobile drawer covers the strip rather than the strip
 * covering — and swallowing the clicks of — the controls underneath.
 */

import Link from 'next/link'

const SOURCE_URL = 'https://github.com/frankbria/narrative-modeling-app'

export function SiteFooter({ withSidebar = false }: { withSidebar?: boolean }) {
  return (
    <footer
      className={`pointer-events-none fixed bottom-2 z-20 flex items-center gap-2 rounded bg-background/80 px-2 py-1 text-xs text-muted-foreground backdrop-blur-sm ${
        withSidebar ? 'left-2 lg:left-[17rem]' : 'left-2'
      }`}
    >
      <a
        href={SOURCE_URL}
        target="_blank"
        rel="noopener noreferrer"
        title="This service is licensed under the GNU AGPL v3. Get the source code."
        className="pointer-events-auto hover:text-foreground hover:underline"
      >
        AGPL-3.0 · Source
      </a>
      <span aria-hidden="true">·</span>
      <Link href="/legal/terms" className="pointer-events-auto hover:text-foreground hover:underline">
        Terms
      </Link>
      <span aria-hidden="true">·</span>
      <Link href="/legal/privacy" className="pointer-events-auto hover:text-foreground hover:underline">
        Privacy
      </Link>
    </footer>
  )
}
