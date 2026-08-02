'use client';

import React from 'react';
import { useWorkflow } from '@/lib/contexts/WorkflowContext';
import { WORKFLOW_STAGES } from '@/lib/types/workflow';
import { cn } from '@/lib/utils';
import * as Icons from 'lucide-react';
import { motion } from 'framer-motion';

export function WorkflowBar() {
  const { state, canAccessStage, setCurrentStage } = useWorkflow();

  return (
    <div className="bg-card border-b border-border shadow-sm sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <nav className="flex items-center justify-between py-4">
          <div className="flex items-center space-x-2 overflow-x-auto scrollbar-hide flex-1 min-w-0">
            {WORKFLOW_STAGES.map((stage, index) => {
              const Icon = Icons[stage.icon as keyof typeof Icons] as React.ComponentType<{ className?: string }>;
              const isCompleted = state.completedStages.has(stage.id);
              const isCurrent = state.currentStage === stage.id;
              const isAccessible = canAccessStage(stage.id);
              const isLast = index === WORKFLOW_STAGES.length - 1;

              return (
                <React.Fragment key={stage.id}>
                  <motion.button
                    onClick={() => isAccessible && setCurrentStage(stage.id)}
                    disabled={!isAccessible}
                    title={stage.name}
                    aria-label={stage.name}
                    className={cn(
                      "flex items-center space-x-2 px-4 py-2 rounded-lg transition-all duration-200",
                      "focus:outline-none focus:ring-2 focus:ring-offset-2",
                      {
                        'bg-blue-600 text-white shadow-lg focus:ring-blue-500': isCurrent,
                        'bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-200 hover:bg-green-200 dark:hover:bg-green-900/60 focus:ring-green-500': isCompleted && !isCurrent,
                        'bg-muted text-gray-400 cursor-not-allowed': !isAccessible && !isCompleted,
                        'bg-muted text-foreground hover:bg-muted focus:ring-gray-500': isAccessible && !isCompleted && !isCurrent,
                      }
                    )}
                    whileHover={isAccessible ? { scale: 1.05 } : {}}
                    whileTap={isAccessible ? { scale: 0.95 } : {}}
                  >
                    <div className="relative">
                      <Icon className="w-5 h-5" />
                      {isCompleted && (
                        <motion.div
                          initial={{ scale: 0 }}
                          animate={{ scale: 1 }}
                          className="absolute -top-1 -right-1 w-3 h-3 bg-green-500 rounded-full"
                        >
                          <Icons.Check className="w-2 h-2 text-white absolute top-0.5 left-0.5" />
                        </motion.div>
                      )}
                    </div>
                    <span className="font-medium whitespace-nowrap">
                      {isCurrent ? stage.name : index + 1}
                    </span>
                  </motion.button>

                  {!isLast && (
                    <div className="flex items-center">
                      <motion.div
                        className={cn(
                          "h-0.5 w-2 sm:w-3 transition-all duration-500",
                          {
                            'bg-green-500': isCompleted && state.completedStages.has(WORKFLOW_STAGES[index + 1].id),
                            'bg-gray-300': !isCompleted || !state.completedStages.has(WORKFLOW_STAGES[index + 1].id),
                          }
                        )}
                        initial={{ scaleX: 0 }}
                        animate={{ scaleX: 1 }}
                        transition={{ delay: index * 0.1 }}
                      />
                      <Icons.ChevronRight className={cn(
                        "w-4 h-4 -ml-1 transition-colors duration-300",
                        {
                          'text-green-500': isCompleted && state.completedStages.has(WORKFLOW_STAGES[index + 1].id),
                          'text-gray-300': !isCompleted || !state.completedStages.has(WORKFLOW_STAGES[index + 1].id),
                        }
                      )} />
                    </div>
                  )}
                </React.Fragment>
              );
            })}
          </div>

          {/* Progress indicator — pinned outside the scrollable stage strip */}
          <div className="ml-4 flex items-center space-x-2 text-sm text-muted-foreground shrink-0">
            <span className="hidden lg:inline">Progress:</span>
            <div className="flex items-center space-x-1">
              <span className="font-semibold text-foreground">
                {state.completedStages.size}
              </span>
              <span>/</span>
              <span>{WORKFLOW_STAGES.length}</span>
            </div>
          </div>
        </nav>

        {/* Stage description */}
        <div className="pb-3 -mt-1">
          <p className="text-sm text-muted-foreground">
            {WORKFLOW_STAGES.find(s => s.id === state.currentStage)?.description}
          </p>
        </div>
      </div>

      {/* Mobile stage indicator */}
      <div className="sm:hidden px-4 pb-2">
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground">
            Stage {WORKFLOW_STAGES.findIndex(s => s.id === state.currentStage) + 1} of {WORKFLOW_STAGES.length}
          </span>
          <span className="font-medium text-foreground">
            {WORKFLOW_STAGES.find(s => s.id === state.currentStage)?.name}
          </span>
        </div>
      </div>
    </div>
  );
}