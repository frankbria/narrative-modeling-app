'use client'

import React, { useState, useEffect, useMemo } from 'react'
import { useAsyncData } from '@/lib/hooks/useAsyncData'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Loader2, Download, RefreshCw, Filter, Eye, BarChart3 } from 'lucide-react'

import { ChartControls, ChartFilter } from './ChartControls'
import { HistogramChart } from './HistogramChart'
import { BoxplotChart } from './BoxplotChart'
import { CorrelationHeatmap } from './CorrelationHeatmap'
import { ScatterPlotChart, ScatterPlotData } from './ScatterPlotChart'
import { LineChart, LineChartData } from './LineChart'
import {
  BoxPlotData,
  getBoxPlot,
  getScatterPlot,
  getLineChart,
  getHistogram,
} from '@/lib/services/visualization'
import { getAuthToken } from '@/lib/auth-helpers'
import { StatItem } from '@/lib/utils'
import { DatasetStatistics, NUMERIC_DATA_TYPES } from '@/lib/types/api'

interface Column {
  name: string
  type: 'numeric' | 'categorical' | 'datetime' | 'text'
  unique_count?: number
  null_count?: number
}

interface InteractiveVisualizationDashboardProps {
  datasetId: string
  columns: Column[]
  statistics?: DatasetStatistics
}

