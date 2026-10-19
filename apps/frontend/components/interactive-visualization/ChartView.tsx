import type { ComponentType, ReactNode } from 'react'
import { Loader2, BarChart3 } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import type { DatasetStatistics } from '@/lib/types/api'
import type { BoxPlotData, LineChartData, ScatterPlotData } from '@/lib/services/visualization'
import { HistogramChart } from '../HistogramChart'
import { BoxplotChart } from '../BoxplotChart'
import { CorrelationHeatmap } from '../CorrelationHeatmap'
import { ScatterPlotChart } from '../ScatterPlotChart'
import { LineChart } from '../LineChart'
import type { DashboardColumn } from './chartSelection'
import { correlationStats } from './correlationStats'

interface EmptyStateProps {
  message: string
}

function EmptyState(props: EmptyStateProps) {
  const { message } = props
  return (
    <div className="flex items-center justify-center h-96 text-muted-foreground">
      <div className="text-center">
        <BarChart3 className="h-12 w-12 mx-auto mb-4 opacity-50" />
        <p>{message}</p>
      </div>
    </div>
  )
}

export interface ChartViewProps {
  activeChart: string
  loading: boolean
  error: string | null
  datasetId: string
  columns: DashboardColumn[]
  statistics?: DatasetStatistics
  selectedColumns: string[]
  numericSelected: string[]
  lineY: string[]
  binCount: number
  refreshKey: number
  boxplotData: BoxPlotData | null
  scatterData: ScatterPlotData | null
  lineData: LineChartData | null
}

function HistogramView(props: ChartViewProps) {
  const { numericSelected, datasetId, binCount, refreshKey } = props
  if (numericSelected.length < 1) {
    return <EmptyState message="Select a numeric column to view its histogram" />
  }
  // HistogramChart fetches its own data and renders loading/empty/error
  // states internally. `key` forces a refetch when the user hits refresh.
  return (
    <HistogramChart
      key={`${numericSelected[0]}-${binCount}-${refreshKey}`}
      datasetId={datasetId}
      column={numericSelected[0]}
      bins={binCount}
    />
  )
}

function ScatterView(props: ChartViewProps) {
  const { numericSelected, scatterData } = props
  if (numericSelected.length < 2) {
    return <EmptyState message="Select two numeric columns (X and Y) to plot a scatter chart" />
  }
  if (!scatterData) return <EmptyState message="No data available for the selected columns" />
  return <ScatterPlotChart data={scatterData} />
}

function LineView(props: ChartViewProps) {
  const { selectedColumns, lineY, lineData } = props
  if (selectedColumns.length < 2 || lineY.length < 1) {
    return <EmptyState message="Select an X column and at least one numeric Y column for a line chart" />
  }
  if (!lineData) return <EmptyState message="No data available for the selected columns" />
  return <LineChart data={lineData} />
}

function BoxplotView(props: ChartViewProps) {
  const { numericSelected, boxplotData } = props
  if (numericSelected.length < 1) {
    return <EmptyState message="Select a numeric column to view its box plot" />
  }
  if (!boxplotData) return <EmptyState message="No data available for the selected column" />
  return <BoxplotChart data={boxplotData} />
}

function CorrelationView(props: ChartViewProps) {
  const { statistics, columns } = props
  return (
    <CorrelationHeatmap
      stats={correlationStats(statistics, columns)}
      correlationMatrix={statistics?.correlation_matrix ?? null}
    />
  )
}

function UnsupportedView() {
  const message = 'This chart type is not supported yet'
  return <EmptyState message={message} />
}

const CHART_VIEWS: Record<string, ComponentType<ChartViewProps>> = {
  histogram: HistogramView,
  scatter: ScatterView,
  line: LineView,
  boxplot: BoxplotView,
  correlation: CorrelationView,
}

interface ChartStatusProps {
  loading: boolean
  error: string | null
  selectedColumns: string[]
  children: ReactNode
}

// What stands in for the chart while it loads, after a failure, or with nothing selected.
function ChartStatus(props: ChartStatusProps) {
  const { loading, error, selectedColumns, children } = props
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
  if (!selectedColumns.length) return <EmptyState message="Select columns to visualize" />
  return <>{children}</>
}

/** The active chart, or what the user still has to do to get one. */
export function ChartView(props: ChartViewProps) {
  const { activeChart, loading, error, selectedColumns } = props
  const View = CHART_VIEWS[activeChart] ?? UnsupportedView
  return (
    <ChartStatus loading={loading} error={error} selectedColumns={selectedColumns}>
      <View {...props} />
    </ChartStatus>
  )
}
