/**
 * AGPL-3.0 §13 source offer (issue #260).
 *
 * A persistent, unobtrusive link to the Corresponding Source of the deployed
 * service. The AGPL requires that network users be able to obtain the source
 * code; this is the visible UI half of that offer (the machine-readable half
 * is the backend `GET /` endpoint). Plain anchor, so it stays a server
 * component with zero client JS.
 */

const SOURCE_URL = 'https://github.com/frankbria/narrative-modeling-app'

export function SourceOffer() {
  return (
    <a
      href={SOURCE_URL}
      target="_blank"
      rel="noopener noreferrer"
      title="This service is licensed under the GNU AGPL v3. Get the source code."
      className="fixed bottom-2 left-2 z-40 text-xs text-muted-foreground hover:text-foreground hover:underline"
    >
      AGPL-3.0 · Source
    </a>
  )
}
