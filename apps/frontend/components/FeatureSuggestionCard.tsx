'use client';

import React, { useState } from 'react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ImportanceIndicator } from '@/components/ImportanceIndicator';
import { cn } from '@/lib/utils';
import {
  Check,
  X,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Cpu,
  Clock,
  Zap,
  Binary,
  BarChart2,
  Calendar,
  Type,
  Layers,
  Hash,
  Activity,
  Target,
} from 'lucide-react';
import { FeatureSuggestion, FeatureType, ComputationCost } from '@/lib/hooks/useFeatureSuggestions';

interface FeatureSuggestionCardProps {
  suggestion: FeatureSuggestion;
  isSelected?: boolean;
  onAccept?: (suggestion: FeatureSuggestion) => void;
  onReject?: (suggestion: FeatureSuggestion) => void;
  onViewDetails?: (suggestion: FeatureSuggestion) => void;
  className?: string;
}

const featureTypeIcons: Record<FeatureType, React.ReactNode> = {
  polynomial: <Binary className="h-4 w-4" />,
  interaction: <Activity className="h-4 w-4" />,
  aggregation: <BarChart2 className="h-4 w-4" />,
  time_based: <Calendar className="h-4 w-4" />,
  text: <Type className="h-4 w-4" />,
  binning: <Layers className="h-4 w-4" />,
  encoding: <Hash className="h-4 w-4" />,
  scaling: <Activity className="h-4 w-4" />,
  mathematical: <Target className="h-4 w-4" />,
  domain_specific: <Sparkles className="h-4 w-4" />,
};

const featureTypeLabels: Record<FeatureType, string> = {
  polynomial: 'Polynomial',
  interaction: 'Interaction',
  aggregation: 'Aggregation',
  time_based: 'Time-Based',
  text: 'Text',
  binning: 'Binning',
  encoding: 'Encoding',
  scaling: 'Scaling',
  mathematical: 'Mathematical',
  domain_specific: 'Domain-Specific',
};

const computationCostConfig: Record<
  ComputationCost,
  { label: string; color: string; icon: React.ReactNode }
> = {
  low: {
    label: 'Fast',
    color: 'bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-200 dark:bg-green-900 dark:text-green-200',
    icon: <Zap className="h-3 w-3" />,
  },
  medium: {
    label: 'Moderate',
    color: 'bg-yellow-100 dark:bg-yellow-900/40 text-yellow-800 dark:text-yellow-200 dark:bg-yellow-900 dark:text-yellow-200',
    icon: <Clock className="h-3 w-3" />,
  },
  high: {
    label: 'Slow',
    color: 'bg-red-100 dark:bg-red-900/40 text-red-800 dark:text-red-200 dark:bg-red-900 dark:text-red-200',
    icon: <Cpu className="h-3 w-3" />,
  },
};

export function FeatureSuggestionCard({
  suggestion,
  isSelected = false,
  onAccept,
  onReject,
  onViewDetails,
  className,
}: FeatureSuggestionCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const costConfig = computationCostConfig[suggestion.computation_cost];

  return (
    <Card
      className={cn(
        'transition-all duration-200 hover:shadow-md',
        isSelected && 'ring-2 ring-primary',
        className
      )}
    >
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          {/* Title and badges */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-muted-foreground">
                {featureTypeIcons[suggestion.feature_type]}
              </span>
              <h3 className="font-semibold text-sm truncate" title={suggestion.name}>
                {suggestion.name}
              </h3>
              {suggestion.source === 'ai' && (
                <Badge variant="secondary" className="text-xs px-1.5 py-0">
                  <Sparkles className="h-3 w-3 mr-1" />
                  AI
                </Badge>
              )}
            </div>

            {/* Feature type and cost badges */}
            <div className="flex flex-wrap gap-1.5">
              <Badge variant="outline" className="text-xs">
                {featureTypeLabels[suggestion.feature_type]}
              </Badge>
              <Badge className={cn('text-xs flex items-center gap-1', costConfig.color)}>
                {costConfig.icon}
                {costConfig.label}
              </Badge>
            </div>
          </div>

          {/* Importance indicator */}
          <div className="flex-shrink-0">
            <ImportanceIndicator score={suggestion.expected_importance} size="sm" />
          </div>
        </div>
      </CardHeader>

      <CardContent className="pt-0">
        {/* Description */}
        <p className="text-sm text-muted-foreground mb-3 line-clamp-2">
          {suggestion.description}
        </p>

        {/* Formula preview */}
        {suggestion.formula && (
          <div className="mb-3">
            <code className="text-xs bg-muted px-2 py-1 rounded font-mono block truncate">
              {suggestion.formula}
            </code>
          </div>
        )}

        {/* Input columns */}
        {suggestion.input_columns.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-3">
            <span className="text-xs text-muted-foreground">Uses:</span>
            {suggestion.input_columns.slice(0, 3).map((col) => (
              <Badge key={col} variant="secondary" className="text-xs">
                {col}
              </Badge>
            ))}
            {suggestion.input_columns.length > 3 && (
              <Badge variant="secondary" className="text-xs">
                +{suggestion.input_columns.length - 3} more
              </Badge>
            )}
          </div>
        )}

        {/* Expandable explanation */}
        <div className="border-t pt-3">
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors w-full"
          >
            {isExpanded ? (
              <ChevronUp className="h-3 w-3" />
            ) : (
              <ChevronDown className="h-3 w-3" />
            )}
            <span>{isExpanded ? 'Hide explanation' : 'Show explanation'}</span>
          </button>

          {isExpanded && (
            <div className="mt-2 text-sm text-muted-foreground">
              <p>{suggestion.explanation}</p>
            </div>
          )}
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2 mt-4">
          <Button
            size="sm"
            variant={isSelected ? 'secondary' : 'default'}
            className="flex-1"
            onClick={() => onAccept?.(suggestion)}
            disabled={isSelected}
          >
            <Check className="h-4 w-4 mr-1" />
            {isSelected ? 'Added' : 'Accept'}
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => onReject?.(suggestion)}
          >
            <X className="h-4 w-4" />
          </Button>
          {onViewDetails && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => onViewDetails(suggestion)}
            >
              Details
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
