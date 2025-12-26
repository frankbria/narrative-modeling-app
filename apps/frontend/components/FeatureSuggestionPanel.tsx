'use client';

import React, { useEffect, useMemo } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';
import { FeatureSuggestionCard } from '@/components/FeatureSuggestionCard';
import { SuggestionFilters } from '@/components/SuggestionFilters';
import { useFeatureEngineering } from '@/lib/contexts/FeatureEngineeringContext';
import {
  useFeatureSuggestions,
  FeatureSuggestion,
} from '@/lib/hooks/useFeatureSuggestions';
import { cn } from '@/lib/utils';
import {
  Sparkles,
  RefreshCw,
  AlertTriangle,
  Loader2,
  Grid3X3,
  List,
  ChevronRight,
  Brain,
  Wand2,
  CheckCircle,
} from 'lucide-react';

interface FeatureSuggestionPanelProps {
  datasetId: string;
  targetColumn?: string;
  problemType?: string;
  onFeatureSelected?: (suggestion: FeatureSuggestion) => void;
  className?: string;
}

export function FeatureSuggestionPanel({
  datasetId,
  targetColumn,
  problemType,
  onFeatureSelected,
  className,
}: FeatureSuggestionPanelProps) {
  const {
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
  } = useFeatureSuggestions({
    datasetId,
    targetColumn,
    problemType,
    maxSuggestions: 20,
    includeAi: true,
  });

  const {
    selectedFeatures,
    addFeature,
    removeFeature,
    isFeatureSelected,
    filters,
    viewMode,
    setViewMode,
  } = useFeatureEngineering();

  // Fetch suggestions on mount
  useEffect(() => {
    fetchSuggestions();
  }, [fetchSuggestions]);

  // Filter and sort suggestions
  const filteredSuggestions = useMemo(() => {
    let result = [...suggestions];

    // Filter by search query
    if (filters.searchQuery) {
      const query = filters.searchQuery.toLowerCase();
      result = result.filter(
        (s) =>
          s.name.toLowerCase().includes(query) ||
          s.description.toLowerCase().includes(query)
      );
    }

    // Filter by feature types
    if (filters.featureTypes.length > 0) {
      result = result.filter((s) => filters.featureTypes.includes(s.feature_type));
    }

    // Filter by computation costs
    if (filters.computationCosts.length > 0) {
      result = result.filter((s) =>
        filters.computationCosts.includes(s.computation_cost)
      );
    }

    // Filter by importance range
    result = result.filter((s) => {
      const importance = s.expected_importance * 100;
      return importance >= filters.minImportance && importance <= filters.maxImportance;
    });

    // Sort
    result.sort((a, b) => {
      let comparison = 0;

      switch (filters.sortBy) {
        case 'importance':
          comparison = b.expected_importance - a.expected_importance;
          break;
        case 'name':
          comparison = a.name.localeCompare(b.name);
          break;
        case 'type':
          comparison = a.feature_type.localeCompare(b.feature_type);
          break;
        case 'cost': {
          const costOrder = { low: 0, medium: 1, high: 2 };
          comparison = costOrder[a.computation_cost] - costOrder[b.computation_cost];
          break;
        }
      }

      return filters.sortOrder === 'asc' ? comparison : -comparison;
    });

    return result;
  }, [suggestions, filters]);

  const handleAccept = (suggestion: FeatureSuggestion) => {
    addFeature(suggestion);
    acceptSuggestion(suggestion.id);
    onFeatureSelected?.(suggestion);
  };

  const handleReject = (suggestion: FeatureSuggestion) => {
    removeFeature(suggestion.id);
    rejectSuggestion(suggestion.id);
  };

  const handleLoadMore = () => {
    const excludeIds = suggestions.map((s) => s.id);
    loadMore(excludeIds);
  };

  // Loading skeleton
  if (isLoading && suggestions.length === 0) {
    return (
      <Card className={className}>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
            <CardTitle>Generating Suggestions...</CardTitle>
          </div>
          <CardDescription>
            Analyzing your dataset and generating feature recommendations
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[...Array(6)].map((_, i) => (
              <Card key={i}>
                <CardHeader className="pb-2">
                  <Skeleton className="h-5 w-3/4" />
                  <Skeleton className="h-4 w-1/2 mt-2" />
                </CardHeader>
                <CardContent>
                  <Skeleton className="h-16 w-full" />
                  <Skeleton className="h-8 w-full mt-4" />
                </CardContent>
              </Card>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  // Error state
  if (error && suggestions.length === 0) {
    return (
      <Card className={className}>
        <CardContent className="flex flex-col items-center justify-center h-64 space-y-4 pt-6">
          <AlertTriangle className="h-8 w-8 text-destructive" />
          <p className="text-destructive text-center">{error}</p>
          <Button onClick={() => { clearError(); fetchSuggestions(); }} variant="outline" size="sm">
            <RefreshCw className="mr-2 h-4 w-4" />
            Retry
          </Button>
        </CardContent>
      </Card>
    );
  }

  const ruleBasedSuggestions = filteredSuggestions.filter((s) => s.source === 'rule_based');
  const aiSuggestions = filteredSuggestions.filter((s) => s.source === 'ai');

  return (
    <Card className={className}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            <CardTitle>Feature Suggestions</CardTitle>
          </div>
          <div className="flex items-center gap-2">
            {/* Selected count */}
            {selectedFeatures.length > 0 && (
              <Badge variant="default" className="gap-1">
                <CheckCircle className="h-3 w-3" />
                {selectedFeatures.length} selected
              </Badge>
            )}

            {/* View mode toggle */}
            <div className="flex border rounded-lg p-0.5 bg-muted">
              <Button
                variant={viewMode === 'grid' ? 'default' : 'ghost'}
                size="sm"
                onClick={() => setViewMode('grid')}
                className="h-7 px-2"
              >
                <Grid3X3 className="h-4 w-4" />
              </Button>
              <Button
                variant={viewMode === 'list' ? 'default' : 'ghost'}
                size="sm"
                onClick={() => setViewMode('list')}
                className="h-7 px-2"
              >
                <List className="h-4 w-4" />
              </Button>
            </div>

            {/* Refresh */}
            <Button
              onClick={() => fetchSuggestions()}
              variant="outline"
              size="sm"
              disabled={isLoading}
            >
              {isLoading ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="mr-2 h-4 w-4" />
              )}
              Refresh
            </Button>
          </div>
        </div>
        <CardDescription>
          AI-powered feature recommendations to improve your model
          {detectedDomain && ` • Detected domain: ${detectedDomain}`}
        </CardDescription>

        {/* Detection info */}
        {(detectedProblemType || detectedTargetColumn) && (
          <div className="flex flex-wrap gap-2 mt-2">
            {detectedProblemType && (
              <Badge variant="outline">
                <Brain className="h-3 w-3 mr-1" />
                {detectedProblemType}
              </Badge>
            )}
            {detectedTargetColumn && (
              <Badge variant="outline">
                Target: {detectedTargetColumn}
              </Badge>
            )}
          </div>
        )}
      </CardHeader>

      <CardContent>
        {/* Filters */}
        <SuggestionFilters className="mb-6" />

        {/* Results summary */}
        <div className="flex items-center justify-between mb-4">
          <p className="text-sm text-muted-foreground">
            Showing {filteredSuggestions.length} of {suggestions.length} suggestions
            {metadata.processing_time_ms && (
              <span className="ml-2">
                • Generated in {(metadata.processing_time_ms / 1000).toFixed(1)}s
              </span>
            )}
          </p>
        </div>

        {/* Suggestions tabs */}
        <Tabs defaultValue="all" className="w-full">
          <TabsList className="grid w-full grid-cols-3 mb-4">
            <TabsTrigger value="all" className="gap-1">
              All
              <Badge variant="secondary" className="ml-1">
                {filteredSuggestions.length}
              </Badge>
            </TabsTrigger>
            <TabsTrigger value="rule-based" className="gap-1">
              <Wand2 className="h-3 w-3" />
              Rule-Based
              <Badge variant="secondary" className="ml-1">
                {ruleBasedSuggestions.length}
              </Badge>
            </TabsTrigger>
            <TabsTrigger value="ai" className="gap-1">
              <Sparkles className="h-3 w-3" />
              AI
              <Badge variant="secondary" className="ml-1">
                {aiSuggestions.length}
              </Badge>
            </TabsTrigger>
          </TabsList>

          <TabsContent value="all">
            <SuggestionGrid
              suggestions={filteredSuggestions}
              viewMode={viewMode}
              isFeatureSelected={isFeatureSelected}
              onAccept={handleAccept}
              onReject={handleReject}
            />
          </TabsContent>

          <TabsContent value="rule-based">
            <SuggestionGrid
              suggestions={ruleBasedSuggestions}
              viewMode={viewMode}
              isFeatureSelected={isFeatureSelected}
              onAccept={handleAccept}
              onReject={handleReject}
            />
          </TabsContent>

          <TabsContent value="ai">
            {aiSuggestions.length > 0 ? (
              <SuggestionGrid
                suggestions={aiSuggestions}
                viewMode={viewMode}
                isFeatureSelected={isFeatureSelected}
                onAccept={handleAccept}
                onReject={handleReject}
              />
            ) : (
              <Alert>
                <Sparkles className="h-4 w-4" />
                <AlertDescription>
                  AI suggestions are being generated or are not available for this dataset.
                </AlertDescription>
              </Alert>
            )}
          </TabsContent>
        </Tabs>

        {/* Load more */}
        {filteredSuggestions.length > 0 && (
          <div className="flex justify-center mt-6">
            <Button
              variant="outline"
              onClick={handleLoadMore}
              disabled={isLoading}
            >
              {isLoading ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <ChevronRight className="mr-2 h-4 w-4" />
              )}
              Load More Suggestions
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// Helper component for suggestion grid/list
interface SuggestionGridProps {
  suggestions: FeatureSuggestion[];
  viewMode: 'grid' | 'list';
  isFeatureSelected: (id: string) => boolean;
  onAccept: (s: FeatureSuggestion) => void;
  onReject: (s: FeatureSuggestion) => void;
}

function SuggestionGrid({
  suggestions,
  viewMode,
  isFeatureSelected,
  onAccept,
  onReject,
}: SuggestionGridProps) {
  if (suggestions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
        <Sparkles className="h-12 w-12 mb-4 opacity-50" />
        <p>No suggestions match your filters</p>
      </div>
    );
  }

  return (
    <div
      className={cn(
        viewMode === 'grid'
          ? 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4'
          : 'flex flex-col gap-3'
      )}
    >
      {suggestions.map((suggestion) => (
        <FeatureSuggestionCard
          key={suggestion.id}
          suggestion={suggestion}
          isSelected={isFeatureSelected(suggestion.id)}
          onAccept={onAccept}
          onReject={onReject}
        />
      ))}
    </div>
  );
}
