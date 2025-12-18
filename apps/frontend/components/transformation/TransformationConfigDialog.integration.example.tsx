/**
 * Integration Example: TransformationConfigDialog with Pipeline
 *
 * This file demonstrates how to integrate TransformationConfigDialog
 * with the transformation pipeline and data preparation workflow.
 */

import { useState, useCallback } from 'react';
import { TransformationConfigDialog, TransformationConfig } from './TransformationConfigDialog';
import { Button } from '@/components/ui/button';

/**
 * Example 1: Basic Pipeline Integration
 *
 * Shows how to add configurations to a transformation pipeline
 */
export function BasicPipelineIntegration() {
  const [pipeline, setPipeline] = useState<TransformationConfig[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedType, setSelectedType] = useState<string | null>(null);

  const transformationTypes = {
    fill_missing: {
      label: 'Fill Missing Values',
      description: 'Replace missing values with specified method',
      schema: {
        column: {
          type: 'string',
          title: 'Column',
          required: true,
        },
        method: {
          type: 'string',
          title: 'Fill Method',
          enum: ['mean', 'median', 'mode', 'forward', 'backward'],
          required: true,
        },
      },
    },
    remove_duplicates: {
      label: 'Remove Duplicates',
      description: 'Remove duplicate rows from dataset',
      schema: {
        columns: {
          type: 'array',
          items: { type: 'string' },
          title: 'Columns',
          required: true,
        },
        keep_strategy: {
          type: 'string',
          title: 'Keep Strategy',
          enum: ['first', 'last', 'none'],
          required: true,
        },
      },
    },
  };

  const handleAddTransformation = useCallback(
    (config: TransformationConfig) => {
      setPipeline((prev) => [...prev, config]);
      setDialogOpen(false);
    },
    []
  );

  const handleOpenDialog = (type: string) => {
    setSelectedType(type);
    setDialogOpen(true);
  };

  const currentType = selectedType
    ? transformationTypes[selectedType as keyof typeof transformationTypes]
    : null;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold mb-4">Transformation Pipeline</h2>

        {/* Transformation Menu */}
        <div className="grid grid-cols-2 gap-2 mb-6">
          {Object.entries(transformationTypes).map(([type, config]) => (
            <Button
              key={type}
              variant="outline"
              onClick={() => handleOpenDialog(type)}
            >
              {config.label}
            </Button>
          ))}
        </div>

        {/* Pipeline Display */}
        <div className="space-y-2">
          <h3 className="font-semibold">Added Transformations ({pipeline.length})</h3>
          <div className="border rounded-lg p-4 bg-gray-50">
            {pipeline.length === 0 ? (
              <p className="text-gray-500">No transformations added yet</p>
            ) : (
              <ol className="space-y-2">
                {pipeline.map((config, index) => (
                  <li key={index} className="text-sm">
                    {index + 1}. {config.type} - {JSON.stringify(config.parameters)}
                  </li>
                ))}
              </ol>
            )}
          </div>
        </div>
      </div>

      {/* Configuration Dialog */}
      {currentType && (
        <TransformationConfigDialog
          open={dialogOpen}
          onOpenChange={setDialogOpen}
          transformationType={selectedType}
          transformationLabel={currentType.label}
          transformationDescription={currentType.description}
          parametersSchema={currentType.schema}
          availableColumns={['id', 'name', 'email', 'age', 'status']}
          datasetId="dataset-123"
          onAdd={handleAddTransformation}
        />
      )}
    </div>
  );
}

/**
 * Example 2: With Preview Functionality
 *
 * Shows how to integrate preview API calls
 */
