'use client';

/**
 * Shared stage-transition footer for the 8-stage workflow (issue #88).
 *
 * Gives every stage page a consistent "Back" + "Continue to <next stage>"
 * affordance, replacing the ad-hoc per-page buttons. The Continue CTA is gated
 * on stage completion (`completedStages`) and `validateStageCompletion`, so a
 * transition can't happen until the current stage has the data the next stage
 * needs (AC1 + AC5). Navigation is route-aware via the context helpers (AC4).
 */

import React, { useState } from 'react';
import { ArrowLeft, ArrowRight, CheckCircle, Loader2 } from 'lucide-react';
import { useWorkflow } from '@/lib/contexts/WorkflowContext';
import { WorkflowStage } from '@/lib/types/workflow';
import {
  getNextStage,
  getPreviousStage,
  validateStageCompletion,
} from '@/lib/utils/stageValidation';

interface StageNavigationProps {
  /** The stage this navigation footer belongs to. */
  currentStage: WorkflowStage;
  /**
   * Override the completion check. Defaults to whether `currentStage` is in
   * `completedStages`. Useful when a page knows it is ready before the context
   * state has settled.
   */
  ready?: boolean;
  /** External loading flag (e.g. an in-flight action on the page). */
  loading?: boolean;
  /** Override the Continue button label. */
  continueLabel?: string;
  /**
   * Optional action run before advancing (e.g. persist a final selection).
   * If it throws, navigation is skipped.
   */
  onContinue?: () => void | Promise<void>;
  /** Hide the Back button (e.g. on the first stage). */
  hideBack?: boolean;
  /** Handler for the final stage's terminal CTA (no next stage). */
  onFinish?: () => void;
  /** Label for the final-stage CTA. */
  finishLabel?: string;
  className?: string;
}

export function StageNavigation({
  currentStage,
  ready,
  loading = false,
  continueLabel,
  onContinue,
  hideBack = false,
  onFinish,
  finishLabel = 'Finish',
  className = '',
}: StageNavigationProps) {
  const { state, goToNextStage, goToPreviousStage } = useWorkflow();
  const [busy, setBusy] = useState(false);

  const next = getNextStage(currentStage);
  const previous = getPreviousStage(currentStage);

  const isComplete = ready ?? state.completedStages.has(currentStage);
  const validation = validateStageCompletion(
    currentStage,
    state.stageData?.[currentStage]
  );
  const isBusy = loading || busy;
  const canContinue = isComplete && validation.isValid && !isBusy;

  const handleContinue = async () => {
    if (!canContinue) return;
    try {
      setBusy(true);
      if (onContinue) await onContinue();
      goToNextStage();
    } catch (error) {
      console.error('Failed to advance to the next stage:', error);
    } finally {
      setBusy(false);
    }
  };

  // What to tell the user when Continue is disabled.
  const hint = isComplete
    ? validation.errors[0]
    : 'Complete this step to continue.';

  return (
    <div
      className={`mt-6 flex items-center justify-between gap-4 ${className}`}
      data-testid="stage-navigation"
    >
      <div>
        {previous && !hideBack && (
          <button
            type="button"
            onClick={goToPreviousStage}
            disabled={isBusy}
            data-testid="back-button"
            className="inline-flex items-center gap-2 px-4 py-2 text-gray-600 hover:text-gray-900 disabled:opacity-50"
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </button>
        )}
      </div>

      <div className="flex flex-col items-end gap-1">
        {next ? (
          <button
            type="button"
            onClick={handleContinue}
            disabled={!canContinue}
            data-testid="continue-button"
            aria-label={continueLabel ?? `Continue to ${next.name}`}
            className={`inline-flex items-center gap-2 px-6 py-2 rounded-lg font-medium transition-colors ${
              canContinue
                ? 'bg-blue-600 text-white hover:bg-blue-700'
                : 'bg-gray-300 text-gray-500 cursor-not-allowed'
            }`}
          >
            {isBusy ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : null}
            {continueLabel ?? `Continue to ${next.name}`}
            {!isBusy && <ArrowRight className="w-4 h-4" />}
          </button>
        ) : (
          onFinish && (
            <button
              type="button"
              onClick={onFinish}
              disabled={isBusy}
              data-testid="finish-button"
              className="inline-flex items-center gap-2 px-6 py-2 rounded-lg font-medium bg-green-600 text-white hover:bg-green-700 disabled:opacity-50"
            >
              <CheckCircle className="w-4 h-4" />
              {finishLabel}
            </button>
          )
        )}
        {next && !canContinue && hint && (
          <p className="text-xs text-gray-500" data-testid="continue-hint">
            {hint}
          </p>
        )}
      </div>
    </div>
  );
}

export default StageNavigation;
