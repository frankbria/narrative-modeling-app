import Link from 'next/link'
import { PublicNav } from '@/components/PublicNav'
import { Button } from '@/components/ui/button'
import { Hero } from './Hero'
import { HowItWorks } from './HowItWorks'
import { ProductShots } from './ProductShots'
import { NotYet } from './NotYet'
import { PricingSummary } from './PricingSummary'
import { ProofPoints } from './ProofPoints'
import { TrustStrip } from './TrustStrip'

export function LandingPage() {
  return (
    <div className="mx-auto w-full max-w-5xl space-y-14 px-2 pb-24 pt-6 text-foreground">
      <PublicNav />
      <Hero />
      <ProofPoints />
      <HowItWorks />
      <ProductShots />
      <TrustStrip />
      <PricingSummary />
      <NotYet />
      <section aria-labelledby="closing-heading" className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-border bg-card p-6 shadow-[inset_4px_0_0_var(--primary)]">
        <div>
          <h2 id="closing-heading" className="text-xl font-bold">Bring one spreadsheet</h2>
          <p className="text-muted-foreground">The free tier covers a complete run, from upload to a deployed model.</p>
        </div>
        <Button asChild size="lg">
          <Link href="/auth/signin">Start free</Link>
        </Button>
      </section>
    </div>
  )
}
