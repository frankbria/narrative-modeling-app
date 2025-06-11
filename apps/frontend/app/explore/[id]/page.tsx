'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { useAuth } from '@clerk/nextjs'
import Link from 'next/link'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Loader2, ArrowLeft, BarChart3, Database, Brain, CheckCircle2, TrendingUp } from 'lucide-react'

// Import our new components
import { DataPreviewTable } from '@/components/DataPreviewTable'
import { SchemaViewer } from '@/components/SchemaViewer'
import { StatisticsDashboard } from '@/components/StatisticsDashboard'
import { QualityReportCard } from '@/components/QualityReportCard'
import { AIInsightsPanel } from '@/components/AIInsightsPanel'
import { InteractiveVisualizationDashboard } from '@/components/InteractiveVisualizationDashboard'

interface ProcessedDataset {
  id: string
  filename: string
  is_processed: boolean
  schema: any
  statistics: any
  quality_report: any
  data_preview: any[]
  processed_at: string
}

export default function DatasetAnalysisPage() {
  const params = useParams()
  const { getToken } = useAuth()
  const [dataset, setDataset] = useState<ProcessedDataset | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState('overview')

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

  useEffect(() => {
    const fetchDataset = async () => {
      try {
        setIsLoading(true)
        const token = await getToken()
        const datasetId = params?.id as string

        if (!datasetId) {
          setError('No dataset ID provided')
          return
        }

        // Fetch dataset metadata
        const response = await fetch(`${apiUrl}/api/v1/user_data/${datasetId}`, {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        })

        if (!response.ok) {
          throw new Error('Failed to fetch dataset')
        }

        const data = await response.json()
        setDataset(data)

        // If not processed, start processing
        if (!data.is_processed) {
          await processDataset(datasetId, token)
        }
      } catch (err) {
        console.error('Error fetching dataset:', err)
        setError(err instanceof Error ? err.message : 'Failed to fetch dataset')
      } finally {
        setIsLoading(false)
      }
    }

    fetchDataset()
  }, [params?.id, getToken, apiUrl])

  const processDataset = async (datasetId: string, token: string) => {
    try {
      const response = await fetch(`${apiUrl}/api/v1/data/process`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ file_id: datasetId })
      })

      if (response.ok) {
        const processedData = await response.json()
        setDataset(prev => prev ? { ...prev, ...processedData } : null)
      }
    } catch (err) {
      console.error('Error processing dataset:', err)
    }
  }

  const handleExport = async () => {
    try {
      const token = await getToken()
      const response = await fetch(`${apiUrl}/api/v1/data/${dataset?.id}/export`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ format: 'csv' })
      })

      if (response.ok) {
        const exportData = await response.json()
        // Handle download URL
        window.open(exportData.download_url, '_blank')
      }
    } catch (err) {
      console.error('Error exporting dataset:', err)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-64">
        <Loader2 className="h-8 w-8 animate-spin mr-3 text-primary" />
        <span className="text-lg">Loading dataset...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6">
        <Card>
          <CardContent className="flex flex-col items-center justify-center h-64 space-y-4">
            <p className="text-destructive text-lg">{error}</p>
            <Link href="/explore">
              <Button variant="outline">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Datasets
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (!dataset) {
    return (
      <div className="p-6">
        <Card>
          <CardContent className="flex flex-col items-center justify-center h-64 space-y-4">
            <p className="text-muted-foreground text-lg">Dataset not found</p>
            <Link href="/explore">
              <Button variant="outline">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Datasets
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Link href="/explore">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back
              </Button>
            </Link>
            <h1 className="text-3xl font-bold">{dataset.filename}</h1>
          </div>
          <div className="flex items-center gap-4 text-muted-foreground">
            {dataset.is_processed ? (
              <div className="flex items-center gap-1 text-green-600">
                <CheckCircle2 className="h-4 w-4" />
                <span className="text-sm">Processed</span>
              </div>
            ) : (
              <div className="flex items-center gap-1 text-yellow-600">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span className="text-sm">Processing...</span>
              </div>
            )}
            {dataset.processed_at && (
              <span className="text-sm">
                Processed {new Date(dataset.processed_at).toLocaleDateString()}
              </span>
            )}
          </div>
        </div>
        <Button onClick={handleExport} disabled={!dataset.is_processed}>
          Export Data
        </Button>
      </div>

      {!dataset.is_processed ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center h-64 space-y-4">
            <Loader2 className="h-12 w-12 animate-spin text-primary" />
            <div className="text-center">
              <h3 className="text-lg font-semibold">Processing Dataset</h3>
              <p className="text-muted-foreground">
                Analyzing schema, calculating statistics, and assessing quality...
              </p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="grid w-full grid-cols-6">
            <TabsTrigger value="overview" className="flex items-center gap-2">
              <Database className="h-4 w-4" />
              Overview
            </TabsTrigger>
            <TabsTrigger value="schema" className="flex items-center gap-2">
              <BarChart3 className="h-4 w-4" />
              Schema
            </TabsTrigger>
            <TabsTrigger value="statistics" className="flex items-center gap-2">
              <BarChart3 className="h-4 w-4" />
              Statistics
            </TabsTrigger>
            <TabsTrigger value="visualizations" className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4" />
              Visualizations
            </TabsTrigger>
            <TabsTrigger value="quality" className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4" />
              Quality
            </TabsTrigger>
            <TabsTrigger value="insights" className="flex items-center gap-2">
              <Brain className="h-4 w-4" />
              AI Insights
            </TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <Card>
                <CardContent className="p-4">
                  <div className="flex items-center space-x-2">
                    <Database className="h-5 w-5 text-primary" />
                    <div>
                      <p className="text-2xl font-bold">
                        {dataset.schema?.row_count?.toLocaleString() || 'N/A'}
                      </p>
                      <p className="text-sm text-muted-foreground">Rows</p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="p-4">
                  <div className="flex items-center space-x-2">
                    <BarChart3 className="h-5 w-5 text-primary" />
                    <div>
                      <p className="text-2xl font-bold">
                        {dataset.schema?.column_count || 'N/A'}
                      </p>
                      <p className="text-sm text-muted-foreground">Columns</p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="p-4">
                  <div className="flex items-center space-x-2">
                    <CheckCircle2 className="h-5 w-5 text-primary" />
                    <div>
                      <p className="text-2xl font-bold">
                        {dataset.quality_report?.overall_quality_score 
                          ? (dataset.quality_report.overall_quality_score * 100).toFixed(1) + '%'
                          : 'N/A'
                        }
                      </p>
                      <p className="text-sm text-muted-foreground">Quality Score</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            <DataPreviewTable datasetId={dataset.id} onExport={handleExport} />
          </TabsContent>

          <TabsContent value="schema">
            {dataset.schema ? (
              <SchemaViewer schema={dataset.schema} />
            ) : (
              <Card>
                <CardContent className="flex items-center justify-center h-32">
                  <p className="text-muted-foreground">Schema information not available</p>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          <TabsContent value="statistics">
            {dataset.statistics ? (
              <StatisticsDashboard 
                datasetId={dataset.id} 
                statistics={dataset.statistics}
              />
            ) : (
              <Card>
                <CardContent className="flex items-center justify-center h-32">
                  <p className="text-muted-foreground">Statistics not available</p>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          <TabsContent value="visualizations">
            {dataset.schema?.columns ? (
              <InteractiveVisualizationDashboard
                datasetId={dataset.id}
                columns={dataset.schema.columns.map((col: any) => ({
                  name: col.name,
                  type: col.type === 'int64' || col.type === 'float64' || col.type === 'number' ? 'numeric' :
                        col.type === 'object' || col.type === 'string' ? 'categorical' :
                        col.type === 'datetime64[ns]' || col.type === 'datetime' ? 'datetime' : 'text',
                  unique_count: col.unique_count,
                  null_count: col.null_count
                }))}
                statistics={dataset.statistics}
              />
            ) : (
              <Card>
                <CardContent className="flex items-center justify-center h-32">
                  <p className="text-muted-foreground">Schema information required for visualizations</p>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          <TabsContent value="quality">
            {dataset.quality_report ? (
              <QualityReportCard report={dataset.quality_report} />
            ) : (
              <Card>
                <CardContent className="flex items-center justify-center h-32">
                  <p className="text-muted-foreground">Quality report not available</p>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          <TabsContent value="insights">
            <AIInsightsPanel datasetId={dataset.id} />
          </TabsContent>
        </Tabs>
      )}
    </div>
  )
} 