export function InteractiveVisualizationDashboard({
  datasetId,
  columns,
  statistics
}: InteractiveVisualizationDashboardProps) {
  const [activeTab, setActiveTab] = useState('configure')
  const [activeChart, setActiveChart] = useState('histogram')
  const [rawSelectedColumns, setSelectedColumns] = useState<string[]>([])
  const [filters, setFilters] = useState<ChartFilter[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Real chart data fetched from the backend (issue #170). Histogram fetches
  // itself via HistogramChart's datasetId/column mode; correlation is derived
  // from the `statistics` prop, so only these three need local state here.
  const [boxplotData, setBoxplotData] = useState<BoxPlotData | null>(null)
  const [scatterData, setScatterData] = useState<ScatterPlotData | null>(null)
  const [lineData, setLineData] = useState<LineChartData | null>(null)
  // Bumping this re-runs the fetch effect and remounts HistogramChart.
  const [refreshKey, setRefreshKey] = useState(0)

  // Chart configuration state
  const [showGrid, setShowGrid] = useState(true)
  const [showAnimations, setShowAnimations] = useState(true)
  const [binCount, setBinCount] = useState(50)

  // Memoised because selectedColumns derives from it and that feeds an effect's
  // dependency list; a fresh array per render would refetch forever.
  const numericColumns = useMemo(
    () => columns.filter(col => col.type === 'numeric'),
    [columns],
  )
  const categoricalColumns = columns.filter(col => col.type === 'categorical')
  const datetimeColumns = columns.filter(col => col.type === 'datetime')

  // Auto-select the first numeric column when nothing is chosen. Derived during
  // render rather than written back by an effect: the default is a function of
  // the columns, so storing it only creates a second source of truth.
  // Memoised, not just derived: this feeds the chart-fetch effect's dependency
  // list, so returning a fresh array each render would refetch forever.
  const selectedColumns = useMemo(
    () =>
      rawSelectedColumns.length === 0 && numericColumns.length > 0
        ? [numericColumns[0].name]
        : rawSelectedColumns,
    [rawSelectedColumns, numericColumns],
  )

  // The numeric columns the user has currently selected, in selection order.
  const selectedNumeric = selectedColumns.filter(name =>
    numericColumns.some(col => col.name === name)
  )



  // Fetch real data for the active chart from the backend. Histogram and
  // correlation are handled elsewhere (HistogramChart fetch mode / statistics
  // prop), so this only drives boxplot, scatter, and line.
  useEffect(() => {
    if (activeChart !== 'boxplot' && activeChart !== 'scatter' && activeChart !== 'line') {
      setLoading(false)
      setError(null)
      return
    }

    const numericNames = new Set(
      columns.filter(col => col.type === 'numeric').map(col => col.name)
    )
    const numericSelected = selectedColumns.filter(name => numericNames.has(name))
    // Line charts plot a numeric Y series against any-type X (e.g. a date), so
    // X is the first selected column and Y is the remaining numeric columns.
    const lineX = selectedColumns[0]
    const lineY = selectedColumns.slice(1).filter(name => numericNames.has(name))

    // Requirements per chart — renderChart() shows matching guidance and we
    // never fabricate data. Clear any previously fetched data so a now-invalid
    // selection can't be exported.
    const canFetch =
      activeChart === 'boxplot'
        ? numericSelected.length >= 1
        : activeChart === 'scatter'
          ? numericSelected.length >= 2
          : lineX !== undefined && lineY.length >= 1
    if (!datasetId || !canFetch) {
      setLoading(false)
      setError(null)
      if (activeChart === 'boxplot') setBoxplotData(null)
      else if (activeChart === 'scatter') setScatterData(null)
      else setLineData(null)
      return
    }

    let cancelled = false
    setLoading(true)
    setError(null)
    // Clear the active chart's previous data up front so an in-flight refetch or
    // a failed request can't be exported as the current selection's data.
    if (activeChart === 'boxplot') setBoxplotData(null)
    else if (activeChart === 'scatter') setScatterData(null)
    else setLineData(null)

    const run = async () => {
      try {
        const token = (await getAuthToken()) ?? undefined
        if (activeChart === 'boxplot') {
          const result = await getBoxPlot(datasetId, numericSelected[0], token)
          if (!cancelled) setBoxplotData(result)
        } else if (activeChart === 'scatter') {
          const result = await getScatterPlot(
            datasetId,
            numericSelected[0],
            numericSelected[1],
            filters,
            token
          )
          if (!cancelled) setScatterData(result)
        } else {
          const result = await getLineChart(datasetId, lineX, lineY, filters, token)
          if (!cancelled) setLineData(result)
        }
      } catch (err) {
        // Data was cleared above and stays cleared on failure, so export sees no
        // stale data for the current chart.
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load chart data')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    run()
    return () => {
      cancelled = true
    }
  }, [activeChart, datasetId, selectedColumns, filters, columns, refreshKey])

  const handleColumnToggle = (columnName: string) => {
    // Base the toggle on the derived selection so un-picking the auto-selected
    // column behaves the way it did when that default was stored.
    setSelectedColumns(() => {
      const prev = selectedColumns
      if (prev.includes(columnName)) {
        return prev.filter(name => name !== columnName)
      } else {
        // Limit based on chart type
        const maxColumns = activeChart === 'scatter' ? 2 : activeChart === 'line' ? 4 : 1
        if (prev.length >= maxColumns) {
          return [columnName]
        }
        return [...prev, columnName]
      }
    })
  }

  const handleExportChart = async () => {
    try {
      // Export the real data backing the active chart. Histogram fetches itself
      // inside HistogramChart, so re-fetch the selected column's data on demand.
      let exportData: unknown = null
      if (activeChart === 'correlation') {
        exportData = statistics?.correlation_matrix ?? null
      } else if (activeChart === 'boxplot') {
        exportData = boxplotData
      } else if (activeChart === 'scatter') {
        exportData = scatterData
      } else if (activeChart === 'line') {
        exportData = lineData
      } else if (activeChart === 'histogram' && datasetId && selectedNumeric.length > 0) {
        const token = (await getAuthToken()) ?? undefined
        exportData = await getHistogram(datasetId, selectedNumeric[0], binCount, token)
      }

      if (exportData == null) {
        setError('No chart data available to export yet')
        return
      }

      const dataStr = JSON.stringify(exportData, null, 2)
      const dataBlob = new Blob([dataStr], { type: 'application/json' })
      const url = URL.createObjectURL(dataBlob)
      const link = document.createElement('a')
      link.href = url
      link.download = `${activeChart}_${datasetId}.json`
      link.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error('Export failed:', err)
      setError(err instanceof Error ? err.message : 'Export failed')
    }
  }

  const handleRefreshChart = () => {
    setError(null)
    setRefreshKey(key => key + 1)
  }

  const getChartTypeRecommendations = () => {
    const numSelected = selectedColumns.length
    const recommendations: string[] = []

    if (numSelected === 0) {
      recommendations.push('Select columns to see chart recommendations')
    } else if (numSelected === 1) {
      const col = columns.find(c => c.name === selectedColumns[0])
      if (col?.type === 'numeric') {
        recommendations.push('Histogram, Box Plot')
      } else if (col?.type === 'categorical') {
        recommendations.push('Bar Chart')
      }
    } else if (numSelected === 2) {
      const types = selectedColumns.map(name => columns.find(c => c.name === name)?.type)
      if (types.every(t => t === 'numeric')) {
        recommendations.push('Scatter Plot, Line Chart')
      } else if (types.includes('numeric') && types.includes('categorical')) {
        recommendations.push('Box Plot (grouped), Bar Chart')
      }
    } else {
      recommendations.push('Line Chart, Correlation Heatmap')
    }

    return recommendations
  }

  // Derive StatItem entries for the correlation heatmap. Prefer the provided
  // statistics payload when available, otherwise fall back to the column list.
  const correlationStats: StatItem[] = (() => {
    const columnStats = statistics?.column_statistics
    if (Array.isArray(columnStats)) {
      return columnStats
        // External API payload: guard against malformed (non-object) entries.
        .filter((col) => col !== null && typeof col === 'object')
        .map((col) => ({
          field_name: col.column_name ?? '',
          field_type: (NUMERIC_DATA_TYPES as readonly string[]).includes(col.data_type)
            ? 'numeric'
            : col.data_type ?? '',
          count: col.total_count ?? 0,
          missing_values: col.null_count ?? 0,
          unique_values: col.unique_count ?? 0
        }))
    }
    return columns.map((col) => ({
      field_name: col.name,
      field_type: col.type === 'numeric' ? 'numeric' : col.type,
      count: 0,
      missing_values: col.null_count ?? 0,
      unique_values: col.unique_count ?? 0
    }))
  })()

  const renderChart = () => {
    if (loading) {
      return (
        <div className="flex items-center justify-center h-96">
          <Loader2 className="h-8 w-8 animate-spin mr-2" />
          <span>Loading visualization...</span>
        </div>
      )
    }

    if (error) {
      return (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )
    }

    if (!selectedColumns.length) {
      return (
        <div className="flex items-center justify-center h-96 text-muted-foreground">
          <div className="text-center">
            <BarChart3 className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>Select columns to visualize</p>
          </div>
        </div>
      )
    }

    const emptyState = (message: string) => (
      <div className="flex items-center justify-center h-96 text-muted-foreground">
        <div className="text-center">
          <BarChart3 className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <p>{message}</p>
        </div>
      </div>
    )

    switch (activeChart) {
      case 'histogram':
        if (selectedNumeric.length < 1) {
          return emptyState('Select a numeric column to view its histogram')
        }
        // HistogramChart fetches its own data and renders loading/empty/error
        // states internally. `key` forces a refetch when the user hits refresh.
        return (
          <HistogramChart
            key={`${selectedNumeric[0]}-${binCount}-${refreshKey}`}
            datasetId={datasetId}
            column={selectedNumeric[0]}
            bins={binCount}
          />
        )

      case 'scatter':
        if (selectedNumeric.length < 2) {
          return emptyState('Select two numeric columns (X and Y) to plot a scatter chart')
        }
        return scatterData
          ? <ScatterPlotChart data={scatterData} />
          : emptyState('No data available for the selected columns')

      case 'line': {
        const lineY = selectedColumns.slice(1).filter(name =>
          numericColumns.some(col => col.name === name)
        )
        if (selectedColumns.length < 2 || lineY.length < 1) {
          return emptyState('Select an X column and at least one numeric Y column for a line chart')
        }
        return lineData
          ? <LineChart data={lineData} />
          : emptyState('No data available for the selected columns')
      }

      case 'boxplot':
        if (selectedNumeric.length < 1) {
          return emptyState('Select a numeric column to view its box plot')
        }
        return boxplotData
          ? <BoxplotChart data={boxplotData} />
          : emptyState('No data available for the selected column')

      case 'correlation':
        return (
          <CorrelationHeatmap
            stats={correlationStats}
            correlationMatrix={statistics?.correlation_matrix ?? null}
          />
        )

      default:
        return emptyState('This chart type is not supported yet')
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Eye className="h-5 w-5" />
            Interactive Data Visualization
          </CardTitle>
          <CardDescription>
            Explore your data with interactive charts and filters
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
            <TabsList>
              <TabsTrigger value="configure">Configure</TabsTrigger>
              <TabsTrigger value="visualize">Visualize</TabsTrigger>
              <TabsTrigger value="insights">Insights</TabsTrigger>
            </TabsList>

            <TabsContent value="configure" className="space-y-4">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Column Selection */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">Select Columns</CardTitle>
                    <CardDescription>
                      Choose columns for visualization ({selectedColumns.length} selected)
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {/* Numeric Columns */}
                      {numericColumns.length > 0 && (
                        <div>
                          <h4 className="text-sm font-medium mb-2 text-green-700">
                            Numeric ({numericColumns.length})
                          </h4>
                          <div className="grid grid-cols-2 gap-2">
                            {numericColumns.map(col => (
                              <Button
                                key={col.name}
                                variant={selectedColumns.includes(col.name) ? "default" : "outline"}
                                size="sm"
                                onClick={() => handleColumnToggle(col.name)}
                                className="justify-start"
                              >
                                {col.name}
                                {selectedColumns.includes(col.name) && (
                                  <Badge variant="secondary" className="ml-2">
                                    {selectedColumns.indexOf(col.name) + 1}
                                  </Badge>
                                )}
                              </Button>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Categorical Columns */}
                      {categoricalColumns.length > 0 && (
                        <div>
                          <h4 className="text-sm font-medium mb-2 text-blue-700">
                            Categorical ({categoricalColumns.length})
                          </h4>
                          <div className="grid grid-cols-2 gap-2">
                            {categoricalColumns.map(col => (
                              <Button
                                key={col.name}
                                variant={selectedColumns.includes(col.name) ? "default" : "outline"}
                                size="sm"
                                onClick={() => handleColumnToggle(col.name)}
                                className="justify-start"
                              >
                                {col.name}
                              </Button>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* DateTime Columns */}
                      {datetimeColumns.length > 0 && (
                        <div>
                          <h4 className="text-sm font-medium mb-2 text-purple-700">
                            DateTime ({datetimeColumns.length})
                          </h4>
                          <div className="grid grid-cols-2 gap-2">
                            {datetimeColumns.map(col => (
                              <Button
                                key={col.name}
                                variant={selectedColumns.includes(col.name) ? "default" : "outline"}
                                size="sm"
                                onClick={() => handleColumnToggle(col.name)}
                                className="justify-start"
                              >
                                {col.name}
                              </Button>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>

                {/* Chart Controls */}
                <ChartControls
                  columns={columns}
                  chartType={activeChart}
                  onChartTypeChange={setActiveChart}
                  filters={filters}
                  onFiltersChange={setFilters}
                  onExport={handleExportChart}
                  onRefresh={handleRefreshChart}
                  showAnimations={showAnimations}
                  onAnimationsChange={setShowAnimations}
                  binCount={binCount}
                  onBinCountChange={setBinCount}
                  showGrid={showGrid}
                  onGridChange={setShowGrid}
                />
              </div>

              {/* Recommendations */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Chart Recommendations</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-2">
                    {getChartTypeRecommendations().map((rec, index) => (
                      <Badge key={index} variant="secondary">
                        {rec}
                      </Badge>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="visualize" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    {activeChart.charAt(0).toUpperCase() + activeChart.slice(1)} Chart
                    <div className="flex gap-2">
                      {filters.length > 0 && (
                        <Badge variant="outline">
                          <Filter className="h-3 w-3 mr-1" />
                          {filters.length} filter{filters.length !== 1 ? 's' : ''}
                        </Badge>
                      )}
                      <Button variant="outline" size="sm" onClick={handleRefreshChart}>
                        <RefreshCw className="h-4 w-4" />
                      </Button>
                      <Button variant="outline" size="sm" onClick={handleExportChart}>
                        <Download className="h-4 w-4" />
                      </Button>
                    </div>
                  </CardTitle>
                  {selectedColumns.length > 0 && (
                    <CardDescription>
                      Visualizing: {selectedColumns.join(', ')}
                    </CardDescription>
                  )}
                </CardHeader>
                <CardContent>
                  {renderChart()}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="insights" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Visualization Insights</CardTitle>
                  <CardDescription>
                    AI-generated insights about your visualization
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <Alert>
                      <AlertDescription>
                        <strong>Pattern Detection:</strong> The {activeChart} chart shows {selectedColumns.length > 0 ? `interesting patterns in ${selectedColumns.join(', ')}` : 'no data selected'}.
                      </AlertDescription>
                    </Alert>
                    
                    {selectedColumns.length > 1 && (
                      <Alert>
                        <AlertDescription>
                          <strong>Correlation Analysis:</strong> Variables appear to have moderate correlation based on the selected visualization type.
                        </AlertDescription>
                      </Alert>
                    )}
                    
                    <Alert>
                      <AlertDescription>
                        <strong>Recommendation:</strong> Consider exploring {activeChart === 'histogram' ? 'box plots' : 'histograms'} for additional insights into the data distribution.
                      </AlertDescription>
                    </Alert>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  )
}