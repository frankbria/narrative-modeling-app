'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useSession } from 'next-auth/react';
import { getAuthToken } from '@/lib/auth-helpers';
import { useWorkflow } from '@/lib/contexts/WorkflowContext';
import { WorkflowStage } from '@/lib/types/workflow';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Loader2, ArrowLeft, Eye, List } from 'lucide-react';
import Link from 'next/link';

// Import transformation components
import TransformationPipeline from '@/components/transformation/TransformationPipeline';
// Note: These components will be created in the next phase
// import { ColumnSelector } from '@/components/transformation/ColumnSelector';
// import { TransformationChainView } from '@/components/transformation/TransformationChainView';
// import { TransformationConfigDialog } from '@/components/transformation/TransformationConfigDialog';

interface Dataset {
  id: string;
  filename: string;
  num_rows: number;
  num_columns: number;
  schema?: any;
  file_id?: string;
}

export default function DatasetPreparePage() {
  const params = useParams();
  const router = useRouter();
  const { data: session } = useSession();
  const { state, completeStage, canAccessStage } = useWorkflow();

  const datasetId = params?.id as string;
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'visual' | 'chain'>('visual');
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

  // Check workflow access and fetch dataset
  useEffect(() => {
    if (!canAccessStage(WorkflowStage.DATA_PREPARATION)) {
      router.push('/upload');
      return;
    }

    const fetchDataset = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const token = await getAuthToken();

        if (!datasetId) {
          setError('No dataset ID provided');
          return;
        }

        const response = await fetch(`${apiUrl}/user_data/${datasetId}`, {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
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
        setError(err instanceof Error ? err.message : 'Failed to fetch dataset');
      } finally {
        setIsLoading(false);
      }
    };

    fetchDataset();
  }, [datasetId, apiUrl, canAccessStage, router]);

  // Warn before navigation if unsaved changes
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (hasUnsavedChanges) {
        e.preventDefault();
        e.returnValue = '';
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [hasUnsavedChanges]);

  const handleComplete = async (transformedDatasetId: string) => {
    try {
      // Complete DATA_PREPARATION stage
      completeStage(WorkflowStage.DATA_PREPARATION, {
        datasetId: transformedDatasetId,
        originalDatasetId: datasetId,
        timestamp: new Date().toISOString()
      });

      // Auto-advance to next stage via WorkflowContext
      // Navigation happens automatically through completeStage
    } catch (err) {
      console.error('Error completing preparation stage:', err);
      setError('Failed to complete data preparation. Please try again.');
    }
  };

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
            <div className="text-center space-y-2">
              <h3 className="text-lg font-semibold text-destructive">
                {error ? 'Error Loading Dataset' : 'Dataset Not Found'}
              </h3>
              <p className="text-muted-foreground text-sm">
                {error || 'The requested dataset could not be found.'}
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
    <div className="container mx-auto px-4 py-6 space-y-6">
      {/* Header Section */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        {/* Title and Breadcrumb */}
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
            <h1 className="text-3xl font-bold">Prepare Data</h1>
            <p className="text-muted-foreground">
              {dataset.filename} • {dataset.num_rows?.toLocaleString() || 'N/A'} rows • {dataset.num_columns || 'N/A'} columns
            </p>
          </div>
        </div>

        {/* View Toggle and Actions */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex border rounded-lg p-1 bg-muted">
            <Button
              variant={viewMode === 'visual' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setViewMode('visual')}
              className="gap-1"
            >
              <Eye className="h-4 w-4" />
              Visual
            </Button>
            <Button
              variant={viewMode === 'chain' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setViewMode('chain')}
              className="gap-1"
            >
              <List className="h-4 w-4" />
              Chain
            </Button>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="grid grid-cols-1 gap-6">
        {/* Transformation Pipeline */}
        <Card>
          <CardHeader className="border-b">
            <CardTitle className="text-lg">
              {viewMode === 'visual' ? 'Visual Pipeline' : 'Transformation Chain'}
            </CardTitle>
          </CardHeader>
          <CardContent className="p-6">
            {viewMode === 'visual' ? (
              <>
                {/* Visual Pipeline View */}
                <TransformationPipeline
                  datasetId={datasetId}
                  onComplete={handleComplete}
                  onUnsavedChanges={setHasUnsavedChanges}
                />
              </>
            ) : (
              <>
                {/* Chain View - Placeholder for future TransformationChainView component */}
                <div className="flex items-center justify-center h-64 border-2 border-dashed rounded-lg">
                  <div className="text-center text-muted-foreground">
                    <List className="h-12 w-12 mx-auto mb-2 opacity-50" />
                    <p className="text-sm">Chain view coming soon</p>
                  </div>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Information Footer */}
      <div className="flex flex-col gap-2 text-xs text-muted-foreground">
        <p>
          Changes are automatically saved. Navigate away to continue to the next stage when you're done.
        </p>
        {hasUnsavedChanges && (
          <p className="text-yellow-600 dark:text-yellow-500">
            You have unsaved changes. They will be lost if you navigate away.
          </p>
        )}
      </div>
    </div>
  );
}
