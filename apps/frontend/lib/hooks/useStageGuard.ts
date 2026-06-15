'use client';

/**
 * Stage dependency guard (issue #88, AC2).
 *
 * Replaces the ad-hoc `if (!canAccessStage(...)) router.push('/upload')` blocks
 * scattered across stage pages. A gated stage now redirects the user to the
 * *earliest incomplete prerequisite* (not always `/upload`) and surfaces a
 * helpful message via StageGuardBanner instead of flashing an empty shell.
 *
 * Crucially it waits for `isHydrated` before deciding — checking access before
 * the workflow state has been restored always sees an empty `completedStages`
 * and would wrongly kick a legitimate user back to the start.
 */

import { useEffect, useRef } from 'react';
import { useWorkflow } from '@/lib/contexts/WorkflowContext';
import { WorkflowStage } from '@/lib/types/workflow';
import {
  getFirstIncompletePrerequisite,
  getStageConfig,
} from '@/lib/utils/stageValidation';

export interface UseStageGuardResult {
  /** True once hydration is done and the stage is accessible (safe to render). */
  ready: boolean;
}

export function useStageGuard(stage: WorkflowStage): UseStageGuardResult {
  const { state, isHydrated, canAccessStage, requestStageRedirect } = useWorkflow();
  const accessible = canAccessStage(stage);
  // Redirect at most once per mount: once we navigate away the page unmounts,
  // but this also prevents a redundant second push if the effect re-runs.
  const redirectedRef = useRef(false);

  useEffect(() => {
    if (!isHydrated) return;
    if (accessible) {
      redirectedRef.current = false;
      return;
    }
    if (redirectedRef.current) return;
    redirectedRef.current = true;

    const target =
      getFirstIncompletePrerequisite(stage, state.completedStages) ??
      WorkflowStage.DATA_LOADING;
    const targetName = getStageConfig(target)?.name ?? 'a previous step';
    const stageName = getStageConfig(stage)?.name ?? 'this step';

    requestStageRedirect(
      target,
      `Complete "${targetName}" before you can access "${stageName}".`
    );
    // state.completedStages identity changes as stages complete; rerun so a
    // user who satisfies the prerequisite mid-session is no longer redirected.
  }, [isHydrated, accessible, stage, state.completedStages, requestStageRedirect]);

  return { ready: isHydrated && accessible };
}
