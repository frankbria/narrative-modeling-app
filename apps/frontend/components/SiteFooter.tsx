/**
 * Site-wide footer strip.
 *
 * Carries two things that must be reachable from every page for both signed-in
 * and signed-out visitors: the AGPL-3.0 §13 offer of Corresponding Source
 * (issue #260 — the machine-readable half is the backend `GET /`), and the
 * Terms and Privacy Policy links (issue #473). Plain anchors, so this stays a
 * server component with zero client JS.
 *
 * Positioning is not cosmetic. `Sidebar` is `fixed left-0 w-64 z-30` with
 * `justify-between`, so its API Keys / Admin / theme controls sit in this exact
 * corner when signed in. This strip therefore clears the sidebar's width at
 * `lg+` (where the sidebar is pinned rather than a drawer) and stays *below* it
 * on z, so an open mobile drawer covers the strip rather than the strip
 * covering — and swallowing the clicks of — the controls underneath.
 */

const SOURCE_URL = 'https://github.com/frankbria/narrative-modeling-app'

export function SiteFooter({ withSidebar = false }: { withSidebar?: boolean }) {
  return (
    <footer
      className={`fixed bottom-2 z-20 flex items-center gap-2 rounded bg-background/80 px-2 py-1 text-xs text-muted-foreground backdrop-blur-sm ${
        withSidebar ? 'left-2 lg:left-[17rem]' : 'left-2'
      }`}
    >
      <a
        href={SOURCE_URL}
        target="_blank"
        rel="noopener noreferrer"
        title="This service is licensed under the GNU AGPL v3. Get the source code."
        className="hover:text-foreground hover:underline"
      >
        AGPL-3.0 · Source
      </a>
      <span aria-hidden="true">·</span>
      <a href="/legal/terms" className="hover:text-foreground hover:underline">
        Terms
      </a>
      <span aria-hidden="true">·</span>
      <a href="/legal/privacy" className="hover:text-foreground hover:underline">
        Privacy
      </a>
    </footer>
  )
}
