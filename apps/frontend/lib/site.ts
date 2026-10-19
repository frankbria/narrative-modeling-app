/**
 * Where this deployment says it lives, and whether it may be indexed (#766, #831).
 *
 * One image serves dev. and www., so both answers are read from the environment
 * when a request arrives, never from a build-time constant. `NEXTAUTH_URL` is
 * already each host's public address (required in production by `auth-config`),
 * so metadata needs no second variable. `ENVIRONMENT` is the same word the
 * backend reads; compose sets it per host, and anything but `production` hides
 * the site from crawlers, so a missing value fails closed.
 */
import type { Metadata } from 'next'
import { COMPANY } from '@/lib/legal/company'

type Env = Record<string, string | undefined>

/** Positioning.md section 2: the tagline for the title and OG cards. */
export const TAGLINE = 'Explained predictions from your spreadsheet.'

const OG_IMAGE = '/og-image.png'

export function siteUrl(env: Env = process.env): URL {
  return new URL(env.NEXTAUTH_URL || 'http://localhost:3000')
}

export function isProduction(env: Env = process.env): boolean {
  return env.ENVIRONMENT === 'production'
}

export function siteMetadata(env: Env = process.env): Metadata {
  return {
    metadataBase: siteUrl(env),
    title: COMPANY.serviceName,
    description: COMPANY.valueLine,
    openGraph: {
      type: 'website',
      siteName: COMPANY.serviceName,
      title: `${COMPANY.serviceName}: ${TAGLINE}`,
      description: COMPANY.valueLine,
      images: [{ url: OG_IMAGE, width: 1200, height: 630, alt: COMPANY.serviceName }],
    },
    twitter: {
      card: 'summary_large_image',
      title: `${COMPANY.serviceName}: ${TAGLINE}`,
      description: COMPANY.valueLine,
      images: [OG_IMAGE],
    },
  }
}
