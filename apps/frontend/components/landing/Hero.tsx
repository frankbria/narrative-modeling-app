import Image from 'next/image'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { COMPANY } from '@/lib/legal/company'

/** Positioning.md section 2, long form: who it is for and what it does. */
function longForm(name: string): string {
  return (
    `For applied researchers and analysts who have to defend a prediction, ${name} takes a CSV or XLSX, ` +
    'cross-validates about ten algorithms, explains the winner with SHAP, keeps a reproducible history, ' +
    'exports the model as self-contained Python or Docker, and serves it from a secured prediction ' +
    'endpoint, on a free tier sized for one complete run.'
  )
}

export function Hero() {
  const description = longForm(COMPANY.serviceName)
  return (
    <section aria-labelledby="hero-heading" className="flex flex-col items-start gap-6 pt-4">
      <Image src="/logo.svg" alt={COMPANY.serviceName} width={220} height={44} priority unoptimized />
      <h1 id="hero-heading" className="max-w-3xl text-4xl font-bold tracking-tight text-foreground">
        {COMPANY.valueLine}
      </h1>
      <p className="max-w-3xl text-lg text-muted-foreground">{description}</p>
      <Button asChild size="lg" className="transition-all focus-visible:ring-[3px]">
        <Link href="/auth/signin">Get started</Link>
      </Button>
    </section>
  )
}
