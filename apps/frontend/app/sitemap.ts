import type { MetadataRoute } from 'next'
import { siteUrl } from '@/lib/site'

// Decided per request: the same image runs on dev. and www. (#766, #831).
export const dynamic = 'force-dynamic'

const PUBLIC_PAGES = ['/', '/pricing', '/legal/terms', '/legal/privacy']

export default function sitemap(): MetadataRoute.Sitemap {
  const base = siteUrl()
  return PUBLIC_PAGES.map((path) => ({ url: new URL(path, base).href }))
}
