import { WORKFLOW_STAGES } from '@/lib/types/workflow'
import { STAGE_BLURBS } from './stageBlurbs'

export function HowItWorks() {
  const stages = WORKFLOW_STAGES
  return (
    <section aria-labelledby="how-heading" className="space-y-4">
      <h2 id="how-heading" className="text-2xl font-semibold text-foreground">
        How it works
      </h2>
      <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {stages.map((stage, index) => (
          <li key={stage.id} className="rounded-lg border border-border bg-card p-4 text-card-foreground">
            <p className="text-xs font-medium text-muted-foreground">{`Step ${index + 1}`}</p>
            <h3 className="mt-1 font-semibold">{stage.name}</h3>
            <p className="mt-1 text-sm text-muted-foreground">{STAGE_BLURBS[stage.id]}</p>
          </li>
        ))}
      </ol>
    </section>
  )
}
