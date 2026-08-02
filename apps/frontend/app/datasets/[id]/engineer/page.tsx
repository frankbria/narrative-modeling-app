'use client';

import React, { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useSession } from 'next-auth/react';
import Link from 'next/link';
import { getAuthToken } from '@/lib/auth-helpers';
import { FeatureEngineeringProvider, useFeatureEngineering } from '@/lib/contexts/FeatureEngineeringContext';
import { FeatureSuggestionPanel } from '@/components/FeatureSuggestionPanel';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import {
  ArrowLeft,
  Loader2,
  Sparkles,
  Play,
  Trash2,
  ChevronRight,
  Database,
  AlertTriangle,
  CheckCircle,
} from 'lucide-react';

interface Dataset {
  dataset_id: string;
  filename: string;
  original_filename: string;
  num_rows: number;
  num_columns: number;
  columns: string[];
  file_type: string;
}

export default function FeatureEngineeringPage() {
  const params = useParams();
  useRouter();
  useSession();
  const datasetId = params?.id as string;

  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [targetColumn, setTargetColumn] = useState<string | undefined>(undefined);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

  // Fetch dataset details
  useEffect(() => {
    const fetchDataset = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const token = await getAuthToken();

        if (!token) {
          setError('Not authenticated. Please log in.');
          setIsLoading(false);
          return;
        }

        if (!datasetId) {
          setError('No dataset ID provided');
          setIsLoading(false);
          return;
        }

        const response = await fetch(`${apiUrl}/datasets/${datasetId}`, {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        });

        if (!response.ok) {
          if (response.status === 404) {
            throw new Error('Dataset not found');
          }
          throw new Error('Failed to fetch dataset');
        }

        const data = await response.json();
        setDataset(data);
      } catch (err) {
        console.error('Error fetching dataset:', err);
        setError(err instanceof Error ? err.message : 'Failed to load dataset');
      } finally {
        setIsLoading(false);
      }
    };

    if (datasetId) {
      fetchDataset();
    }
  }, [datasetId, apiUrl]);

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <span className="text-lg text-muted-foreground">Loading dataset...</span>
        </div>
      </div>
    );
  }

  // Error state
  if (error || !dataset) {
    return (
      <div className="container mx-auto px-4 py-6">
        <Card className="border-destructive">
          <CardContent className="flex flex-col items-center justify-center h-64 space-y-4 pt-6">
            <AlertTriangle className="h-8 w-8 text-destructive" />
            <div className="text-center space-y-2">
              <h3 className="text-lg font-semibold text-destructive">
                {error || 'Dataset Not Found'}
              </h3>
              <p className="text-muted-foreground text-sm">
                Unable to load the dataset for feature engineering.
              </p>
            </div>
            <Link href="/explore">
              <Button variant="outline">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Datasets
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <FeatureEngineeringProvider datasetId={datasetId}>
      <FeatureEngineeringContent
        dataset={dataset}
        targetColumn={targetColumn}
        onTargetColumnChange={setTargetColumn}
      />
    </FeatureEngineeringProvider>
  );
}

interface FeatureEngineeringContentProps {
  dataset: Dataset;
  targetColumn: string | undefined;
  onTargetColumnChange: (column: string | undefined) => void;
}

