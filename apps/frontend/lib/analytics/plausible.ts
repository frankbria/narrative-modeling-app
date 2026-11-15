/**
 * Visit counts for the public marketing pages, sent to Plausible (#769 AC5).
 *
 * One request to Plausible's Events API per page, the same request its own script
 * makes, so no third-party code runs on the page and this file is the whole
 * payload. The Privacy Policy's cookie section and the Plausible row in
 * `SUB_PROCESSORS` describe it: change all three together.
 *
 * shortcut: pageviews only, no engagement time or scroll depth (decided on #1211).
 * Plausible gets those only from its tracker script, whose engagement events follow the
 * open page (into the app once a visitor signs in) and carry the full address. Revisit
 * when a funnel target needs time on page and the tracker can be held to COUNTED_PATHS.
 */
import { NAV_LINKS } from '@/lib/publicLinks'

export const PLAUSIBLE_EVENT_URL = 'https://plausible.io/api/event'

/**
 * The landing page and the pages the public nav shows. Exact paths, never prefixes.
 * The Privacy Policy's section 8 names these pages: a new nav link changes that sentence too.
 */
export const COUNTED_PATHS: readonly string[] = ['/', ...NAV_LINKS.map((link) => link.href)]

/**
 * The query-string parameters Plausible reads for its source and campaign reports (#1211).
 * Only these travel; anything else in the address (a callback URL, a token) is dropped, and so
 * is a tag whose value holds an @: a newsletter's merge tags can put the reader's email there.
 * Values are not length-capped (decided on #1227): a cap would not stop a short crafted value
 * such as a name in `ref`, and the Privacy Policy promises them "as the link wrote them". A cap
 * changes that sentence and the Plausible row in SUB_PROCESSORS in the same change.
 */
export const CAMPAIGN_PARAMETERS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'ref'] as const

export interface PageviewEvent {
  name: 'pageview'
  domain: string
  url: string
  referrer?: string
}

/**
 * The outside site that led here, as its origin alone. No path is ever sent: a path
 * on one of our own hosts (this one, or dev. next to www.) can hold a dataset or model id.
 */
function referringSite(referrer: string, origin: string): string | undefined {
  try {
    const from = new URL(referrer).origin
    // An opaque origin (file:, about:) serialises as the string "null".
    return from === origin || from === 'null' ? undefined : from
  } catch {
    // Not an address (the browser gave none). Counting a visit must never throw into the page.
    return undefined
  }
}

function campaignQuery(search: string): string {
  const given = new URLSearchParams(search)
  const kept = new URLSearchParams()
  for (const name of CAMPAIGN_PARAMETERS) {
    const value = given.get(name)
    if (value && !value.includes('@')) kept.set(name, value)
  }
  const query = kept.toString()
  return query ? `?${query}` : ''
}

export function pageviewEvent(
  domain: string,
  origin: string,
  pathname: string,
  referrer: string,
  search = '',
): PageviewEvent {
  const event: PageviewEvent = { name: 'pageview', domain, url: origin + pathname + campaignQuery(search) }
  const cameFrom = referringSite(referrer, origin)
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
