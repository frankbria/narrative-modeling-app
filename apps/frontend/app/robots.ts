import type { MetadataRoute } from 'next'
import { isProduction, siteUrl } from '@/lib/site'

// Decided per request: the same image runs on dev. and www. (#766, #831).
export const dynamic = 'force-dynamic'

export default function robots(): MetadataRoute.Robots {
  if (!isProduction()) return { rules: { userAgent: '*', disallow: '/' } }
  return {
    // Pages need their assets (/_next/static, /logo.svg, /og-image.png) to render, and the
    // app pages a crawler could reach only redirect to sign-in.
    rules: { userAgent: '*', allow: '/', disallow: ['/api/', '/auth/'] },
    sitemap: new URL('/sitemap.xml', siteUrl()).href,
  }
}
