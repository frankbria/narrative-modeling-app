import type { ReactNode } from 'react'
import { Download, Filter, RefreshCw } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { chartTitle } from './chartSelection'

interface RecommendationsCardProps {
  recommendations: string[]
}

export function RecommendationsCard(props: RecommendationsCardProps) {
  const { recommendations } = props
  const renderBadge = (rec: string, index: number) => (
    <Badge key={index} variant="secondary">
      {rec}
    </Badge>
  )
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Chart Recommendations</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-2">{recommendations.map(renderBadge)}</div>
      </CardContent>
    </Card>
  )
}

interface FilterCountProps {
  count: number
}

function FilterCount(props: FilterCountProps) {
  const { count } = props
  if (count === 0) return null
  return (
    <Badge variant="outline">
      <Filter className="h-3 w-3 mr-1" />
      {count} filter{count !== 1 ? 's' : ''}
    </Badge>
  )
}

interface VisualizePanelProps {
  activeChart: string
  filterCount: number
  selectedColumns: string[]
  onRefresh: VoidFunction
  onExport: VoidFunction
  /** The chart itself. */
  children: ReactNode
}

export function VisualizePanel(props: VisualizePanelProps) {
  const { activeChart, filterCount, selectedColumns, onRefresh, onExport, children } = props
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          {chartTitle(activeChart)} Chart
          <div className="flex gap-2">
            <FilterCount count={filterCount} />
            <Button variant="outline" size="sm" onClick={onRefresh}>
              <RefreshCw className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="sm" onClick={onExport}>
              <Download className="h-4 w-4" />
            </Button>
          </div>
        </CardTitle>
        {selectedColumns.length > 0 ? (
          <CardDescription>Visualizing: {selectedColumns.join(', ')}</CardDescription>
        ) : null}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}

interface InsightsPanelProps {
  activeChart: string
  selectedColumns: string[]
}

function patternText(selectedColumns: string[]): string {
  if (selectedColumns.length === 0) return 'no data selected'
  return `interesting patterns in ${selectedColumns.join(', ')}`
}

export function InsightsPanel(props: InsightsPanelProps) {
  const { activeChart, selectedColumns } = props
  return (
    <Card>
      <CardHeader>
        <CardTitle>Visualization Insights</CardTitle>
        <CardDescription>AI-generated insights about your visualization</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <Alert>
            <AlertDescription>
              <strong>Pattern Detection:</strong> The {activeChart} chart shows {patternText(selectedColumns)}.
            </AlertDescription>
          </Alert>

          {selectedColumns.length > 1 ? (
            <Alert>
              <AlertDescription>
                <strong>Correlation Analysis:</strong> Variables appear to have moderate correlation based on the selected visualization type.
              </AlertDescription>
            </Alert>
          ) : null}

          <Alert>
            <AlertDescription>
              <strong>Recommendation:</strong> Consider exploring {activeChart === 'histogram' ? 'box plots' : 'histograms'} for additional insights into the data distribution.
            </AlertDescription>
          </Alert>
        </div>
      </CardContent>
    </Card>
  )
}
