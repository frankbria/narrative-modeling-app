'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useWorkflow } from '@/lib/contexts/WorkflowContext';
import { WORKFLOW_STAGES } from '@/lib/types/workflow';

export default function HomePage() {
  const router = useRouter();
  const { state } = useWorkflow();

  useEffect(() => {
    // Find the first incomplete stage and redirect there
    const firstIncompleteStage = WORKFLOW_STAGES.find(
      stage => !state.completedStages.has(stage.id)
    );

    if (firstIncompleteStage) {
      router.push(firstIncompleteStage.route);
    } else {
      // All stages complete, go to deployment
      router.push('/deploy');
    }
  }, [router, state.completedStages]);

  return (
    <div className="flex items-center justify-center h-full">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
    </div>
  );
}