export function PipelineWithPreview() {
  const [pipeline, setPipeline] = useState<TransformationConfig[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [previewResult, setPreviewResult] = useState<any>(null);
  const [isLoadingPreview, setIsLoadingPreview] = useState(false);

  const handlePreview = async (config: TransformationConfig) => {
    setIsLoadingPreview(true);
    try {
      const response = await fetch('/api/transformations/preview', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${process.env.NEXT_PUBLIC_AUTH_TOKEN}`,
        },
        body: JSON.stringify({
          dataset_id: 'dataset-123',
          transformations: [config],
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Preview failed');
      }

      const result = await response.json();
      setPreviewResult(result);
    } finally {
      setIsLoadingPreview(false);
    }
  };

  const handleAddTransformation = (config: TransformationConfig) => {
    setPipeline((prev) => [...prev, config]);
    setDialogOpen(false);
    setPreviewResult(null);
  };

  return (
    <div className="grid grid-cols-2 gap-6">
      {/* Left: Dialog */}
      <div>
        <Button onClick={() => setDialogOpen(true)}>Add Transformation</Button>

        <TransformationConfigDialog
          open={dialogOpen}
          onOpenChange={setDialogOpen}
          transformationType="fill_missing"
          transformationLabel="Fill Missing Values"
          transformationDescription="Replace missing values"
          parametersSchema={{
            column: {
              type: 'string',
              title: 'Column',
              required: true,
            },
            method: {
              type: 'string',
              title: 'Method',
              enum: ['mean', 'median', 'mode'],
              required: true,
            },
          }}
          availableColumns={['id', 'name', 'email', 'age']}
          datasetId="dataset-123"
          onAdd={handleAddTransformation}
          onPreview={handlePreview}
        />
      </div>

      {/* Right: Preview Result */}
      <div>
        <h3 className="font-semibold mb-2">Preview Result</h3>
        <div className="border rounded-lg p-4 bg-gray-50 h-64 overflow-y-auto">
          {isLoadingPreview ? (
            <p className="text-gray-500">Loading preview...</p>
          ) : previewResult ? (
            <pre className="text-xs">
              {JSON.stringify(previewResult, null, 2)}
            </pre>
          ) : (
            <p className="text-gray-500">No preview available</p>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * Example 3: Edit/Delete Transformation
 *
 * Shows how to edit existing transformations and support deletion
 */
export function PipelineWithEditDelete() {
  const [pipeline, setPipeline] = useState<TransformationConfig[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);

  const handleAddTransformation = (config: TransformationConfig) => {
    if (editingIndex !== null) {
      // Update existing
      const newPipeline = [...pipeline];
      newPipeline[editingIndex] = config;
      setPipeline(newPipeline);
      setEditingIndex(null);
    } else {
      // Add new
      setPipeline((prev) => [...prev, config]);
    }
    setDialogOpen(false);
  };

  const handleEditTransformation = (index: number) => {
    setEditingIndex(index);
    setDialogOpen(true);
  };

  const handleDeleteTransformation = () => {
    if (editingIndex !== null) {
      setPipeline((prev) =>
        prev.filter((_, i) => i !== editingIndex)
      );
      setDialogOpen(false);
      setEditingIndex(null);
    }
  };

  const editingConfig = editingIndex !== null ? pipeline[editingIndex] : null;

  return (
    <div className="space-y-6">
      <div>
        <Button onClick={() => {
          setEditingIndex(null);
          setDialogOpen(true);
        }}>
          Add Transformation
        </Button>
      </div>

      {/* Pipeline List with Edit/Delete */}
      <div className="space-y-2">
        {pipeline.map((config, index) => (
          <div
            key={index}
            className="border rounded-lg p-4 flex justify-between items-center"
          >
            <div>
              <p className="font-semibold">Step {index + 1}: {config.type}</p>
              <p className="text-sm text-gray-600">
                {JSON.stringify(config.parameters)}
              </p>
            </div>
            <div className="space-x-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => handleEditTransformation(index)}
              >
                Edit
              </Button>
              <Button
                size="sm"
                variant="destructive"
                onClick={() => {
                  setPipeline((prev) =>
                    prev.filter((_, i) => i !== index)
                  );
                }}
              >
                Delete
              </Button>
            </div>
          </div>
        ))}
      </div>

      {/* Configuration Dialog */}
      <TransformationConfigDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        transformationType={editingConfig?.type ?? 'fill_missing'}
        transformationLabel="Configure Transformation"
        transformationDescription="Set parameters for your transformation"
        parametersSchema={{
          column: {
            type: 'string',
            title: 'Column',
            required: true,
          },
          method: {
            type: 'string',
            title: 'Method',
            enum: ['mean', 'median', 'mode'],
            required: true,
          },
        }}
        availableColumns={['id', 'name', 'email', 'age']}
        datasetId="dataset-123"
        onAdd={handleAddTransformation}
        onDelete={editingIndex !== null ? handleDeleteTransformation : undefined}
        existingConfig={editingConfig}
      />
    </div>
  );
}

/**
 * Example 4: Multi-type Transformation Builder
 *
 * Shows how to support multiple transformation types dynamically
 */
export const TRANSFORMATION_CATALOG = {
  fill_missing: {
    label: 'Fill Missing Values',
    description: 'Replace missing values with specified method',
    schema: {
      column: {
        type: 'string',
        title: 'Target Column',
        required: true,
      },
      method: {
        type: 'string',
        title: 'Fill Method',
        enum: ['mean', 'median', 'mode', 'forward', 'backward', 'value'],
        required: true,
      },
      fill_value: {
        type: 'string',
        title: 'Custom Value',
        required: false,
      },
    },
  },
  remove_duplicates: {
    label: 'Remove Duplicates',
    description: 'Remove duplicate rows from dataset',
    schema: {
      columns: {
        type: 'array',
        items: { type: 'string' },
        title: 'Columns to Consider',
        required: true,
      },
      keep_strategy: {
        type: 'string',
        title: 'Keep Strategy',
        enum: ['first', 'last', 'none'],
        required: true,
      },
    },
  },
  scale_normalize: {
    label: 'Scale/Normalize',
    description: 'Scale numeric columns to a standard range',
    schema: {
      columns: {
        type: 'array',
        items: { type: 'string' },
        title: 'Columns to Scale',
        required: true,
      },
      method: {
        type: 'string',
        title: 'Scaling Method',
        enum: ['minmax', 'standard', 'robust'],
        required: true,
      },
    },
  },
  remove_outliers: {
    label: 'Remove Outliers',
    description: 'Remove rows with outlier values',
    schema: {
      columns: {
        type: 'array',
        items: { type: 'string' },
        title: 'Columns',
        required: true,
      },
      method: {
        type: 'string',
        title: 'Detection Method',
        enum: ['iqr', 'zscore', 'isolation_forest'],
        required: true,
      },
      threshold: {
        type: 'number',
        title: 'Threshold',
        minimum: 0,
        maximum: 10,
        required: true,
      },
    },
  },
} as const;

export function MultiTypeTransformationBuilder() {
  const [pipeline, setPipeline] = useState<TransformationConfig[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedType, setSelectedType] = useState<string | null>(null);

  const handleOpenDialog = (type: string) => {
    setSelectedType(type);
    setDialogOpen(true);
  };

  const handleAddTransformation = (config: TransformationConfig) => {
    setPipeline((prev) => [...prev, config]);
    setDialogOpen(false);
  };

  const currentConfig = selectedType
    ? TRANSFORMATION_CATALOG[selectedType as keyof typeof TRANSFORMATION_CATALOG]
    : null;

  return (
    <div className="space-y-6">
      {/* Transformation Selector */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
        {Object.entries(TRANSFORMATION_CATALOG).map(([type, config]) => (
          <Button
            key={type}
            variant="outline"
            onClick={() => handleOpenDialog(type)}
            className="text-xs"
          >
            {config.label}
          </Button>
        ))}
      </div>

      {/* Pipeline Summary */}
      <div className="border rounded-lg p-4 bg-blue-50">
        <h3 className="font-semibold mb-2">
          Transformation Pipeline ({pipeline.length} steps)
        </h3>
        <ol className="space-y-1">
          {pipeline.map((config, index) => (
            <li key={index} className="text-sm">
              {index + 1}. {config.type}
            </li>
          ))}
        </ol>
      </div>

      {/* Configuration Dialog */}
      {currentConfig && (
        <TransformationConfigDialog
          open={dialogOpen}
          onOpenChange={setDialogOpen}
          transformationType={selectedType}
          transformationLabel={currentConfig.label}
          transformationDescription={currentConfig.description}
          parametersSchema={currentConfig.schema}
          availableColumns={[
            'id',
            'name',
            'email',
            'age',
            'salary',
            'department',
            'status',
          ]}
          datasetId="dataset-123"
          onAdd={handleAddTransformation}
        />
      )}
    </div>
  );
}
