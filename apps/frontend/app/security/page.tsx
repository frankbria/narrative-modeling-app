import type { Metadata } from 'next'
import { SecurityContent } from '@/components/trust/SecurityContent'
import { COMPANY } from '@/lib/legal/company'

export const metadata: Metadata = {
  title: `Security | ${COMPANY.serviceName}`,
  description: `Where ${COMPANY.serviceName} stores a dataset, how it is scanned for personal data, what reaches a language model, who the sub-processors are, and how to have it deleted.`,
  alternates: { canonical: '/security' },
}

/** Public (an exact-path exemption in middleware.ts, #772): read before an account exists. */
export default function SecurityPage() {
  return <SecurityContent />
}
