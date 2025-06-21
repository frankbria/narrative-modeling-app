'use client';

import { useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { useSession } from 'next-auth/react';
import { TransformationPipeline } from '@/components/TransformationPipeline';
import { TransformationSidebar } from '@/components/TransformationSidebar';
import { TransformationPreview } from '@/components/TransformationPreview';
import { RecipeBrowser } from '@/components/RecipeBrowser';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Wand2, Save, Play, History, BookOpen } from 'lucide-react';
import { TransformationService } from '@/lib/services/transformation';
import { getAuthToken } from '@/lib/auth-helpers';
import axios from 'axios';
import { API_BASE_URL } from '@/lib/config';

export default function TransformPage() {
  const searchParams = useSearchParams();
  const datasetId = searchParams.get('datasetId');
  const { data: session } = useSession();
  
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [selectedNode, setSelectedNode] = useState(null);
  const [previewData, setPreviewData] = useState(null);
  const [isApplying, setIsApplying] = useState(false);
  const [activeTab, setActiveTab] = useState('build');
  const [datasetInfo, setDatasetInfo] = useState(null);
  const [suggestions, setSuggestions] = useState([]);

  useEffect(() => {
    if (datasetId) {
      fetchDatasetInfo();
      fetchSuggestions();
    }
  }, [datasetId]);

  const fetchDatasetInfo = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/data/${datasetId}`, {
        headers: {
          'Authorization': `Bearer ${await getAuthToken()}`
        }
      });
      setDatasetInfo(response.data);
    } catch (error) {
      console.error('Failed to fetch dataset info:', error);
    }
  };

  const fetchSuggestions = async () => {
    if (!session || !datasetId) return;
    
    try {
      const token = await getAuthToken();
      const response = await TransformationService.getTransformationSuggestions(datasetId, token);
      setSuggestions(response.suggestions);
    } catch (error) {
      console.error('Failed to fetch suggestions:', error);
    }
  };

  const handleNodeAdd = (transformationType) => {
    // Add new transformation node to the pipeline
    const newNode = {
      id: `node-${nodes.length + 1}`,
      type: 'transformation',
      position: { x: 250, y: nodes.length * 100 + 50 },
      data: {
        type: transformationType,
        parameters: {},
        label: transformationType.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
      }
    };
    setNodes([...nodes, newNode]);
  };

  const handleNodeSelect = (node) => {
    setSelectedNode(node);
    if (node) {
      previewTransformation(node);
    }
  };

  const previewTransformation = async (node) => {
    if (!session || !datasetId) return;
    
    try {
      const token = await getAuthToken();
      const response = await TransformationService.previewTransformation(
        {
          dataset_id: datasetId,
          transformation_type: node.data.type,
          parameters: node.data.parameters,
          preview_rows: 100
        },
        token
      );
      setPreviewData(response);
    } catch (error) {
      console.error('Preview failed:', error);
    }
  };

  const buildTransformationPipeline = () => {
    // Build ordered list of transformations from nodes and edges
    return nodes.map(node => ({
      type: node.data.type,
      parameters: node.data.parameters
    }));
  };

  const handleApplyTransformations = async () => {
    if (!session || !datasetId) return;
    
    setIsApplying(true);
    try {
      const transformations = buildTransformationPipeline();
      const token = await getAuthToken();
      const response = await TransformationService.applyTransformationPipeline(
        {
          dataset_id: datasetId,
          transformations: transformations.map(t => ({
            type: t.type,
            parameters: t.parameters,
            description: `Apply ${t.type}`
          }))
        },
        token
      );
      
      if (response.success) {
        // Show success message and refresh dataset info
        await fetchDatasetInfo();
        // Clear the pipeline after successful application
        setNodes([]);
        setEdges([]);
        setSelectedNode(null);
        setPreviewData(null);
      }
    } catch (error) {
      console.error('Apply transformations failed:', error);
    } finally {
      setIsApplying(false);
    }
  };

  const handleAutoClean = async () => {
    if (!session || !datasetId) return;
    
    try {
      const token = await getAuthToken();
      const response = await TransformationService.autoCleanDataset(
        {
          dataset_id: datasetId,
          options: {
            remove_duplicates: true,
            trim_whitespace: true,
            handle_missing: 'impute'
          }
        },
        token
      );
      
      if (response.success) {
        // Refresh and show results
        await fetchDatasetInfo();
      }
    } catch (error) {
      console.error('Auto-clean failed:', error);
    }
  };


  // Authentication guard
  if (!session) {
    return (
      <div className="container mx-auto p-8">
        <div className="text-center">
          <h2 className="text-2xl font-bold mb-4">Authentication Required</h2>
          <p className="text-muted-foreground">Please sign in to access the transformation pipeline.</p>
        </div>
      </div>
    );
  }

  if (!datasetId) {
    return (
      <div className="container mx-auto p-8">
        <div className="text-center">
          <h2 className="text-2xl font-bold mb-4">No Dataset Selected</h2>
          <p className="text-muted-foreground">Please select a dataset from the Explore page to start transforming.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col">
      <div className="border-b p-4">
        <div className="container mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Transform Data</h1>
            <p className="text-sm text-muted-foreground">
              {datasetInfo?.filename || 'Loading...'}
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={handleAutoClean}
              disabled={isApplying}
            >
              <Wand2 className="w-4 h-4 mr-2" />
              Auto Clean
            </Button>
            <Button
              onClick={handleApplyTransformations}
              disabled={isApplying || nodes.length === 0}
            >
              <Play className="w-4 h-4 mr-2" />
              Apply Transformations
            </Button>
          </div>
        </div>
      </div>

      <div className="flex-1 flex">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col">
          <TabsList className="px-4">
            <TabsTrigger value="build">Build Pipeline</TabsTrigger>
            <TabsTrigger value="recipes">
              <BookOpen className="w-4 h-4 mr-2" />
              Recipes
            </TabsTrigger>
            <TabsTrigger value="history">
              <History className="w-4 h-4 mr-2" />
              History
            </TabsTrigger>
          </TabsList>

          <TabsContent value="build" className="flex-1 flex p-0">
            <TransformationSidebar 
              onTransformationAdd={handleNodeAdd}
              datasetInfo={datasetInfo}
            />
            <div className="flex-1 flex flex-col">
              <TransformationPipeline
                nodes={nodes}
                edges={edges}
                onNodesChange={setNodes}
                onEdgesChange={setEdges}
                onNodeSelect={handleNodeSelect}
              />
              <TransformationPreview
                previewData={previewData}
                selectedNode={selectedNode}
              />
            </div>
          </TabsContent>

          <TabsContent value="recipes" className="flex-1 p-4">
            <RecipeBrowser
              datasetId={datasetId}
              onApplyRecipe={(recipe) => {
                // Load recipe transformations into pipeline
                setActiveTab('build');
              }}
            />
          </TabsContent>

          <TabsContent value="history" className="flex-1 p-4">
            <div>Transformation history will be shown here</div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}