'use client';

import React, { useState } from 'react';
import { useAsyncData } from '@/lib/hooks/useAsyncData';
import { API_URL } from '@/lib/constants';
import { getAuthToken } from '@/lib/auth-helpers';
import { Pencil, Trash2, Copy, Check, AlertCircle, Plus, Search, Tag } from 'lucide-react';

interface Feature {
  id: string;
  feature_id: string;
  name: string;
  description: string | null;
  formula_string: string | null;
  tags: string[];
  is_valid: boolean;
  created_at: string;
  updated_at: string;
}

interface FeatureListProps {
  datasetId: string;
  onEdit: (feature: Feature) => void;
  onCreate: () => void;
  onApply?: (featureId: string) => void;
}

/**
 * FeatureList component displays a list of saved features for a dataset.
 *
 * Provides functionality for viewing, searching, filtering by tags, editing,
 * duplicating, and deleting features. Also supports applying features to datasets.
 *
 * @param props - Component properties
 * @param props.datasetId - The ID of the dataset to load features for
 * @param props.onEdit - Callback invoked when user clicks edit on a feature
 * @param props.onCreate - Callback invoked when user clicks the New Feature button
 * @param props.onApply - Optional callback invoked when user applies a feature to the dataset
 * @returns A React element displaying the feature list with search, filter, and CRUD controls
 *
 * @remarks
 * - Features are loaded from the API on mount and when datasetId changes
 * - Supports text search by name and description
 * - Supports filtering by multiple tags (AND logic)
 * - Delete operations require user confirmation
 * - Duplicate creates a copy with "_copy" suffix
 */
