import Link from 'next/link'
import { KeyRound, RotateCcw, ShieldCheck, Trash2 } from 'lucide-react'
import { COMPANY } from '@/lib/legal/company'

/** Each line traces to code: #608/#490 PII, #461 fallbacks, #480/#497 erasure, #602 refund. */
const COMMITMENTS = [
  { icon: ShieldCheck, text: 'PII is scanned and masked before anything reaches a language model.' },
  { icon: KeyRound, text: 'Every AI feature works without an AI key.' },
  { icon: Trash2, text: 'One-click erasure of your data.' },
  { icon: RotateCcw, text: `${COMPANY.refundWindowDays}-day refund from your first payment.` },
]

export function TrustStrip() {
  const commitments = COMMITMENTS
  return (
    <section aria-labelledby="trust-heading" className="space-y-4">
      <h2 id="trust-heading" className="text-2xl font-semibold text-foreground">
        What happens to your data
      </h2>
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {commitments.map(({ icon: Icon, text }) => (
          <li key={text} className="flex items-start gap-3 rounded-lg border border-border bg-card p-4 text-sm text-card-foreground">
            <Icon aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
            <span>{text}</span>
          </li>
        ))}
      </ul>
      <Link href="/legal/privacy" className="text-sm text-primary hover:underline">
        Read the Privacy Policy
      </Link>
    </section>
  )
}
