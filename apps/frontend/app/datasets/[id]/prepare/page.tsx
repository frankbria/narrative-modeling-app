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
import { TransformationChainView, TransformationStep } from '@/components/transformation/TransformationChainView';
import { TransformationConfigDialog, TransformationConfig } from '@/components/transformation/TransformationConfigDialog';

interface Dataset {
  id: string;
  filename: string;
  num_rows: number;
  num_columns: number;
  schema?: Record<string, unknown>;
  file_id?: string;
}

/**
 * DatasetPreparePage Component
 *
 * Provides a data preparation interface for applying transformations to uploaded datasets.
 * Manages two view modes: visual (ReactFlow pipeline) and chain (linear list).
 *
 * State Management:
 * - transformations: Array of transformation steps (persisted in localStorage)
 * - viewMode: Current view mode ('visual' | 'chain')
 * - editingIndex: Index of transformation being edited (null when dialog closed)
 * - availableColumns: Column names from dataset for transformation config
 * - transformationTypes: Available transformation types from backend API
 *
 * @returns {JSX.Element} The data preparation page with transformation pipeline
 */
export default function DatasetPreparePage() {
  const params = useParams();
  const router = useRouter();
  useSession();
  const { completeStage, canAccessStage, isHydrated } = useWorkflow();

  const datasetId = params?.id as string;
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'visual' | 'chain'>('visual');
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [transformations, setTransformations] = useState<TransformationStep[]>([]);

  // Edit dialog state
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [availableColumns, setAvailableColumns] = useState<string[]>([]);
  const [transformationTypes, setTransformationTypes] = useState<Record<string, unknown>[]>([]);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

  // Load saved transformations from backend/localStorage
  useEffect(() => {
    const loadTransformations = async () => {
      try {
        // Try to load from localStorage first (draft state)
        const savedTransformations = localStorage.getItem(`transformations_${datasetId}`);
        if (savedTransformations) {
          const parsed = JSON.parse(savedTransformations);
          setTransformations(parsed);
        }
      } catch (err) {
        console.error('Failed to load transformations:', err);
      }
    };

    if (datasetId) {
      loadTransformations();
    }
  }, [datasetId]);

  // Save transformations to localStorage when they change
  useEffect(() => {
    if (!datasetId) return;

    try {
      if (transformations.length > 0) {
        localStorage.setItem(`transformations_${datasetId}`, JSON.stringify(transformations));
      } else {
        // Clear localStorage when all transformations are deleted
        localStorage.removeItem(`transformations_${datasetId}`);
      }
    } catch (err) {
      console.error('Failed to save/clear transformations:', err);
    }
  }, [transformations, datasetId]);

  // Check workflow access and fetch dataset
  useEffect(() => {
    // Wait for workflow state to hydrate before gating — checking too early
    // always sees an empty state and wrongly redirects to /upload
    if (!isHydrated) {
      return;
    }

    if (!canAccessStage(WorkflowStage.DATA_PREPARATION)) {
      router.push('/upload');
      return;
    }

    const fetchDataset = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const token = await getAuthToken();

        if (!token) {
          setError('Not authenticated. Please log in to continue.');
          setIsLoading(false);
          return;
        }

        if (!datasetId) {
          setError('No dataset ID provided');
          setIsLoading(false);
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
  }, [datasetId, apiUrl, canAccessStage, router, isHydrated]);

  // Fetch transformation types and available columns for edit dialog
  useEffect(() => {
    const fetchMetadata = async () => {
      try {
        const token = await getAuthToken();

        if (!token) {
          console.error('Cannot fetch metadata: Not authenticated');
          return;
        }

        // Fetch available transformation types
        const typesResponse = await fetch(`${apiUrl}/transformations/available`, {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        });

        if (typesResponse.ok) {
          const typesData = await typesResponse.json();
          setTransformationTypes(typesData.transformations || []);
        }

        // Fetch available columns from dataset preview
        if (datasetId) {
          const columnsResponse = await fetch(`${apiUrl}/data/${datasetId}/preview`, {
            headers: {
              Authorization: `Bearer ${token}`,
              'Content-Type': 'application/json'
            }
          });

          if (columnsResponse.ok) {
            const columnsData = await columnsResponse.json();
            if (columnsData.columns && Array.isArray(columnsData.columns)) {
              const columnNames = columnsData.columns.map((col: { name: string }) => col.name);
              setAvailableColumns(columnNames);
            }
          }
        }
      } catch (err) {
        console.error('Failed to fetch metadata for edit dialog:', err);
      }
    };

    if (datasetId) {
      fetchMetadata();
    }
  }, [datasetId, apiUrl]);

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

  /**
   * Completes the data preparation stage and advances workflow
   *
   * @param {string} transformedDatasetId - The ID of the transformed dataset from backend
   * @returns {Promise<void>}
   *
   * Side effects:
   * - Completes DATA_PREPARATION workflow stage via WorkflowContext
   * - Stores completion metadata (datasetId, originalDatasetId, timestamp)
   * - Triggers automatic navigation to next workflow stage
   * - Sets error state if completion fails
   */
  const handleComplete = async (transformedDatasetId: string) => {
    try {
      // Complete DATA_PREPARATION and auto-advance. autoAdvance is opt-in (#88);
      // this alternate prepare route has no explicit Continue CTA, so it opts in
      // to keep its one-step flow. (The previous implicit default never actually
      // navigated — canAccessStage saw the pre-completion state — so this also
      // fixes a latent dead-navigation bug.)
      completeStage(WorkflowStage.DATA_PREPARATION, {
        datasetId: transformedDatasetId,
        originalDatasetId: datasetId,
        timestamp: new Date().toISOString()
      }, { autoAdvance: true });
    } catch (err) {
      console.error('Error completing preparation stage:', err);
      setError('Failed to complete data preparation. Please try again.');
    }
  };

  /**
   * Reorders transformations in the chain by moving a step from one position to another
   *
   * @param {number} startIndex - Current index of the transformation to move
   * @param {number} endIndex - Target index where the transformation should be placed
   * @returns {void}
   *
   * Side effects:
   * - Updates transformations state array with new order
   * - Marks changes as unsaved (triggers browser warning on navigation)
   * - Triggers localStorage save via useEffect
   */
  const handleReorder = (startIndex: number, endIndex: number) => {
    const newTransformations = [...transformations];
    const [movedItem] = newTransformations.splice(startIndex, 1);
    newTransformations.splice(endIndex, 0, movedItem);
    setTransformations(newTransformations);
    setHasUnsavedChanges(true);
  };

  /**
   * Opens the edit dialog for a transformation at the specified index
   *
   * @param {number} index - Index of the transformation to edit
   * @returns {void}
   *
   * Side effects:
   * - Sets editingIndex state, triggering TransformationConfigDialog to render
   * - Dialog pre-populated with existing transformation configuration
   */
  const handleEditTransformation = (index: number) => {
    setEditingIndex(index);
  };

  /**
   * Saves changes from the edit dialog to update a transformation
   *
   * @param {TransformationConfig} config - Updated transformation configuration from dialog
   * @returns {void}
   *
   * Side effects:
   * - Updates transformation at editingIndex with new type, label, and parameters
   * - Closes edit dialog by setting editingIndex to null
   * - Marks changes as unsaved
   * - Triggers localStorage save via useEffect
   */
  const handleSaveEdit = (config: TransformationConfig) => {
    if (editingIndex === null) return;

    const newTransformations = [...transformations];
    // The dialog cannot change the transformation type during an edit and its
    // payload carries no label — only the parameters may be updated, otherwise
    // the formatted label would be clobbered with the raw type string.
    newTransformations[editingIndex] = {
      ...newTransformations[editingIndex],
      parameters: config.parameters
    };

    setTransformations(newTransformations);
    setEditingIndex(null);
    setHasUnsavedChanges(true);
  };

  /**
   * Cancels editing and closes the edit dialog without saving changes
   *
   * @returns {void}
   *
   * Side effects:
   * - Closes edit dialog by setting editingIndex to null
   */
  const handleCancelEdit = () => {
    setEditingIndex(null);
  };

  /**
   * Deletes a transformation from the chain
   *
   * @param {number} index - Index of the transformation to delete
   * @returns {void}
   *
   * Side effects:
   * - Removes transformation at specified index from state array
   * - Marks changes as unsaved
   * - Triggers localStorage save or cleanup via useEffect
   */
  const handleDeleteTransformation = (index: number) => {
    const newTransformations = transformations.filter((_, i) => i !== index);
    setTransformations(newTransformations);
    setHasUnsavedChanges(true);
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
                {/* Visual Pipeline View. This page owns its own Visual/Chain
                    toggle, so suppress the pipeline's built-in one (#275) to
                    avoid a duplicate toggle. */}
                <TransformationPipeline
                  datasetId={datasetId}
                  onComplete={handleComplete}
                  onUnsavedChanges={setHasUnsavedChanges}
                  showViewToggle={false}
                />
              </>
            ) : (
              <>
                {/* Chain View - Linear list of transformation steps */}
                <TransformationChainView
                  transformations={transformations}
                  onReorder={handleReorder}
                  onEdit={handleEditTransformation}
                  onDelete={handleDeleteTransformation}
                  className="min-h-[400px]"
                />
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Information Footer */}
      <div className="flex flex-col gap-2 text-xs text-muted-foreground">
        <p>
          Changes are saved locally in your browser. Use the Complete button to save to the server and continue.
        </p>
        {hasUnsavedChanges && (
          <p className="text-yellow-600 dark:text-yellow-500">
            You have unsaved changes that are not yet saved to the server.
          </p>
        )}
      </div>

      {/* Edit Transformation Dialog */}
      {/* Guard on transformations[editingIndex]: the index can briefly outlive
          its array entry (e.g. a delete while the dialog is open), and accessing
          .type on undefined would crash the page. */}
      {editingIndex !== null && transformations[editingIndex] && (() => {
        const editingType = transformations[editingIndex].type;
        const typeMeta = transformationTypes.find(
          (t) => t.type === editingType
        );
        return (
          <TransformationConfigDialog
            open={editingIndex !== null}
            onOpenChange={(open) => {
              if (!open) handleCancelEdit();
            }}
            transformationType={editingType}
            transformationLabel={
              (typeMeta?.label as string | undefined) ??
              transformations[editingIndex].label
            }
            transformationDescription={
              (typeMeta?.description as string | undefined) ?? ''
            }
            parametersSchema={
              (typeMeta?.parameters_schema as Record<string, unknown> | undefined) ?? {}
            }
            existingConfig={{
              type: editingType,
              label: transformations[editingIndex].label,
              parameters: transformations[editingIndex].parameters
            }}
            availableColumns={availableColumns}
            datasetId={datasetId}
            onAdd={handleSaveEdit}
          />
        );
      })()}
    </div>
  );
}
