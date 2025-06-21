"use client";

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { 
  Database, 
  TrendingUp, 
  Users, 
  Home,
  Download,
  Eye,
  CheckCircle,
  ArrowRight,
  BarChart,
  Target
} from 'lucide-react';

interface SampleDataset {
  dataset_id: string;
  name: string;
  description: string;
  size_mb: number;
  rows: number;
  columns: number;
  problem_type: string;
  difficulty_level: string;
  tags: string[];
  preview_data: Array<Record<string, any>>;
  target_column: string;
  feature_columns: string[];
  learning_objectives: string[];
  expected_accuracy?: number;
  download_url: string;
  documentation_url?: string;
}

interface SampleDatasetSelectorProps {
  onDatasetSelected: (datasetId: string) => void;
}

export function SampleDatasetSelector({ onDatasetSelected }: SampleDatasetSelectorProps) {
  const [datasets, setDatasets] = useState<SampleDataset[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedDataset, setSelectedDataset] = useState<SampleDataset | null>(null);
  const [loadingDataset, setLoadingDataset] = useState<string | null>(null);

  useEffect(() => {
    loadSampleDatasets();
  }, []);

  const loadSampleDatasets = async () => {
    try {
      const response = await fetch('/api/v1/onboarding/sample-datasets');
      const data = await response.json();
      setDatasets(data);
    } catch (error) {
      console.error('Failed to load sample datasets:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadDataset = async (datasetId: string) => {
    try {
      setLoadingDataset(datasetId);
      
      const response = await fetch(`/api/v1/onboarding/sample-datasets/${datasetId}/load`, {
        method: 'POST'
      });
      
      const result = await response.json();
      
      if (result.success) {
        onDatasetSelected(datasetId);
        // You might want to show a success message or redirect
        console.log('Dataset loaded successfully:', result);
      }
    } catch (error) {
      console.error('Failed to load dataset:', error);
    } finally {
      setLoadingDataset(null);
    }
  };

  const getDifficultyColor = (level: string) => {
    switch (level) {
      case 'beginner': return 'bg-green-100 text-green-800';
      case 'intermediate': return 'bg-yellow-100 text-yellow-800';
      case 'advanced': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getProblemTypeIcon = (type: string) => {
    switch (type) {
      case 'binary_classification': return <Target className="h-4 w-4" />;
      case 'multiclass_classification': return <BarChart className="h-4 w-4" />;
      case 'regression': return <TrendingUp className="h-4 w-4" />;
      default: return <Database className="h-4 w-4" />;
    }
  };

  const getDatasetIcon = (datasetId: string) => {
    switch (datasetId) {
      case 'customer_churn': return <Users className="h-8 w-8 text-blue-500" />;
      case 'house_prices': return <Home className="h-8 w-8 text-green-500" />;
      case 'marketing_response': return <TrendingUp className="h-8 w-8 text-purple-500" />;
      default: return <Database className="h-8 w-8 text-gray-500" />;
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <Card key={i} className="animate-pulse">
            <CardHeader>
              <div className="h-4 bg-gray-200 rounded w-3/4"></div>
              <div className="h-3 bg-gray-200 rounded w-1/2"></div>
            </CardHeader>
            <CardContent>
              <div className="h-20 bg-gray-200 rounded"></div>
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="text-center space-y-2">
        <h3 className="text-lg font-semibold">Choose a Sample Dataset</h3>
        <p className="text-gray-600">
          Perfect for learning! These curated datasets help you understand different ML concepts.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {datasets.map((dataset) => (
          <Card 
            key={dataset.dataset_id} 
            className={`cursor-pointer transition-all hover:shadow-md ${
              selectedDataset?.dataset_id === dataset.dataset_id 
                ? 'ring-2 ring-blue-500 border-blue-500' 
                : ''
            }`}
            onClick={() => setSelectedDataset(dataset)}
          >
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  {getDatasetIcon(dataset.dataset_id)}
                  <div>
                    <CardTitle className="text-lg">{dataset.name}</CardTitle>
                    <div className="flex items-center gap-2 mt-1">
                      <Badge variant="secondary" className={getDifficultyColor(dataset.difficulty_level)}>
                        {dataset.difficulty_level}
                      </Badge>
                      <div className="flex items-center gap-1 text-sm text-gray-500">
                        {getProblemTypeIcon(dataset.problem_type)}
                        <span className="capitalize">
                          {dataset.problem_type.replace('_', ' ')}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              <CardDescription className="text-sm">
                {dataset.description}
              </CardDescription>
            </CardHeader>

            <CardContent className="space-y-4">
              {/* Dataset Stats */}
              <div className="grid grid-cols-3 gap-2 text-center text-xs">
                <div>
                  <div className="font-medium text-blue-600">{dataset.rows.toLocaleString()}</div>
                  <div className="text-gray-500">Rows</div>
                </div>
                <div>
                  <div className="font-medium text-green-600">{dataset.columns}</div>
                  <div className="text-gray-500">Columns</div>
                </div>
                <div>
                  <div className="font-medium text-purple-600">{dataset.size_mb}MB</div>
                  <div className="text-gray-500">Size</div>
                </div>
              </div>

              {/* Tags */}
              <div className="flex flex-wrap gap-1">
                {dataset.tags.slice(0, 3).map((tag) => (
                  <Badge key={tag} variant="outline" className="text-xs">
                    {tag}
                  </Badge>
                ))}
                {dataset.tags.length > 3 && (
                  <Badge variant="outline" className="text-xs">
                    +{dataset.tags.length - 3} more
                  </Badge>
                )}
              </div>

              {/* Expected Accuracy */}
              {dataset.expected_accuracy && (
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-600">Expected Accuracy:</span>
                  <span className="font-medium text-green-600">
                    {(dataset.expected_accuracy * 100).toFixed(0)}%
                  </span>
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex gap-2 pt-2">
                <Button 
                  size="sm" 
                  variant="outline" 
                  className="flex-1"
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedDataset(dataset);
                  }}
                >
                  <Eye className="mr-1 h-3 w-3" />
                  Preview
                </Button>
                <Button 
                  size="sm" 
                  className="flex-1"
                  disabled={loadingDataset === dataset.dataset_id}
                  onClick={(e) => {
                    e.stopPropagation();
                    loadDataset(dataset.dataset_id);
                  }}
                >
                  {loadingDataset === dataset.dataset_id ? (
                    <>
                      <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-white mr-1" />
                      Loading...
                    </>
                  ) : (
                    <>
                      <Download className="mr-1 h-3 w-3" />
                      Use This
                    </>
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Dataset Detail Modal/Panel */}
      {selectedDataset && (
        <Card className="border-2 border-blue-200 bg-blue-50">
          <CardHeader>
            <div className="flex items-start justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  {getDatasetIcon(selectedDataset.dataset_id)}
                  {selectedDataset.name}
                </CardTitle>
                <CardDescription>{selectedDataset.description}</CardDescription>
              </div>
              <Button 
                onClick={() => setSelectedDataset(null)}
                variant="ghost" 
                size="sm"
              >
                ✕
              </Button>
            </div>
          </CardHeader>

          <CardContent className="space-y-4">
            {/* Learning Objectives */}
            <div>
              <h4 className="font-medium mb-2">What you'll learn:</h4>
              <ul className="space-y-1">
                {selectedDataset.learning_objectives.map((objective, index) => (
                  <li key={index} className="flex items-start gap-2 text-sm">
                    <CheckCircle className="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
                    <span>{objective}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Data Preview */}
            <div>
              <h4 className="font-medium mb-2">Data Preview:</h4>
              <div className="overflow-x-auto">
                <table className="w-full text-xs border-collapse border border-gray-300">
                  <thead>
                    <tr className="bg-gray-100">
                      {Object.keys(selectedDataset.preview_data[0] || {}).map((column) => (
                        <th key={column} className="border border-gray-300 px-2 py-1 text-left">
                          {column}
                          {column === selectedDataset.target_column && (
                            <Badge className="ml-1 text-xs" variant="secondary">Target</Badge>
                          )}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {selectedDataset.preview_data.slice(0, 3).map((row, index) => (
                      <tr key={index}>
                        {Object.values(row).map((value, colIndex) => (
                          <td key={colIndex} className="border border-gray-300 px-2 py-1">
                            {String(value)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex gap-3 pt-2">
              <Button 
                className="flex-1"
                disabled={loadingDataset === selectedDataset.dataset_id}
                onClick={() => loadDataset(selectedDataset.dataset_id)}
              >
                {loadingDataset === selectedDataset.dataset_id ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2" />
                    Loading Dataset...
                  </>
                ) : (
                  <>
                    <Download className="mr-2 h-4 w-4" />
                    Load This Dataset
                  </>
                )}
              </Button>
              
              {selectedDataset.documentation_url && (
                <Button variant="outline">
                  <ArrowRight className="mr-2 h-4 w-4" />
                  Learn More
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}