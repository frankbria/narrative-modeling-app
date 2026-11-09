import { useEffect } from 'react'
import { useAsyncData } from '@/lib/hooks/useAsyncData'
import { useWorkflow } from '@/lib/contexts/WorkflowContext'
import { useStageGuard } from '@/lib/hooks/useStageGuard'
import { WorkflowStage } from '@/lib/types/workflow'
import { modelService } from '@/lib/services/model'
import { nameEvaluationClasses } from '@/lib/evaluation/classLabels'
import type { ModelEvaluationResponse } from '@/lib/types/evaluation'

export type EvaluateView = 'loading' | 'error' | 'empty' | 'ready'

// SHAP summary is best-effort enrichment (issue #80): a failure (or a model
// with no SHAP support) must never block the evaluation view.
async function loadEvaluation(modelId: string) {
  const raw = await modelService.getEvaluation(modelId)
  // The page keeps an empty state for a body with no evaluation in it.
  const evaluation = raw && nameEvaluationClasses(raw)
  const shap = await modelService.getShapSummary(modelId).catch(() => null)
  return { evaluation, shap }
}

const completionPayload = (evaluation: ModelEvaluationResponse | null | undefined) => ({
  evaluationComplete: true,
  metrics: evaluation?.metrics ?? evaluation?.stored_metrics,
  timestamp: new Date().toISOString()
})

// Accessible but no trained model in state: send the user back to train.
function useMissingModelRedirect(ready: boolean, modelId: string | undefined) {
  const { requestStageRedirect } = useWorkflow()
  useEffect(() => {
    if (!ready || modelId) return
    requestStageRedirect(WorkflowStage.MODEL_TRAINING, 'Train a model before evaluating it.')
  }, [ready, modelId, requestStageRedirect])
}

export function useEvaluation() {
  const { state, completeStage } = useWorkflow()
  const { ready } = useStageGuard(WorkflowStage.MODEL_EVALUATION)
  const { modelId } = state
  const { data, loading, error, reload } = useAsyncData(
    () => loadEvaluation(modelId as string),
    [modelId],
    { enabled: ready && !!modelId }
  )
  useMissingModelRedirect(ready, modelId)
  const evaluation = data?.evaluation
  return {
    loading,
    error,
    reload,
    evaluation,
    shap: data?.shap,
    datasetId: state.datasetId,
    proceed: () => completeStage(WorkflowStage.MODEL_EVALUATION, completionPayload(evaluation))
  }
}

export type Evaluation = ReturnType<typeof useEvaluation>

export function evaluateView(ev: Pick<Evaluation, 'loading' | 'error' | 'evaluation'>): EvaluateView {
  if (ev.loading) return 'loading'
  if (ev.error) return 'error'
  return ev.evaluation ? 'ready' : 'empty'
}
