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

// Illustrative rows from the churn sample: the last churn cell is the model's answer,
// drawn the way the logo draws it (highlighter cell, fill handle at the corner).
const ROWS = [
  ['35', '48.20', 'One year', 'No'],
  ['2', '85.10', 'Month-to-month', 'Yes'],
  ['56', '69.65', 'Two year', 'No'],
  ['19', '32.00', 'One year', 'No'],
  ['8', '90.45', 'Month-to-month', 'Yes'],
]

function HeroSheet() {
  return (
    <figure className="min-w-0 overflow-hidden rounded-xl border border-border bg-card shadow-[0_18px_40px_-22px_color-mix(in_oklch,var(--primary)_45%,transparent)]">
      <figcaption className="border-b border-border px-3 py-2 text-xs text-muted-foreground">
        <span className="font-semibold text-foreground">customer_churn.csv</span>, predicting{' '}
        <span className="font-semibold text-primary">churn</span>
      </figcaption>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="bg-muted text-left text-xs text-muted-foreground">
              {['tenure', 'monthly_charges', 'contract', 'churn'].map((column) => (
                <th key={column} scope="col" className="border-b border-r border-border px-3 py-2 font-semibold last:border-r-0">
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row) => (
              <tr key={row.join()}>
                {row.map((cell, index) => (
                  <td key={index} className="border-b border-r border-border px-3 py-2 last:border-r-0">
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
            <tr>
              <td className="border-r border-border px-3 py-2">14</td>
              <td className="border-r border-border px-3 py-2">74.30</td>
              <td className="border-r border-border px-3 py-2">Month-to-month</td>
              <td className="relative bg-highlight px-3 py-2 font-bold text-highlight-foreground outline outline-2 -outline-offset-2 outline-foreground">
                Yes, 71%
                <span aria-hidden="true" className="absolute -bottom-1 -right-1 size-2 border border-card bg-foreground" />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </figure>
  )
}

export function Hero() {
  const description = longForm(COMPANY.serviceName)
  return (
    <section aria-labelledby="hero-heading" className="grid items-center gap-10 pt-6 @container md:grid-cols-[1fr_1.05fr]">
      <div className="flex min-w-0 flex-col items-start gap-6">
        <h1 id="hero-heading" className="text-4xl font-extrabold leading-[1.05] tracking-[-0.03em] text-balance text-foreground sm:text-5xl">
          {COMPANY.valueLine}
        </h1>
        <p className="max-w-[60ch] text-base text-muted-foreground sm:text-lg">{description}</p>
        <div className="flex flex-wrap gap-3">
          <Button asChild size="lg">
            <Link href="/auth/signin">Get started</Link>
          </Button>
          <Button asChild size="lg" variant="outline">
            <Link href="/how-it-works">See how it works</Link>
          </Button>
        </div>
      </div>
      <HeroSheet />
    </section>
  )
}
