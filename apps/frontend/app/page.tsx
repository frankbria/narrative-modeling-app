import type { Metadata } from 'next'
import { redirect } from 'next/navigation'
import { auth } from '@/auth'
import { LandingPage } from '@/components/landing/LandingPage'
import { COMPANY } from '@/lib/legal/company'
import { TAGLINE } from '@/lib/site'

export const metadata: Metadata = {
  title: { absolute: `${COMPANY.serviceName}: ${TAGLINE}` },
  alternates: { canonical: '/' },
}

/**
 * The public landing page (#766). `/` is an exact-path exemption in middleware.ts,
 * so an anonymous visitor reaches this; a signed-in one keeps the dashboard.
 */
export default async function HomePage() {
  const session = await auth()
  if (session) redirect('/dashboard')
  return <LandingPage />
}
