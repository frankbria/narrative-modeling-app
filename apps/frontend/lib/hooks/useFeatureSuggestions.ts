import { useState, useCallback } from 'react';
import { getAuthToken } from '@/lib/auth-helpers';

export interface FeatureSuggestion {
  id: string;
  name: string;
  description: string;
  feature_type: FeatureType;
  formula: string | null;
  expected_importance: number;
  explanation: string;
  computation_cost: ComputationCost;
  input_columns: string[];
  parameters: Record<string, any>;
  source: 'rule_based' | 'ai';
}

// Extended type for suggestions with local state (accepted/rejected status)
export interface FeatureSuggestionWithStatus extends FeatureSuggestion {
  _accepted?: boolean;
  _rejected?: boolean;
}

export type FeatureType =
  | 'polynomial'
  | 'interaction'
  | 'aggregation'
  | 'time_based'
  | 'text'
  | 'binning'
  | 'encoding'
  | 'scaling'
  | 'mathematical'
  | 'domain_specific';

export type ComputationCost = 'low' | 'medium' | 'high';

export interface FeatureSuggestionResponse {
  dataset_id: string;
  suggestions: FeatureSuggestion[];
  detected_problem_type: string | null;
  detected_target_column: string | null;
  detected_domain: string | null;
  total_suggestions: number;
  rule_based_count: number;
  ai_count: number;
  metadata: Record<string, any>;
  generated_at: string;
}

export interface FeatureFeedback {
  suggestion_id: string;
  accepted: boolean;
  modified_parameters?: Record<string, any>;
  reason?: string;
}

export interface UseFeatureSuggestionsOptions {
  datasetId: string;
  targetColumn?: string;
  problemType?: string;
  maxSuggestions?: number;
  includeAi?: boolean;
}

export interface UseFeatureSuggestionsReturn {
  suggestions: FeatureSuggestion[];
  isLoading: boolean;
  error: string | null;
  detectedProblemType: string | null;
  detectedTargetColumn: string | null;
  detectedDomain: string | null;
  metadata: Record<string, any>;
  fetchSuggestions: (options?: Partial<UseFeatureSuggestionsOptions>) => Promise<void>;
  acceptSuggestion: (suggestionId: string, modifiedParams?: Record<string, any>) => Promise<void>;
  rejectSuggestion: (suggestionId: string, reason?: string) => Promise<void>;
  loadMore: (excludeIds: string[]) => Promise<void>;
  clearError: () => void;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export function useFeatureSuggestions(
  options: UseFeatureSuggestionsOptions
): UseFeatureSuggestionsReturn {
  const { datasetId } = options;

  const [suggestions, setSuggestions] = useState<FeatureSuggestionWithStatus[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detectedProblemType, setDetectedProblemType] = useState<string | null>(null);
  const [detectedTargetColumn, setDetectedTargetColumn] = useState<string | null>(null);
  const [detectedDomain, setDetectedDomain] = useState<string | null>(null);
  const [metadata, setMetadata] = useState<Record<string, any>>({});

  const fetchSuggestions = useCallback(
    async (overrideOptions?: Partial<UseFeatureSuggestionsOptions>) => {
      setIsLoading(true);
      setError(null);

      try {
        const token = await getAuthToken();
        if (!token) {
          throw new Error('Not authenticated');
        }

        const requestBody = {
          target_column: overrideOptions?.targetColumn ?? options.targetColumn,
          problem_type: overrideOptions?.problemType ?? options.problemType,
          max_suggestions: overrideOptions?.maxSuggestions ?? options.maxSuggestions ?? 20,
          include_ai_suggestions: overrideOptions?.includeAi ?? options.includeAi ?? true,
        };

        const response = await fetch(
          `${API_URL}/datasets/${datasetId}/features/suggest`,
          {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody),
          }
        );

        if (!response.ok) {
          const errorText = await response.text();
          throw new Error(errorText || 'Failed to fetch suggestions');
        }

        const data: FeatureSuggestionResponse = await response.json();

        setSuggestions(data.suggestions);
        setDetectedProblemType(data.detected_problem_type);
        setDetectedTargetColumn(data.detected_target_column);
        setDetectedDomain(data.detected_domain);
        setMetadata(data.metadata);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'An error occurred');
      } finally {
        setIsLoading(false);
      }
    },
    [datasetId, options.targetColumn, options.problemType, options.maxSuggestions, options.includeAi]
  );

  const acceptSuggestion = useCallback(
    async (suggestionId: string, modifiedParams?: Record<string, any>) => {
      try {
        const token = await getAuthToken();
        if (!token) {
          throw new Error('Not authenticated');
        }

        const response = await fetch(
          `${API_URL}/features/suggestions/${suggestionId}/feedback?dataset_id=${datasetId}`,
          {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              accepted: true,
              modified_parameters: modifiedParams,
            }),
          }
        );

        if (!response.ok) {
          throw new Error('Failed to record feedback');
        }

        // Optimistic update - mark as accepted in UI
        setSuggestions((prev) =>
          prev.map((s): FeatureSuggestionWithStatus =>
            s.id === suggestionId
              ? { ...s, _accepted: true }
              : s
          )
        );
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to accept suggestion');
      }
    },
    [datasetId]
  );

  const rejectSuggestion = useCallback(
    async (suggestionId: string, reason?: string) => {
      try {
        const token = await getAuthToken();
        if (!token) {
          throw new Error('Not authenticated');
        }

        const response = await fetch(
          `${API_URL}/features/suggestions/${suggestionId}/feedback?dataset_id=${datasetId}`,
          {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              accepted: false,
              reason,
            }),
          }
        );

        if (!response.ok) {
          throw new Error('Failed to record feedback');
        }

        // Remove rejected suggestion from UI
        setSuggestions((prev) => prev.filter((s) => s.id !== suggestionId));
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to reject suggestion');
      }
    },
    [datasetId]
  );

  const loadMore = useCallback(
    async (excludeIds: string[]) => {
      setIsLoading(true);

      try {
        const token = await getAuthToken();
        if (!token) {
          throw new Error('Not authenticated');
        }

        const response = await fetch(
          `${API_URL}/datasets/${datasetId}/features/suggest-more`,
          {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              excluded_suggestion_ids: excludeIds,
              target_column: options.targetColumn,
              problem_type: options.problemType,
              count: 10,
            }),
          }
        );

        if (!response.ok) {
          throw new Error('Failed to load more suggestions');
        }

        const data: FeatureSuggestionResponse = await response.json();

        // Append new suggestions
        setSuggestions((prev) => [...prev, ...data.suggestions]);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load more');
      } finally {
        setIsLoading(false);
      }
    },
    [datasetId, options.targetColumn, options.problemType]
  );

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    suggestions,
    isLoading,
    error,
    detectedProblemType,
    detectedTargetColumn,
    detectedDomain,
    metadata,
    fetchSuggestions,
    acceptSuggestion,
    rejectSuggestion,
    loadMore,
    clearError,
  };
}
