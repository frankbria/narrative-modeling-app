import { WORKFLOW_STAGES, WorkflowStage } from '@/lib/types/workflow'

/**
 * One line per stage, written for this page: the in-app descriptions promise
 * "connect your data sources", which the do-not-claim list rules out. Keyed by
 * the enum so a ninth stage fails the type check until it is described here.
 */
const BLURBS: Record<WorkflowStage, string> = {
  [WorkflowStage.DATA_LOADING]: 'Upload a CSV or XLSX file.',
  [WorkflowStage.DATA_PROFILING]: 'See distributions, correlations and quality problems before you model.',
  [WorkflowStage.DATA_PREPARATION]: 'Clean the data, with a full history you can undo.',
  [WorkflowStage.FEATURE_ENGINEERING]: 'Choose which columns the model may use, or let it try interaction features.',
  [WorkflowStage.MODEL_TRAINING]: 'About ten algorithms, cross-validated, with a baseline to beat.',
  [WorkflowStage.MODEL_EVALUATION]: 'Read the leaderboard and the SHAP drivers behind the winner.',
  [WorkflowStage.PREDICTION]: 'Score one record or a whole file.',
  [WorkflowStage.DEPLOYMENT]: 'Serve it from a secured endpoint with API keys, or export it as Python or Docker.',
}

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
            <p className="mt-1 text-sm text-muted-foreground">{BLURBS[stage.id]}</p>
          </li>
        ))}
      </ol>
    </section>
  )
}