export default function FeatureList({
  datasetId,
  onEdit,
  onCreate,
  onApply,
}: FeatureListProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const {
    data: featureData,
    loading,
    error,
    reload: loadFeatures,
  } = useAsyncData<Feature[]>(async () => {
    let response: Response;
    try {
      const token = await getAuthToken();
      response = await fetch(`${API_URL}/datasets/${datasetId}/features`, {
        headers: { Authorization: `Bearer ${token}` },
      });
    } catch (err) {
      // Network/auth failure: the old code reported fixed copy here, not err.message.
      console.error('Error loading features:', err);
      throw new Error('Failed to load features');
    }
    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData.detail || 'Failed to load features');
    }
    const data = await response.json();
    return (data.features || []) as Feature[];
  }, [datasetId]);
  // The delete handler removed the row optimistically via setFeatures. The list is
  // owned by the hook now, so track removals separately and filter during render —
  // same instant feedback, without refetching or reintroducing an effect.
  const [deletedIds, setDeletedIds] = useState<string[]>([]);
  const features = (featureData ?? []).filter((f) => !deletedIds.includes(f.feature_id));

  const handleDelete = async (featureId: string) => {
    if (!confirm('Are you sure you want to delete this feature?')) return;

    setDeletingId(featureId);
    try {
      const token = await getAuthToken();
      const response = await fetch(
        `${API_URL}/datasets/${datasetId}/features/${featureId}`,
        {
          method: 'DELETE',
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (response.ok) {
        setDeletedIds((prev) => [...prev, featureId]);
      } else {
        const errData = await response.json();
        alert(errData.detail || 'Failed to delete feature');
      }
    } catch (err) {
      console.error('Error deleting feature:', err);
      alert('Failed to delete feature');
    } finally {
      setDeletingId(null);
    }
  };

  const handleDuplicate = async (feature: Feature) => {
    try {
      const token = await getAuthToken();

      // Get full feature details
      const getResponse = await fetch(
        `${API_URL}/datasets/${datasetId}/features/${feature.feature_id}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!getResponse.ok) {
        alert('Failed to load feature details');
        return;
      }

      const fullFeature = await getResponse.json();

      // Create duplicate
      const createResponse = await fetch(
        `${API_URL}/datasets/${datasetId}/features`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            name: `${fullFeature.name}_copy`,
            description: fullFeature.description,
            tags: fullFeature.tags,
            expression_tree: fullFeature.expression_tree,
            output_type: fullFeature.output_type,
            canvas_state: fullFeature.canvas_state,
          }),
        }
      );

      if (createResponse.ok) {
        loadFeatures();
      } else {
        const errData = await createResponse.json();
        alert(errData.detail || 'Failed to duplicate feature');
      }
    } catch (err) {
      console.error('Error duplicating feature:', err);
      alert('Failed to duplicate feature');
    }
  };

  // Get all unique tags
  const allTags = Array.from(new Set(features.flatMap((f) => f.tags)));

  // Filter features
  const filteredFeatures = features.filter((feature) => {
    const matchesSearch =
      feature.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (feature.description?.toLowerCase().includes(searchTerm.toLowerCase()) ?? false);

    const matchesTags =
      selectedTags.length === 0 ||
      selectedTags.every((tag) => feature.tags.includes(tag));

    return matchesSearch && matchesTags;
  });

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  if (loading) {
    return (
      <div className="p-8 text-center text-muted-foreground">
        Loading features...
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 text-center">
        <AlertCircle className="w-8 h-8 text-red-500 mx-auto mb-2" />
        <p className="text-red-600">{error}</p>
        <button
          onClick={loadFeatures}
          className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Saved Features ({features.length})</h2>
        <button
          onClick={onCreate}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          <Plus className="w-4 h-4" />
          New Feature
        </button>
      </div>

      {/* Search and Filters */}
      <div className="mb-4 space-y-3">
        <div className="relative">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search features..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border rounded-lg"
          />
        </div>

        {allTags.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {allTags.map((tag) => (
              <button
                key={tag}
                onClick={() =>
                  setSelectedTags((prev) =>
                    prev.includes(tag)
                      ? prev.filter((t) => t !== tag)
                      : [...prev, tag]
                  )
                }
                className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-sm ${
                  selectedTags.includes(tag)
                    ? 'bg-blue-600 text-white'
                    : 'bg-muted text-foreground hover:bg-gray-200'
                }`}
              >
                <Tag className="w-3 h-3" />
                {tag}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Feature List */}
      {filteredFeatures.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          {features.length === 0 ? (
            <>
              <p className="text-lg font-medium">No features yet</p>
              <p className="text-sm mt-1">Create your first feature using the builder</p>
            </>
          ) : (
            <p>No features match your search</p>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          {filteredFeatures.map((feature) => (
            <div
              key={feature.feature_id}
              className="p-4 bg-card border rounded-lg hover:shadow-sm transition-shadow"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className="font-medium">{feature.name}</h3>
                    {feature.is_valid ? (
                      <Check className="w-4 h-4 text-green-600" />
                    ) : (
                      <AlertCircle className="w-4 h-4 text-amber-500" />
                    )}
                  </div>

                  {feature.description && (
                    <p className="text-sm text-muted-foreground mt-1">{feature.description}</p>
                  )}

                  {feature.formula_string && (
                    <code className="block mt-2 text-xs font-mono bg-muted px-2 py-1 rounded text-foreground max-w-full overflow-hidden text-ellipsis">
                      {feature.formula_string}
                    </code>
                  )}

                  <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                    <span>Created {formatDate(feature.created_at)}</span>
                    {feature.tags.length > 0 && (
                      <div className="flex gap-1">
                        {feature.tags.map((tag) => (
                          <span
                            key={tag}
                            className="px-1.5 py-0.5 bg-muted rounded text-muted-foreground"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-1 ml-4">
                  {onApply && (
                    <button
                      onClick={() => onApply(feature.feature_id)}
                      className="px-3 py-1.5 text-sm bg-green-600 text-white rounded hover:bg-green-700"
                    >
                      Apply
                    </button>
                  )}
                  <button
                    onClick={() => onEdit(feature)}
                    className="p-2 hover:bg-muted rounded"
                    title="Edit"
                  >
                    <Pencil className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleDuplicate(feature)}
                    className="p-2 hover:bg-muted rounded"
                    title="Duplicate"
                  >
                    <Copy className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleDelete(feature.feature_id)}
                    disabled={deletingId === feature.feature_id}
                    className="p-2 hover:bg-red-100 dark:hover:bg-red-900/40 rounded text-red-600 disabled:opacity-50"
                    title="Delete"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