function FeatureEngineeringContent({
  dataset,
  targetColumn,
  onTargetColumnChange,
}: FeatureEngineeringContentProps) {
  const { selectedFeatures, clearSelectedFeatures, removeFeature } = useFeatureEngineering();
  const [isApplying, setIsApplying] = useState(false);
  const [applyResult, setApplyResult] = useState<{ success: boolean; message: string } | null>(null);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

  const handleApplyFeatures = async () => {
    if (selectedFeatures.length === 0) return;

    setIsApplying(true);
    setApplyResult(null);

    try {
      const token = await getAuthToken();
      if (!token) {
        throw new Error('Not authenticated');
      }

      const response = await fetch(
        `${apiUrl}/datasets/${dataset.dataset_id}/features/apply-multiple`,
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            suggestion_ids: selectedFeatures.map((f) => f.suggestion.id),
          }),
        }
      );

      if (!response.ok) {
        throw new Error('Failed to apply features');
      }

      const result = await response.json();
      // #274: this endpoint is preview-only — the columns are computed but not
      // saved to the dataset. Report honestly so users don't assume it persisted.
      setApplyResult({
        success: true,
        message: `Previewed ${result.applied_features.length} feature(s). These are not saved — use the transformation pipeline to persist them.`,
      });
    } catch (err) {
      setApplyResult({
        success: false,
        message: err instanceof Error ? err.message : 'Failed to apply features',
      });
    } finally {
      setIsApplying(false);
    }
  };

  return (
    <div className="container mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Link href="/explore">
              <Button variant="ghost" size="sm" className="pl-0">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back
              </Button>
            </Link>
          </div>
          <div className="space-y-1 pl-2">
            <div className="flex items-center gap-2">
              <Sparkles className="h-6 w-6 text-primary" />
              <h1 className="text-3xl font-bold">Feature Engineering</h1>
            </div>
            <div className="flex items-center gap-2 text-muted-foreground">
              <Database className="h-4 w-4" />
              <span>{dataset.original_filename}</span>
              <span>•</span>
              <span>{dataset.num_rows?.toLocaleString()} rows</span>
              <span>•</span>
              <span>{dataset.num_columns} columns</span>
            </div>
          </div>
        </div>

        {/* Settings and actions */}
        <div className="flex items-center gap-2">
          {/* Target column selector */}
          <div className="flex items-center gap-2">
            <Label htmlFor="target-column" className="text-sm text-muted-foreground">
              Target:
            </Label>
            <Select value={targetColumn} onValueChange={onTargetColumnChange}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Auto-detect" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="auto">Auto-detect</SelectItem>
                {dataset.columns.map((col) => (
                  <SelectItem key={col} value={col}>
                    {col}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Selected features sheet */}
          <Sheet>
            <SheetTrigger asChild>
              <Button variant="outline" className="gap-2">
                <CheckCircle className="h-4 w-4" />
                Selected
                {selectedFeatures.length > 0 && (
                  <Badge variant="secondary">{selectedFeatures.length}</Badge>
                )}
              </Button>
            </SheetTrigger>
            <SheetContent className="w-[400px] sm:w-[540px]">
              <SheetHeader>
                <SheetTitle>Selected Features</SheetTitle>
                <SheetDescription>
                  Features you&apos;ve selected to add to your dataset
                </SheetDescription>
              </SheetHeader>
              <div className="mt-6 space-y-4">
                {selectedFeatures.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    <Sparkles className="h-12 w-12 mx-auto mb-4 opacity-50" />
                    <p>No features selected yet</p>
                    <p className="text-sm mt-2">
                      Accept suggestions from the panel to add them here
                    </p>
                  </div>
                ) : (
                  <>
                    {selectedFeatures.map((feature) => (
                      <Card key={feature.suggestion.id}>
                        <CardHeader className="py-3">
                          <div className="flex items-start justify-between">
                            <div>
                              <CardTitle className="text-sm">
                                {feature.suggestion.name}
                              </CardTitle>
                              <CardDescription className="text-xs">
                                {feature.suggestion.feature_type}
                              </CardDescription>
                            </div>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => removeFeature(feature.suggestion.id)}
                            >
                              <Trash2 className="h-4 w-4 text-destructive" />
                            </Button>
                          </div>
                        </CardHeader>
                      </Card>
                    ))}

                    <Separator />

                    <div className="flex flex-col gap-2">
                      <Button
                        onClick={handleApplyFeatures}
                        disabled={isApplying || selectedFeatures.length === 0}
                        className="w-full"
                      >
                        {isApplying ? (
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        ) : (
                          <Play className="mr-2 h-4 w-4" />
                        )}
                        Apply {selectedFeatures.length} Features
                      </Button>

                      <Button
                        variant="outline"
                        onClick={clearSelectedFeatures}
                        disabled={selectedFeatures.length === 0}
                        className="w-full"
                      >
                        <Trash2 className="mr-2 h-4 w-4" />
                        Clear All
                      </Button>
                    </div>

                    {applyResult && (
                      <div
                        className={`p-3 rounded-lg ${
                          applyResult.success
                            ? 'bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-200 dark:bg-green-900 dark:text-green-200'
                            : 'bg-red-100 dark:bg-red-900/40 text-red-800 dark:text-red-200 dark:bg-red-900 dark:text-red-200'
                        }`}
                      >
                        <p className="text-sm">{applyResult.message}</p>
                      </div>
                    )}
                  </>
                )}
              </div>
            </SheetContent>
          </Sheet>
        </div>
      </div>

      {/* Main content */}
      <FeatureSuggestionPanel
        datasetId={dataset.dataset_id}
        targetColumn={targetColumn}
      />

      {/* Next steps */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Next Steps</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            <Link href={`/datasets/${dataset.dataset_id}/prepare`}>
              <Button variant="outline" className="gap-2">
                Data Preparation
                <ChevronRight className="h-4 w-4" />
              </Button>
            </Link>
            <Link href={`/datasets/${dataset.dataset_id}/train`}>
              <Button variant="default" className="gap-2">
                Train Model
                <ChevronRight className="h-4 w-4" />
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
