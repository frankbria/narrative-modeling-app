'use client';

import React from 'react';
import { cn } from '@/lib/utils';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

interface ImportanceIndicatorProps {
  score: number; // 0-1
  showLabel?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export function ImportanceIndicator({
  score,
  showLabel = true,
  size = 'md',
  className,
}: ImportanceIndicatorProps) {
  const percentage = Math.round(score * 100);

  // Determine color based on score
  const getColor = (s: number) => {
    if (s >= 0.7) return 'bg-green-500';
    if (s >= 0.4) return 'bg-yellow-500';
    return 'bg-orange-500';
  };

  const getTextColor = (s: number) => {
    if (s >= 0.7) return 'text-green-600 dark:text-green-400';
    if (s >= 0.4) return 'text-yellow-600 dark:text-yellow-400';
    return 'text-orange-600 dark:text-orange-400';
  };

  const getLabel = (s: number) => {
    if (s >= 0.7) return 'High';
    if (s >= 0.4) return 'Medium';
    return 'Low';
  };

  const sizeClasses = {
    sm: 'h-1.5 w-16',
    md: 'h-2 w-20',
    lg: 'h-2.5 w-24',
  };

  const textSizeClasses = {
    sm: 'text-xs',
    md: 'text-sm',
    lg: 'text-base',
  };

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className={cn('flex items-center gap-2', className)}>
            {/* Progress bar */}
            <div
              className={cn(
                'rounded-full bg-muted overflow-hidden',
                sizeClasses[size]
              )}
              role="progressbar"
              aria-valuenow={percentage}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label={`Importance score: ${percentage}%`}
            >
              <div
                className={cn(
                  'h-full rounded-full transition-all duration-300',
                  getColor(score)
                )}
                style={{ width: `${percentage}%` }}
              />
            </div>

            {/* Label */}
            {showLabel && (
              <span
                className={cn(
                  'font-medium',
                  textSizeClasses[size],
                  getTextColor(score)
                )}
              >
                {percentage}%
              </span>
            )}
          </div>
        </TooltipTrigger>
        <TooltipContent>
          <div className="text-sm">
            <p className="font-semibold">Importance: {getLabel(score)}</p>
            <p className="text-muted-foreground">
              Score: {percentage}% - This feature is expected to have{' '}
              {score >= 0.7 ? 'high' : score >= 0.4 ? 'moderate' : 'low'} predictive
              power for your target variable.
            </p>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
