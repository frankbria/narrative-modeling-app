'use client';

import React, { createContext, useContext, useState, useCallback, useEffect, ReactNode } from 'react';
import { FeatureSuggestion, FeatureType, ComputationCost } from '@/lib/hooks/useFeatureSuggestions';

export interface SelectedFeature {
  suggestion: FeatureSuggestion;
  modifiedParameters?: Record<string, any>;
  addedAt: Date;
}

export interface FilterState {
  featureTypes: FeatureType[];
  minImportance: number;
  maxImportance: number;
  computationCosts: ComputationCost[];
  searchQuery: string;
  sortBy: 'importance' | 'name' | 'type' | 'cost';
  sortOrder: 'asc' | 'desc';
}

export interface FeatureEngineeringContextValue {
  // Selected features
  selectedFeatures: SelectedFeature[];
  addFeature: (suggestion: FeatureSuggestion, modifiedParams?: Record<string, any>) => void;
  removeFeature: (suggestionId: string) => void;
  clearSelectedFeatures: () => void;
  isFeatureSelected: (suggestionId: string) => boolean;

  // Filters
  filters: FilterState;
  setFilters: (filters: Partial<FilterState>) => void;
  resetFilters: () => void;

  // UI state
  viewMode: 'grid' | 'list';
  setViewMode: (mode: 'grid' | 'list') => void;
  expandedSuggestionId: string | null;
  setExpandedSuggestionId: (id: string | null) => void;
}

const defaultFilters: FilterState = {
  featureTypes: [],
  minImportance: 0,
  maxImportance: 100,
  computationCosts: [],
  searchQuery: '',
  sortBy: 'importance',
  sortOrder: 'desc',
};

const FeatureEngineeringContext = createContext<FeatureEngineeringContextValue | null>(null);

export function useFeatureEngineering(): FeatureEngineeringContextValue {
  const context = useContext(FeatureEngineeringContext);
  if (!context) {
    throw new Error('useFeatureEngineering must be used within a FeatureEngineeringProvider');
  }
  return context;
}

interface FeatureEngineeringProviderProps {
  children: ReactNode;
  datasetId: string;
}

export function FeatureEngineeringProvider({
  children,
  datasetId,
}: FeatureEngineeringProviderProps) {
  // Selected features state
  const [selectedFeatures, setSelectedFeatures] = useState<SelectedFeature[]>([]);

  // Filters state
  const [filters, setFiltersState] = useState<FilterState>(defaultFilters);

  // UI state
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [expandedSuggestionId, setExpandedSuggestionId] = useState<string | null>(null);

  // Load persisted state from localStorage
  // The one site in #393 that keeps its setState-in-effect, deliberately.
  //
  // This hydrates from localStorage, which does not exist during SSR — and this
  // is a 'use client' component, which Next still prerenders on the server. The
  // rule's remedies both break here: reading during render throws server-side,
  // and guarding with `typeof window` makes the server render empty while the
  // client renders populated, which is a hydration mismatch.
  //
  // Deferring to an effect so the first client render matches the server's is
  // exactly the documented pattern for browser-only storage. Clearing the lint
  // error would mean introducing a real bug to satisfy a rule that cannot see
  // the constraint, so the suppression is the honest option.
  /* eslint-disable react-hooks/set-state-in-effect -- SSR-safe localStorage hydration; see above */
  useEffect(() => {
    try {
      const savedFeatures = localStorage.getItem(`feature_engineering_${datasetId}_selected`);
      if (savedFeatures) {
        const parsed = JSON.parse(savedFeatures);
        setSelectedFeatures(
          parsed.map((f: any) => ({
            ...f,
            addedAt: new Date(f.addedAt),
          }))
        );
      }

      const savedFilters = localStorage.getItem(`feature_engineering_${datasetId}_filters`);
      if (savedFilters) {
        setFiltersState(JSON.parse(savedFilters));
      }

      const savedViewMode = localStorage.getItem(`feature_engineering_viewMode`);
      if (savedViewMode === 'grid' || savedViewMode === 'list') {
        setViewMode(savedViewMode);
      }
    } catch (err) {
      console.error('Failed to load persisted feature engineering state:', err);
    }
  }, [datasetId]);
  /* eslint-enable react-hooks/set-state-in-effect */

  // Persist selected features
  useEffect(() => {
    try {
      localStorage.setItem(
        `feature_engineering_${datasetId}_selected`,
        JSON.stringify(selectedFeatures)
      );
    } catch (err) {
      console.error('Failed to persist selected features:', err);
    }
  }, [selectedFeatures, datasetId]);

  // Persist filters
  useEffect(() => {
    try {
      localStorage.setItem(
        `feature_engineering_${datasetId}_filters`,
        JSON.stringify(filters)
      );
    } catch (err) {
      console.error('Failed to persist filters:', err);
    }
  }, [filters, datasetId]);

  // Persist view mode
  useEffect(() => {
    try {
      localStorage.setItem('feature_engineering_viewMode', viewMode);
    } catch (err) {
      console.error('Failed to persist view mode:', err);
    }
  }, [viewMode]);

  const addFeature = useCallback(
    (suggestion: FeatureSuggestion, modifiedParams?: Record<string, any>) => {
      setSelectedFeatures((prev) => {
        // Check if already selected
        if (prev.some((f) => f.suggestion.id === suggestion.id)) {
          return prev;
        }
        return [
          ...prev,
          {
            suggestion,
            modifiedParameters: modifiedParams,
            addedAt: new Date(),
          },
        ];
      });
    },
    []
  );

  const removeFeature = useCallback((suggestionId: string) => {
    setSelectedFeatures((prev) => prev.filter((f) => f.suggestion.id !== suggestionId));
  }, []);

  const clearSelectedFeatures = useCallback(() => {
    setSelectedFeatures([]);
  }, []);

  const isFeatureSelected = useCallback(
    (suggestionId: string) => {
      return selectedFeatures.some((f) => f.suggestion.id === suggestionId);
    },
    [selectedFeatures]
  );

  const setFilters = useCallback((newFilters: Partial<FilterState>) => {
    setFiltersState((prev) => ({ ...prev, ...newFilters }));
  }, []);

  const resetFilters = useCallback(() => {
    setFiltersState(defaultFilters);
  }, []);

  const value: FeatureEngineeringContextValue = {
    selectedFeatures,
    addFeature,
    removeFeature,
    clearSelectedFeatures,
    isFeatureSelected,
    filters,
    setFilters,
    resetFilters,
    viewMode,
    setViewMode,
    expandedSuggestionId,
    setExpandedSuggestionId,
  };

  return (
    <FeatureEngineeringContext.Provider value={value}>
      {children}
    </FeatureEngineeringContext.Provider>
  );
}
