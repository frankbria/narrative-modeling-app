'use client';

import React from 'react';
import { Badge } from '@/components/ui/badge';
import { CheckCircle, AlertTriangle, XCircle } from 'lucide-react';
import { RecipeCompatibilityResponse } from '@/lib/services/transformation';

interface RecipeCompatibilityBadgeProps {
  compatibility: RecipeCompatibilityResponse | null;
  isLoading?: boolean;
}

export function RecipeCompatibilityBadge({
  compatibility,
  isLoading
}: RecipeCompatibilityBadgeProps) {
  if (isLoading) {
    return (
      <Badge variant="secondary" className="gap-1">
        <span className="animate-pulse">Checking...</span>
      </Badge>
    );
  }

  if (!compatibility) {
    return null;
  }

  const { is_compatible, compatibility_score, warnings, suggestions } = compatibility;

  const getVariant = () => {
    if (is_compatible && compatibility_score >= 0.9) {
      return 'default';
    }
    if (is_compatible && compatibility_score >= 0.7) {
      return 'secondary';
    }
    return 'destructive';
  };

  const getIcon = () => {
    if (is_compatible && compatibility_score >= 0.9) {
      return <CheckCircle className="w-3 h-3" />;
    }
    if (is_compatible && compatibility_score >= 0.7) {
      return <AlertTriangle className="w-3 h-3" />;
    }
    return <XCircle className="w-3 h-3" />;
  };

  const getLabel = () => {
    if (is_compatible && compatibility_score >= 0.9) {
      return 'Compatible';
    }
    if (is_compatible && compatibility_score >= 0.7) {
      return 'Partially Compatible';
    }
    return 'Incompatible';
  };

  const tooltipContent = (
    <div className="text-xs space-y-2">
      <div>
        <strong>Compatibility Score:</strong> {Math.round(compatibility_score * 100)}%
      </div>
      {warnings.length > 0 && (
        <div>
          <strong>Warnings:</strong>
          <ul className="list-disc list-inside mt-1">
            {warnings.map((warning, idx) => (
              <li key={idx}>{warning}</li>
            ))}
          </ul>
        </div>
      )}
      {suggestions.length > 0 && (
        <div>
          <strong>Suggestions:</strong>
          <ul className="list-disc list-inside mt-1">
            {suggestions.map((suggestion, idx) => (
              <li key={idx}>{suggestion}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );

  return (
    <div className="relative group">
      <Badge variant={getVariant()} className="gap-1 cursor-help">
        {getIcon()}
        <span>{getLabel()}</span>
        <span className="text-xs opacity-75">({Math.round(compatibility_score * 100)}%)</span>
      </Badge>

      {(warnings.length > 0 || suggestions.length > 0) && (
        <div className="absolute z-10 hidden group-hover:block top-full mt-2 w-64 p-3 bg-gray-900 text-white rounded-lg shadow-lg">
          {tooltipContent}
          <div className="absolute -top-1 left-4 w-2 h-2 bg-gray-900 transform rotate-45"></div>
        </div>
      )}
    </div>
  );
}
