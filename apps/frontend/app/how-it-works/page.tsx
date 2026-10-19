import type { Metadata } from 'next'
import { HowItWorksContent } from '@/components/how-it-works/HowItWorksContent'
import { COMPANY } from '@/lib/legal/company'

export const metadata: Metadata = {
  title: `How it works | ${COMPANY.serviceName}`,
  description: `The eight stages ${COMPANY.serviceName} walks you through, from uploading a spreadsheet to a trained, explained model, with a screenshot of each.`,
  alternates: { canonical: '/how-it-works' },
}

/** Public (an exact-path exemption in middleware.ts, #772). */
export default function HowItWorksPage() {
  return <HowItWorksContent />
}
