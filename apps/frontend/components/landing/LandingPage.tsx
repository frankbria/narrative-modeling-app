import { Hero } from './Hero'
import { HowItWorks } from './HowItWorks'
import { NotYet } from './NotYet'
import { PricingSummary } from './PricingSummary'
import { ProofPoints } from './ProofPoints'
import { TrustStrip } from './TrustStrip'

export function LandingPage() {
  return (
    <div className="mx-auto w-full max-w-5xl space-y-14 px-2 pb-24 pt-6 text-foreground">
      <Hero />
      <ProofPoints />
      <HowItWorks />
      <TrustStrip />
      <PricingSummary />
      <NotYet />
    </div>
  )
}
