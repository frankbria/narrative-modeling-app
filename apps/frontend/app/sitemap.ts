import type { MetadataRoute } from 'next'
import { PUBLIC_LINKS } from '@/lib/publicLinks'
import { siteUrl } from '@/lib/site'

// Decided per request: the same image runs on dev. and www. (#766, #831).
export const dynamic = 'force-dynamic'

const PUBLIC_PAGES = ['/', ...PUBLIC_LINKS.map((link) => link.href)]

export default function sitemap(): MetadataRoute.Sitemap {
  const base = siteUrl()
  return PUBLIC_PAGES.map((path) => ({ url: new URL(path, base).href }))
}
