'use client'

import React, { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Eye } from 'lucide-react'

import { ChartControls, ChartFilter } from './ChartControls'
import { DatasetStatistics } from '@/lib/types/api'
import { ColumnPicker } from './interactive-visualization/ColumnPicker'
import { ChartView } from './interactive-visualization/ChartView'
import {
  InsightsPanel,
  RecommendationsCard,
  VisualizePanel,
} from './interactive-visualization/DashboardPanels'
import { chartRecommendations } from './interactive-visualization/chartRecommendations'
import type { DashboardColumn } from './interactive-visualization/chartSelection'
import { useChartData } from './interactive-visualization/useChartData'
import { useChartExport } from './interactive-visualization/useChartExport'
import { useColumnSelection } from './interactive-visualization/useColumnSelection'

interface InteractiveVisualizationDashboardProps {
  datasetId: string
  columns: DashboardColumn[]
  statistics?: DatasetStatistics
}

export function InteractiveVisualizationDashboard(props: InteractiveVisualizationDashboardProps) {
  const { datasetId, columns, statistics } = props
  const [activeTab, setActiveTab] = useState('configure')
  const [activeChart, setActiveChart] = useState('histogram')
  const [filters, setFilters] = useState<ChartFilter[]>([])
  // Bumping this re-runs the chart fetch and remounts HistogramChart.
  const [refreshKey, setRefreshKey] = useState(0)

  // Chart configuration state
  const [showGrid, setShowGrid] = useState(true)
  const [showAnimations, setShowAnimations] = useState(true)
  const [binCount, setBinCount] = useState(50)

  const selection = useColumnSelection(columns, activeChart)
  const { selectedColumns, numericSelected, lineX, lineY } = selection
  const chart = useChartData({
    activeChart,
    datasetId,
    columns,
    selectedColumns,
    numericSelected,
    lineX,
    lineY,
    filters,
    refreshKey,
  })
  const { boxplotData, scatterData, lineData } = chart
  const exporter = useChartExport({
    activeChart,
    datasetId,
    statistics,
    numericSelected,
    binCount,
    fetched: { boxplot: boxplotData, scatter: scatterData, line: lineData },
  })

  const handleRefreshChart = () => {
    exporter.clearExportError()
    setRefreshKey(key => key + 1)
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
                <ColumnPicker
                  columns={columns}
                  selectedColumns={selectedColumns}
                  onToggle={selection.toggle}
                />
                <ChartControls
                  columns={columns}
                  chartType={activeChart}
                  onChartTypeChange={setActiveChart}
                  filters={filters}
                  onFiltersChange={setFilters}
                  onExport={exporter.exportChart}
                  onRefresh={handleRefreshChart}
                  showAnimations={showAnimations}
                  onAnimationsChange={setShowAnimations}
                  binCount={binCount}
                  onBinCountChange={setBinCount}
                  showGrid={showGrid}
                  onGridChange={setShowGrid}
                />
              </div>
              <RecommendationsCard recommendations={chartRecommendations(selectedColumns, columns)} />
            </TabsContent>

            <TabsContent value="visualize" className="space-y-4">
              <VisualizePanel
                activeChart={activeChart}
                filterCount={filters.length}
                selectedColumns={selectedColumns}
                onRefresh={handleRefreshChart}
                onExport={exporter.exportChart}
              >
                <ChartView
                  activeChart={activeChart}
                  loading={chart.loading}
                  error={exporter.exportError ?? chart.error}
                  datasetId={datasetId}
                  columns={columns}
                  statistics={statistics}
                  selectedColumns={selectedColumns}
                  numericSelected={numericSelected}
                  lineY={lineY}
                  binCount={binCount}
                  refreshKey={refreshKey}
                  boxplotData={boxplotData}
                  scatterData={scatterData}
                  lineData={lineData}
                />
              </VisualizePanel>
            </TabsContent>

            <TabsContent value="insights" className="space-y-4">
              <InsightsPanel activeChart={activeChart} selectedColumns={selectedColumns} />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  )
}
