'use client';

import React from 'react';
import { useWorkflow } from '@/lib/contexts/WorkflowContext';
import { WORKFLOW_STAGES, WorkflowStage } from '@/lib/types/workflow';
import { cn } from '@/lib/utils';
import * as Icons from 'lucide-react';
import { motion } from 'framer-motion';

export function WorkflowBar() {
  const { state, canAccessStage, setCurrentStage } = useWorkflow();

  return (
    <div className="bg-white border-b border-gray-200 shadow-sm sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <nav className="flex items-center justify-between py-4 overflow-x-auto scrollbar-hide">
          <div className="flex items-center space-x-2 min-w-0">
            {WORKFLOW_STAGES.map((stage, index) => {
              const Icon = Icons[stage.icon as keyof typeof Icons] as React.ComponentType<any>;
              const isCompleted = state.completedStages.has(stage.id);
              const isCurrent = state.currentStage === stage.id;
              const isAccessible = canAccessStage(stage.id);
              const isLast = index === WORKFLOW_STAGES.length - 1;

              return (
                <React.Fragment key={stage.id}>
                  <motion.button
                    onClick={() => isAccessible && setCurrentStage(stage.id)}
                    disabled={!isAccessible}
                    className={cn(
                      "flex items-center space-x-2 px-4 py-2 rounded-lg transition-all duration-200",
                      "focus:outline-none focus:ring-2 focus:ring-offset-2",
                      {
                        'bg-blue-600 text-white shadow-lg focus:ring-blue-500': isCurrent,
                        'bg-green-100 text-green-800 hover:bg-green-200 focus:ring-green-500': isCompleted && !isCurrent,
                        'bg-gray-100 text-gray-400 cursor-not-allowed': !isAccessible && !isCompleted,
                        'bg-gray-50 text-gray-700 hover:bg-gray-100 focus:ring-gray-500': isAccessible && !isCompleted && !isCurrent,
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
                    <span className="font-medium whitespace-nowrap hidden sm:inline">
                      {stage.name}
                    </span>
                    <span className="font-medium whitespace-nowrap sm:hidden">
                      {index + 1}
                    </span>
                  </motion.button>

                  {!isLast && (
                    <div className="flex items-center">
                      <motion.div
                        className={cn(
                          "h-0.5 w-8 sm:w-12 transition-all duration-500",
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

          {/* Progress indicator */}
          <div className="ml-4 flex items-center space-x-2 text-sm text-gray-600">
            <span className="hidden lg:inline">Progress:</span>
            <div className="flex items-center space-x-1">
              <span className="font-semibold text-gray-900">
                {state.completedStages.size}
              </span>
              <span>/</span>
              <span>{WORKFLOW_STAGES.length}</span>
            </div>
          </div>
        </nav>

        {/* Stage description */}
        <div className="pb-3 -mt-1">
          <p className="text-sm text-gray-600">
            {WORKFLOW_STAGES.find(s => s.id === state.currentStage)?.description}
          </p>
        </div>
      </div>

      {/* Mobile stage indicator */}
      <div className="sm:hidden px-4 pb-2">
        <div className="flex items-center justify-between text-xs">
          <span className="text-gray-600">
            Stage {WORKFLOW_STAGES.findIndex(s => s.id === state.currentStage) + 1} of {WORKFLOW_STAGES.length}
          </span>
          <span className="font-medium text-gray-900">
            {WORKFLOW_STAGES.find(s => s.id === state.currentStage)?.name}
          </span>
        </div>
      </div>
    </div>
  );
}