/**
 * Visit counts for the public marketing pages, sent to Plausible (#769 AC5).
 *
 * One request to Plausible's Events API per page, the same request its own script
 * makes, so no third-party code runs on the page and this file is the whole
 * payload. The Privacy Policy's cookie section and the Plausible row in
 * `SUB_PROCESSORS` describe it: change all three together.
 *
 * shortcut: pageviews only, no engagement time or scroll depth; move to
 * `@plausible-analytics/tracker` when time on page is wanted.
 */
import { NAV_LINKS } from '@/lib/publicLinks'

export const PLAUSIBLE_EVENT_URL = 'https://plausible.io/api/event'

/** The landing page and the pages the public nav shows. Exact paths, never prefixes. */
export const COUNTED_PATHS: readonly string[] = ['/', ...NAV_LINKS.map((link) => link.href)]

export interface PageviewEvent {
  name: 'pageview'
  domain: string
  url: string
  referrer?: string
}

/** The outside page that led here, without its query string. One of our own pages is never sent: its path can hold a dataset or model id. */
function externalReferrer(referrer: string, origin: string): string | undefined {
  if (!URL.canParse(referrer)) return undefined
  const from = new URL(referrer)
  return from.origin === origin ? undefined : from.origin + from.pathname
}

export function pageviewEvent(domain: string, origin: string, pathname: string, referrer: string): PageviewEvent {
  const event: PageviewEvent = { name: 'pageview', domain, url: origin + pathname }
  const cameFrom = externalReferrer(referrer, origin)
  if (cameFrom) event.referrer = cameFrom
  return event
}

export async function sendPageview(event: PageviewEvent): Promise<void> {
  try {
    await fetch(PLAUSIBLE_EVENT_URL, {
      method: 'POST',
      // text/plain keeps this a simple cross-origin request (no preflight); Plausible parses it as JSON.
      headers: { 'Content-Type': 'text/plain' },
      body: JSON.stringify(event),
      keepalive: true,
      credentials: 'omit',
    })
  } catch {
    // A content blocker refusing the request is the visitor's choice, not an error to surface or report.
  }
}
