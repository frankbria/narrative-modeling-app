import Image from 'next/image'
import Link from 'next/link'
import { SHOT_SIZE, STAGE_SHOTS } from '@/components/how-it-works/stageShots'
import { WorkflowStage } from '@/lib/types/workflow'

/** Four of the eight stage screenshots on /how-it-works: the ones that show the work. */
const FEATURED: { stage: WorkflowStage; alt: string }[] = [
  { stage: WorkflowStage.DATA_PROFILING, alt: 'A churn dataset profiled: rows, columns and a data preview' },
  { stage: WorkflowStage.MODEL_TRAINING, alt: 'The model training setup: target column and training mode' },
  { stage: WorkflowStage.MODEL_EVALUATION, alt: 'Model evaluation: accuracy, ROC AUC and a plain-language report card' },
  { stage: WorkflowStage.PREDICTION, alt: 'A single prediction with its confidence and what drove it' },
]

export function ProductShots() {
  const shots = FEATURED
  return (
    <section aria-labelledby="shots-heading" className="space-y-4">
      <h2 id="shots-heading" className="text-2xl font-semibold text-foreground">
        See the app
      </h2>
      <div className="grid gap-4 sm:grid-cols-2">
        {shots.map(({ stage, alt }) => (
          <Image
            key={stage}
            src={STAGE_SHOTS[stage]}
            alt={alt}
            width={SHOT_SIZE.width}
            height={SHOT_SIZE.height}
            unoptimized
            className="h-auto w-full rounded-lg border border-border"
          />
        ))}
      </div>
      <Link href="/how-it-works" className="text-sm text-primary hover:underline">
        See every stage and a walkthrough
      </Link>
    </section>
  )
}
