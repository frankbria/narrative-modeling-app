'use client';

import { Check } from 'lucide-react';
import { useWorkflow } from '@/lib/contexts/WorkflowContext';
import { WORKFLOW_STAGES } from '@/lib/types/workflow';
import { cn } from '@/lib/utils';

/**
 * The eight stages as spreadsheet sheet tabs: every tab names its stage, the open one
 * is raised onto the page with a petrol edge, finished ones carry a check. Only the
 * tab strip scrolls sideways on a narrow screen (#185), never the page.
 */
export function WorkflowBar() {
  const { state, canAccessStage, setCurrentStage } = useWorkflow();

  return (
    <div className="sticky top-0 z-20 border-b border-border bg-card">
      <nav aria-label="Workflow stages" className="flex items-end pl-14 pr-4 pt-2.5 lg:px-6">
        <ol className="flex min-w-0 flex-1 items-end gap-0.5 overflow-x-auto scrollbar-hide">
          {WORKFLOW_STAGES.map((stage, index) => {
            const isCompleted = state.completedStages.has(stage.id);
            const isCurrent = state.currentStage === stage.id;
            const isAccessible = canAccessStage(stage.id);

            return (
              <li key={stage.id} className="shrink-0">
                <button
                  type="button"
                  onClick={() => isAccessible && setCurrentStage(stage.id)}
                  disabled={!isAccessible}
                  title={stage.name}
                  aria-label={stage.name}
                  aria-current={isCurrent ? 'step' : undefined}
                  className={cn(
                    'relative -mb-px flex items-center gap-1.5 whitespace-nowrap rounded-t-lg border border-b-0 border-border px-3 py-2 text-sm transition-colors',
                    'focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40',
                    isCurrent
                      ? 'bg-card font-bold text-foreground shadow-[inset_0_3px_0_var(--primary)]'
                      : 'bg-background font-medium',
                    !isCurrent && isAccessible && 'text-foreground hover:bg-accent',
                    !isAccessible && 'cursor-not-allowed text-muted-foreground'
                  )}
                >
                  {isCompleted && !isCurrent ? (
                    <Check className="h-3.5 w-3.5 text-success" aria-hidden="true" />
                  ) : (
                    // The open stage's number is the highlighter cell, as on the dashboard strip.
                    <span
                      className={cn(
                        'font-bold',
                        isCurrent ? 'rounded bg-highlight px-1.5 text-highlight-foreground' : 'text-muted-foreground'
                      )}
                    >
                      {index + 1}
                    </span>
                  )}
                  <span>{stage.tab}</span>
                </button>
              </li>
            );
          })}
        </ol>
        <p className="ml-4 hidden shrink-0 pb-2 text-xs text-muted-foreground xl:block">
          {state.completedStages.size} of {WORKFLOW_STAGES.length} stages done
        </p>
      </nav>
    </div>
  );
}
