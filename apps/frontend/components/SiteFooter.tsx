/**
 * Site-wide footer strip.
 *
 * Carries two things that must be reachable from every page for both signed-in
 * and signed-out visitors: the AGPL-3.0 §13 offer of Corresponding Source
 * (issue #260 — the machine-readable half is the backend `GET /`), and the
 * Terms and Privacy Policy links (issue #473). Plain anchors, so this stays a
 * server component with zero client JS; the legal links are internal but use
 * anchors for the same reason.
 */

const SOURCE_URL = 'https://github.com/frankbria/narrative-modeling-app'

export function SiteFooter() {
  return (
    <footer className="fixed bottom-2 left-2 z-40 flex items-center gap-2 text-xs text-muted-foreground">
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
