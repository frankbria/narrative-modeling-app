import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

/** Says what is being calculated while the evaluation loads (#1168). */
export function EvaluateLoading() {
  return (
    <div role="status" className="mx-auto max-w-6xl space-y-4 rounded-lg bg-card p-6 shadow-md">
      <h1 className="text-2xl font-bold">Checking how well your model predicts</h1>
      <p className="text-muted-foreground">
        Scoring it on rows it never saw during training. This takes a few seconds.
      </p>
      <Skeleton className="h-28 w-full" />
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Skeleton className="h-24" />
        <Skeleton className="h-24" />
        <Skeleton className="h-24" />
      </div>
    </div>
  )
}

export function EvaluateError(props: { message: string; onRetry: () => void; onBack: () => void }) {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="max-w-md text-center">
        <h2 className="mb-2 text-2xl font-semibold">Failed to Load Evaluation</h2>
        <p className="mb-4 text-muted-foreground">{props.message}</p>
        <div className="flex justify-center gap-2">
          <Button onClick={props.onRetry}>Try again</Button>
          <Button variant="outline" onClick={props.onBack}>
            Go to Model Training
          </Button>
        </div>
      </div>
    </div>
  )
}
