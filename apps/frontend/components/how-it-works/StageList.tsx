import Image from 'next/image'
import { STAGE_BLURBS } from '@/components/landing/stageBlurbs'
import { WORKFLOW_STAGES } from '@/lib/types/workflow'
import { SHOT_SIZE, STAGE_SHOTS } from './stageShots'

export function StageList() {
  const stages = WORKFLOW_STAGES
  return (
    <ol aria-label="The eight stages" className="m-0 list-none space-y-10 p-0">
      {stages.map((stage, index) => (
        <li key={stage.id} className="m-0 space-y-3 p-0">
          <p className="m-0 text-xs font-medium text-muted-foreground">{`Step ${index + 1}`}</p>
          <h3 className="m-0">{stage.name}</h3>
          <p className="m-0">{STAGE_BLURBS[stage.id]}</p>
          <Image
            src={STAGE_SHOTS[stage.id]}
            alt={`The ${stage.name} stage of the workflow, as it appears in the app`}
            width={SHOT_SIZE.width}
            height={SHOT_SIZE.height}
            unoptimized
            className="m-0 h-auto w-full rounded-lg border border-border"
          />
        </li>
      ))}
    </ol>
  )
}
