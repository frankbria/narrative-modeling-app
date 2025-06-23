'use client'

// apps/frontend/app/review/page.tsx
import { useSession } from 'next-auth/react'
import { getAuthToken } from '@/lib/auth-helpers'
import { useState, useEffect, useCallback } from 'react'
import { StatsCard } from '@/components/StatsCard'
import { calculateDescriptiveStats, StatItem } from '@/lib/utils'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useDatasetChatContext } from '@/lib/hooks/useDatasetChatContext';
import ReactMarkdown from 'react-markdown';
import { CorrelationHeatmap } from "@/components/CorrelationHeatmap";
import { useRouter } from 'next/navigation';
import { ArrowRight, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import Link from 'next/link';
import { API_URL } from '@/lib/constants';

interface UserData {
  id: string;
  user_id: string;
  file_name: string;
  file_path: string;
  file_size: number;
  file_type: string;
  upload_date: string;
  schema: StatItem[];
  histogram_data: Record<string, number[]>;
  boxplot_data: Record<string, number[]>;
  preview_data: Record<string, string | number | boolean | null>[];
  previewData?: Array<Array<string | number | boolean | null>>;
  headers?: string[];
  ai_summary: string;
  error?: string;
}

interface Dataset {
  _id: string;
  filename: string;
  num_rows: number;
  num_columns: number;
  created_at: string;
  user_id: string;
}

interface AISummary {
  overview: string;
  issues: string[];
  relationships: string[];
  suggestions: string[];
}

export default function ReviewPage() {
  const { data: session } = useSession()
  const router = useRouter()
  const [data, setData] = useState<UserData | null>(null)
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [selectedDatasetId, setSelectedDatasetId] = useState<string | null>(null)
  const [stats, setStats] = useState<StatItem[]>([])
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const { isLoading: isLoadingAISummary, error: aiSummaryError, isAvailable: isAISummaryAvailable } = useDatasetChatContext(data?.id || null);
  const [aiSummary, setAiSummary] = useState<AISummary | null>(null);

  const fetchDatasets = useCallback(async () => {
    if (!session?.user?.id) return

    try {
      const response = await fetch(`${API_URL}/user_data`, {
        headers: {
          'Authorization': `Bearer ${await getAuthToken()}`
        }
      })

      if (!response.ok) {
        throw new Error('Failed to fetch datasets')
      }

      const result = await response.json()
      setDatasets(result)
    } catch (err) {
      console.error('Error fetching datasets:', err)
      setError(err instanceof Error ? err.message : 'An error occurred')
    }
  }, [session])

  const fetchPreviewData = useCallback(async () => {
    if (!session?.user?.id || !selectedDatasetId) return

    try {
      setIsLoading(true)
      setError(null)
      
      const response = await fetch(`${API_URL}/user_data/preview/${selectedDatasetId}`, {
        headers: {
          'Authorization': `Bearer ${await getAuthToken()}`
        }
      })

      if (!response.ok) {
        const errorText = await response.text()
        throw new Error(`Failed to fetch preview data: ${errorText}`)
      }

      const result = await response.json()
      
      // Transform the data to match our UserData interface
      const transformedData: UserData = {
        id: result.id,
        user_id: session.user.id,
        file_name: result.fileName,
        file_path: result.s3_url,
        file_size: 0, // Not provided by API
        file_type: result.fileType,
        upload_date: result.created_at || new Date().toISOString(),
        schema: result.schema || [],
        histogram_data: {},
        boxplot_data: {},
        preview_data: [],
        previewData: result.previewData,
        headers: result.headers,
        ai_summary: '',
        error: result.error
      }
      
      setData(transformedData)
      
      // Calculate descriptive statistics
      if (result.headers && result.previewData) {
        const calculatedStats = calculateDescriptiveStats(result.previewData, result.headers)
        setStats(calculatedStats)
      }
    } catch (err) {
      console.error('Error fetching preview data:', err)
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setIsLoading(false)
    }
  }, [session, selectedDatasetId])

  useEffect(() => {
    if (session) {
      fetchDatasets()
    }
  }, [session, fetchDatasets])

  useEffect(() => {
    if (selectedDatasetId) {
      fetchPreviewData()
    }
  }, [selectedDatasetId, fetchPreviewData])

  useEffect(() => {
    const fetchAISummary = async () => {
      if (!data?.id) return;

      try {
        const response = await fetch(`${API_URL}/user_data/${data.id}/ai-summary`, {
          headers: {
            'Authorization': `Bearer ${await getAuthToken()}`
          }
        });

        if (!response.ok) {
          throw new Error(`Failed to fetch AI summary: ${await response.text()}`);
        }

        const summary = await response.json();
        setAiSummary({
          overview: summary.overview || '',
          issues: summary.issues || [],
          relationships: summary.relationships || [],
          suggestions: summary.suggestions || []
        });
      } catch (error) {
        console.error('Error fetching AI summary:', error);
        setAiSummary(null);
      }
    };

    fetchAISummary();
  }, [data?.id, session]);

  const handleDatasetSelect = (datasetId: string) => {
    setSelectedDatasetId(datasetId)
  }

  const handleNextStep = () => {
    if (selectedDatasetId) {
      router.push(`/explore/${selectedDatasetId}`)
    }
  }

  if (!session) return <p>Please log in to access this page.</p>
  
  return (
    <div className="flex-1 p-6 space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Dataset Review</h1>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <Loader2 className="h-6 w-6 animate-spin mr-2 text-blue-600" />
          <span>Loading data...</span>
        </div>
      ) : error ? (
        <div className="text-red-500 p-6">{error}</div>
      ) : !data ? (
        <div className="text-gray-500 p-6">Select a dataset to view its analysis</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="md:col-span-1">
            <Card>
              <CardHeader>
                <CardTitle>Select Dataset</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {datasets.length === 0 ? (
                    <div className="text-center">
                      <p className="text-gray-500 mb-4">No datasets available</p>
                      <Link href="/upload">
                        <Button className="w-full">Upload Dataset</Button>
                      </Link>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {datasets.map((dataset) => (
                        <div
                          key={dataset._id}
                          className={`p-3 rounded-lg cursor-pointer transition-colors ${
                            selectedDatasetId === dataset._id
                              ? 'bg-blue-100 border-2 border-blue-500 shadow-md'
                              : 'hover:bg-gray-50 border border-gray-200'
                          }`}
                          onClick={() => handleDatasetSelect(dataset._id)}
                        >
                          <h3 className="font-medium">{dataset.filename}</h3>
                          <p className="text-sm text-gray-500">
                            {dataset.num_rows} rows × {dataset.num_columns} columns
                          </p>
                          <p className="text-sm text-gray-500">
                            Created: {new Date(dataset.created_at).toLocaleDateString()}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                  {selectedDatasetId && (
                    <div className="mt-4">
                      <Button onClick={handleNextStep} className="w-full flex items-center justify-center gap-2 bg-blue-500 text-white">
                        Next Step <ArrowRight className="h-4 w-4" />
                        Explore Data
                      </Button>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="md:col-span-3">
            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>AI Analysis</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="mt-6">
                      {isLoadingAISummary ? (
                        <div className="text-sm text-gray-500">
                          <p>Loading AI analysis...</p>
                        </div>
                      ) : aiSummaryError ? (
                        <div className="text-sm text-red-500">
                          <p>Error loading AI analysis: {aiSummaryError}</p>
                        </div>
                      ) : !isAISummaryAvailable ? (
                        <div className="text-sm text-gray-500">
                          <p>AI analysis is not yet available. It will be generated automatically after the dataset is processed.</p>
                        </div>
                      ) : (
                        <div className="space-y-6">
                          <div className="bg-blue-50 p-4 rounded-lg border border-blue-200">
                            <h4 className="text-blue-800 font-bold mb-2">Overview</h4>
                            <div className="text-blue-700">
                              <ReactMarkdown>{aiSummary?.overview || 'No overview available.'}</ReactMarkdown>
                            </div>
                          </div>
                          
                          <div className="bg-yellow-50 p-4 rounded-lg border border-yellow-200">
                            <h4 className="text-yellow-800 font-bold mb-2">Potential Issues</h4>
                            <div className="text-yellow-700">
                              <ReactMarkdown>
                                {aiSummary?.issues && aiSummary.issues.length > 0
                                  ? aiSummary.issues.map((issue: string) => `- ${issue}`).join('\n')
                                  : 'No potential issues identified.'}
                              </ReactMarkdown>
                            </div>
                          </div>
                          
                          <div className="bg-green-50 p-4 rounded-lg border border-green-200">
                            <h4 className="text-green-800 font-bold mb-2">Potential Relationships</h4>
                            <div className="text-green-700">
                              <ReactMarkdown>
                                {aiSummary?.relationships && aiSummary.relationships.length > 0
                                  ? aiSummary.relationships.map((relationship: string) => `- ${relationship}`).join('\n')
                                  : 'No potential relationships identified.'}
                              </ReactMarkdown>
                            </div>
                          </div>
                          
                          <div className="bg-purple-50 p-4 rounded-lg border border-purple-200">
                            <h4 className="text-purple-800 font-bold mb-2">Recommendations</h4>
                            <div className="text-purple-700">
                              <ReactMarkdown>
                                {aiSummary?.suggestions && aiSummary.suggestions.length > 0
                                  ? aiSummary.suggestions.map((suggestion: string) => `- ${suggestion}`).join('\n')
                                  : 'No recommendations available.'}
                              </ReactMarkdown>
                            </div>
                          </div>

                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6 text-sm text-gray-500">
                            <div>
                              <p>Upload Date</p>
                              <p className="font-medium text-gray-700">
                                {data.upload_date ? new Date(data.upload_date).toLocaleString() : 'Unknown'}
                              </p>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      )}
      
      {data && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="md:col-span-4">
            {stats.length > 0 && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                {stats.map((stat, index) => (
                  <StatsCard key={index} stats={stat} />
                ))}
              </div>
            )}
            
            {data.schema && data.schema.length > 0 && (
              <Card className="mt-6">
                <CardHeader>
                  <CardTitle>Correlation Analysis</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="w-full overflow-x-auto">
                    <div className="min-w-[600px]">
                      {(() => {
                        console.log('Rendering CorrelationHeatmap with schema:', data.schema);
                        console.log('schema length:', data.schema.length);
                        console.log('schema structure:', JSON.stringify(data.schema, null, 2));
                        
                        // Check if there are any numeric fields
                        const numericFields = data.schema.filter(
                          field => field.field_type === 'numeric'
                        );
                        console.log('Numeric fields count:', numericFields.length);
                        
                        return (
                          <CorrelationHeatmap 
                            stats={data.schema}
                          />
                        );
                      })()}
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
            
            {data.schema && data.schema.length > 0 ? (
              <Card className="mt-6">
                <CardHeader>
                  <CardTitle>Data Preview</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="overflow-x-auto">
                    {(() => {
                      console.log('Data Preview - data:', data);
                      console.log('Data Preview - previewData:', data.previewData);
                      console.log('Data Preview - headers:', data.headers);
                      
                      // Check if previewData exists and has items
                      if (!data.previewData || data.previewData.length === 0) {
                        return (
                          <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-md text-yellow-700">
                            <p className="font-medium">No preview data available</p>
                            <p className="text-sm mt-1">
                              The preview data could not be loaded. This might be due to an issue with the data format.
                            </p>
                          </div>
                        );
                      }
                      
                      // Get headers from API response or schema
                      const headers = data.headers || data.schema.map(field => field.field_name);
                      
                      return (
                        <Table>
                          <TableHeader>
                            <TableRow className="bg-gray-800">
                              {headers.map((header, index) => (
                                <TableHead key={index} className="text-white font-semibold">
                                  {header}
                                </TableHead>
                              ))}
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {data.previewData.map((row, rowIndex) => (
                              <TableRow
                                key={rowIndex}
                                className={rowIndex % 2 === 0 ? 'bg-white' : 'bg-gray-50'}
                              >
                                {row.map((cell, cellIndex) => (
                                  <TableCell key={cellIndex} className="text-gray-900">
                                    {cell !== null && cell !== undefined ? String(cell) : ''}
                                  </TableCell>
                                ))}
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      );
                    })()}
                  </div>
                </CardContent>
              </Card>
            ) : (
              <Card className="mt-6">
                <CardHeader>
                  <CardTitle>Data Preview</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-md text-yellow-700">
                    <p className="font-medium">No preview data available</p>
                    <p className="text-sm mt-1">
                      {data.error ? data.error : "The preview data could not be loaded. This might be due to an issue with the S3 storage or file format."}
                    </p>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
