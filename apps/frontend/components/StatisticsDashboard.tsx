'use client'

import React, { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { CorrelationHeatmap } from './CorrelationHeatmap'
import { HistogramChart } from './HistogramChart'
import { BoxplotChart } from './BoxplotChart'
import { 
  BarChart3, 
  TrendingUp, 
  AlertTriangle,
  Database,
  Percent,
  Target
} from 'lucide-react'

interface ColumnStatistic {
  column_name: string
  data_type: string
  total_count: number
  null_count: number
  null_percentage: number
  unique_count: number
  unique_percentage: number
  mean?: number
  median?: number
  std_dev?: number
  min_value?: number
  max_value?: number
  q1?: number
  q3?: number
  outlier_count?: number
  outlier_percentage?: number
  most_frequent_values?: Array<{value: any, count: number, percentage: number}>
}

interface StatisticsData {
  row_count: number
  column_count: number
  memory_usage_mb: number
  correlation_matrix?: Record<string, Record<string, number>>
  column_statistics: ColumnStatistic[]
  missing_value_summary: {
    total_missing_values: number
    columns_with_missing: number
    complete_columns: number
  }
}

interface StatisticsDashboardProps {
  datasetId: string
  statistics?: StatisticsData
}

export function StatisticsDashboard({ datasetId, statistics: initialStats }: StatisticsDashboardProps) {
  const [statistics, setStatistics] = useState<StatisticsData | null>(initialStats || null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedColumn, setSelectedColumn] = useState<string | null>(null)

  useEffect(() => {
    if (!statistics) {
      fetchStatistics()
    }
  }, [datasetId])

  const fetchStatistics = async () => {
    try {
      setLoading(true)
      const response = await fetch(`/api/data/${datasetId}/statistics`, {
        credentials: 'include',
      })

      if (!response.ok) {
        throw new Error('Failed to fetch statistics')
      }

      const data = await response.json()
      setStatistics(data.statistics)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  if (loading && !statistics) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center h-64">
          <p className="text-muted-foreground">Loading statistics...</p>
        </CardContent>
      </Card>
    )
  }

  if (error || !statistics) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center h-64">
          <p className="text-destructive">Error: {error || 'No statistics available'}</p>
        </CardContent>
      </Card>
    )
  }

  const numericColumns = statistics.column_statistics.filter(col => 
    ['integer', 'float', 'currency', 'percentage'].includes(col.data_type)
  )

  const categoricalColumns = statistics.column_statistics.filter(col => 
    ['categorical', 'string', 'boolean'].includes(col.data_type)
  )

  return (
    <div className="space-y-6">
      {/* Overview Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center space-x-2">
              <Database className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-2xl font-bold">{statistics.row_count.toLocaleString()}</p>
                <p className="text-xs text-muted-foreground">Rows</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center space-x-2">
              <BarChart3 className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-2xl font-bold">{statistics.column_count}</p>
                <p className="text-xs text-muted-foreground">Columns</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center space-x-2">
              <Percent className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-2xl font-bold">
                  {((1 - statistics.missing_value_summary.total_missing_values / (statistics.row_count * statistics.column_count)) * 100).toFixed(1)}%
                </p>
                <p className="text-xs text-muted-foreground">Complete</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center space-x-2">
              <Target className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-2xl font-bold">{statistics.memory_usage_mb.toFixed(1)}</p>
                <p className="text-xs text-muted-foreground">MB</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Statistics Tabs */}
      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="numeric">Numeric</TabsTrigger>
          <TabsTrigger value="categorical">Categorical</TabsTrigger>
          <TabsTrigger value="correlations">Correlations</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          {/* Missing Values Summary */}
          <Card>
            <CardHeader>
              <CardTitle>Missing Values</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-4 text-center">
                <div>
                  <p className="text-2xl font-bold text-red-600">
                    {statistics.missing_value_summary.total_missing_values.toLocaleString()}
                  </p>
                  <p className="text-sm text-muted-foreground">Total Missing</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-yellow-600">
                    {statistics.missing_value_summary.columns_with_missing}
                  </p>
                  <p className="text-sm text-muted-foreground">Columns Affected</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-green-600">
                    {statistics.missing_value_summary.complete_columns}
                  </p>
                  <p className="text-sm text-muted-foreground">Complete Columns</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Top Issues */}
          <Card>
            <CardHeader>
              <CardTitle>Data Quality Issues</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {statistics.column_statistics
                  .filter(col => col.null_percentage > 10 || (col.outlier_percentage && col.outlier_percentage > 5))
                  .slice(0, 5)
                  .map((col, index) => (
                    <div key={index} className="flex items-center justify-between p-3 bg-muted rounded-lg">
                      <div>
                        <p className="font-medium">{col.column_name}</p>
                        <p className="text-sm text-muted-foreground">
                          {col.null_percentage > 10 && `${col.null_percentage.toFixed(1)}% missing`}
                          {col.null_percentage > 10 && col.outlier_percentage && col.outlier_percentage > 5 && ' • '}
                          {col.outlier_percentage && col.outlier_percentage > 5 && `${col.outlier_percentage.toFixed(1)}% outliers`}
                        </p>
                      </div>
                      <AlertTriangle className="h-5 w-5 text-yellow-600" />
                    </div>
                  ))}
                {statistics.column_statistics
                  .filter(col => col.null_percentage > 10 || (col.outlier_percentage && col.outlier_percentage > 5))
                  .length === 0 && (
                  <p className="text-center text-muted-foreground py-8">No significant issues detected</p>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="numeric" className="space-y-4">
          <div className="grid gap-4">
            {numericColumns.map((col) => (
              <Card key={col.column_name}>
                <CardHeader>
                  <CardTitle className="text-base">{col.column_name}</CardTitle>
                  <CardDescription>
                    {col.data_type} • {col.unique_count.toLocaleString()} unique values
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                      <p className="text-muted-foreground">Mean</p>
                      <p className="font-semibold">{col.mean?.toFixed(2) || 'N/A'}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Median</p>
                      <p className="font-semibold">{col.median?.toFixed(2) || 'N/A'}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Std Dev</p>
                      <p className="font-semibold">{col.std_dev?.toFixed(2) || 'N/A'}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Outliers</p>
                      <p className="font-semibold">{col.outlier_count || 0} ({(col.outlier_percentage || 0).toFixed(1)}%)</p>
                    </div>
                  </div>
                  
                  {/* Mini histogram would go here */}
                  <div className="mt-4">
                    <HistogramChart datasetId={datasetId} column={col.column_name} height={100} />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="categorical" className="space-y-4">
          <div className="grid gap-4">
            {categoricalColumns.map((col) => (
              <Card key={col.column_name}>
                <CardHeader>
                  <CardTitle className="text-base">{col.column_name}</CardTitle>
                  <CardDescription>
                    {col.data_type} • {col.unique_count.toLocaleString()} unique values
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div className="flex justify-between text-sm">
                      <span>Cardinality</span>
                      <Badge variant={col.unique_percentage > 90 ? 'destructive' : col.unique_percentage > 50 ? 'secondary' : 'default'}>
                        {col.unique_percentage.toFixed(1)}%
                      </Badge>
                    </div>
                    
                    {col.most_frequent_values && (
                      <div className="space-y-2">
                        <p className="text-sm font-medium">Most Frequent Values</p>
                        {col.most_frequent_values.slice(0, 5).map((item, index) => (
                          <div key={index} className="flex items-center justify-between text-sm">
                            <span className="truncate max-w-[200px]">{String(item.value)}</span>
                            <div className="flex items-center gap-2">
                              <Progress value={item.percentage} className="w-16 h-2" />
                              <span className="text-muted-foreground">{item.percentage.toFixed(1)}%</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="correlations">
          {statistics.correlation_matrix ? (
            <Card>
              <CardHeader>
                <CardTitle>Correlation Matrix</CardTitle>
                <CardDescription>
                  Correlation between numeric variables
                </CardDescription>
              </CardHeader>
              <CardContent>
                <CorrelationHeatmap datasetId={datasetId} />
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="flex items-center justify-center h-32">
                <p className="text-muted-foreground">No correlation data available</p>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}