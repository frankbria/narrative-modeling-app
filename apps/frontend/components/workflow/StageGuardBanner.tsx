'use client';

/**
 * Global banner that surfaces the message set when a stage guard redirects the
 * user (issue #88, AC2). Rendered once in the root layout, below the
 * WorkflowBar, so any guarded redirect shows a single consistent explanation
 * instead of an empty page. Auto-dismisses after a few seconds and can be
 * dismissed manually.
 */

import React, { useEffect } from 'react';
import { HugeiconsIcon } from '@/components/ui/icon';
import { AlertCircleIcon, Cancel01Icon } from '@hugeicons/core-free-icons';
import { useWorkflow } from '@/lib/contexts/WorkflowContext';

const AUTO_DISMISS_MS = 8000;

export function StageGuardBanner() {
  const { guardMessage, clearGuardMessage } = useWorkflow();

  useEffect(() => {
    if (!guardMessage) return;
    const timer = setTimeout(clearGuardMessage, AUTO_DISMISS_MS);
    return () => clearTimeout(timer);
  }, [guardMessage, clearGuardMessage]);

  if (!guardMessage) return null;

  return (
    <div
      role="status"
      data-testid="stage-guard-banner"
      className="mx-auto max-w-5xl mt-3 px-4"
    >
      <div className="flex items-start gap-3 rounded-lg border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-foreground">
        <HugeiconsIcon icon={AlertCircleIcon} className="mt-0.5 h-5 w-5 shrink-0 text-warning" />
        <p className="flex-1">{guardMessage}</p>
        <button
          type="button"
          onClick={clearGuardMessage}
          aria-label="Dismiss message"
          className="shrink-0 text-warning hover:text-foreground"
        >
          <HugeiconsIcon icon={Cancel01Icon} className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

export default StageGuardBanner;
