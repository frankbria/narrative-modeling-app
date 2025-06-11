'use client'

import React, { useState, useEffect, useMemo } from 'react'
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

interface Column {
  name: string
  type: 'numeric' | 'categorical' | 'datetime' | 'text'
  unique_count?: number
  null_count?: number
}

interface InteractiveVisualizationDashboardProps {
  datasetId: string
  columns: Column[]
  statistics?: any
}

export function InteractiveVisualizationDashboard({
  datasetId,
  columns,
  statistics
}: InteractiveVisualizationDashboardProps) {
  const [activeChart, setActiveChart] = useState('histogram')
  const [selectedColumns, setSelectedColumns] = useState<string[]>([])
  const [filters, setFilters] = useState<ChartFilter[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  // Chart configuration state
  const [showGrid, setShowGrid] = useState(true)
  const [showAnimations, setShowAnimations] = useState(true)
  const [binCount, setBinCount] = useState(50)
  
  // Sample data for demonstration
  const [chartData, setChartData] = useState<any>(null)

  const numericColumns = columns.filter(col => col.type === 'numeric')
  const categoricalColumns = columns.filter(col => col.type === 'categorical')
  const datetimeColumns = columns.filter(col => col.type === 'datetime')

  // Auto-select first numeric column if none selected
  useEffect(() => {
    if (selectedColumns.length === 0 && numericColumns.length > 0) {
      setSelectedColumns([numericColumns[0].name])
    }
  }, [columns, selectedColumns.length, numericColumns])

  // Generate sample data based on chart type and columns
  const generateSampleData = useMemo(() => {
    if (!selectedColumns.length) return null

    switch (activeChart) {
      case 'scatter':
        if (selectedColumns.length >= 2) {
          const data: ScatterPlotData = {
            data: Array.from({ length: 100 }, (_, i) => ({
              x: Math.random() * 100,
              y: Math.random() * 100 + (Math.random() * 50 - 25),
              label: `Point ${i + 1}`,
              category: i % 3 === 0 ? 'A' : i % 3 === 1 ? 'B' : 'C'
            })),
            xLabel: selectedColumns[0],
            yLabel: selectedColumns[1],
            title: `${selectedColumns[0]} vs ${selectedColumns[1]}`
          }
          return data
        }
        break

      case 'line':
        const lineData: LineChartData = {
          data: Array.from({ length: 50 }, (_, i) => {
            const item: any = { x: i }
            selectedColumns.forEach((col, index) => {
              item[col] = Math.sin(i * 0.1 + index) * 50 + 50 + Math.random() * 10
            })
            return item
          }),
          lines: selectedColumns.map((col, index) => ({
            dataKey: col,
            label: col,
            color: ['#8884d8', '#82ca9d', '#ffc658', '#ff7c7c'][index % 4]
          })),
          xLabel: 'Time',
          yLabel: 'Value',
          title: `Time Series: ${selectedColumns.join(', ')}`,
          showBrush: true
        }
        return lineData

      case 'histogram':
        return {
          bins: Array.from({ length: binCount }, () => Math.floor(Math.random() * 50)),
          binEdges: Array.from({ length: binCount + 1 }, (_, i) => i * 2),
          counts: Array.from({ length: binCount }, () => Math.floor(Math.random() * 50)),
          min: 0,
          max: binCount * 2
        }

      default:
        return null
    }
  }, [activeChart, selectedColumns, binCount])

  const handleColumnToggle = (columnName: string) => {
    setSelectedColumns(prev => {
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
      // In a real implementation, this would export the chart as PNG/PDF
      const dataStr = JSON.stringify(chartData, null, 2)
      const dataBlob = new Blob([dataStr], { type: 'application/json' })
      const url = URL.createObjectURL(dataBlob)
      const link = document.createElement('a')
      link.href = url
      link.download = `${activeChart}_${datasetId}.json`
      link.click()
    } catch (error) {
      console.error('Export failed:', error)
    }
  }

  const handleRefreshChart = () => {
    setLoading(true)
    // Simulate API call
    setTimeout(() => {
      setLoading(false)
      // Force re-generation of sample data
      setSelectedColumns([...selectedColumns])
    }, 1000)
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

    const data = generateSampleData

    switch (activeChart) {
      case 'histogram':
        return data ? <HistogramChart data={data} /> : null

      case 'scatter':
        return data ? <ScatterPlotChart data={data} /> : null

      case 'line':
        return data ? <LineChart data={data} /> : null

      case 'boxplot':
        return <BoxplotChart column={selectedColumns[0]} />

      case 'correlation':
        return <CorrelationHeatmap />

      default:
        return <div>Chart type not implemented</div>
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
          <Tabs value="configure" className="space-y-4">
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