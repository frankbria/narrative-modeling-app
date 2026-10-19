import type { MetadataRoute } from 'next'
import { isProduction, siteUrl } from '@/lib/site'

// Decided per request: the same image runs on dev. and www. (#766, #831).
export const dynamic = 'force-dynamic'

export default function robots(): MetadataRoute.Robots {
  if (!isProduction()) return { rules: { userAgent: '*', disallow: '/' } }
  return {
    // `$` anchors the root and pricing; the legal pages are a subtree. Everything else is the app.
    rules: { userAgent: '*', allow: ['/$', '/pricing$', '/legal/'], disallow: '/' },
    sitemap: new URL('/sitemap.xml', siteUrl()).href,
  }
}
