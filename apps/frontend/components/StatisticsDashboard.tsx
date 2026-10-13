'use client'

import React from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { CorrelationHeatmap } from './CorrelationHeatmap'
import { HistogramChart } from './HistogramChart'
import { StatItem } from '@/lib/utils'
import {
  BarChart3,
  AlertTriangle,
  Database,
  Percent,
  Target,
  type LucideIcon
} from 'lucide-react'

interface FrequentValue {
  value: unknown
  count: number
  percentage: number
}

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
  most_frequent_values?: FrequentValue[]
}

interface MissingValueSummary {
  total_missing_values: number
  columns_with_missing: number
  complete_columns: number
}

type CorrelationMatrix = Record<string, Record<string, number>>

interface StatisticsData {
  row_count: number
  column_count: number
  memory_usage_mb: number
  correlation_matrix?: CorrelationMatrix
  column_statistics: ColumnStatistic[]
  missing_value_summary: MissingValueSummary
}

interface StatisticsDashboardProps {
  datasetId: string
  /** What processing stored for the dataset. The component reads nothing else (#825). */
  statistics: StatisticsData
}

interface ColumnProps {
  col: ColumnStatistic
}

interface NumericCardProps extends ColumnProps {
  datasetId: string
}

interface TileProps {
  icon: LucideIcon
  value: string | number
  label: string
}

interface FigureProps {
  label: string
  value: string
}

interface CorrelationsProps {
  columns: ColumnStatistic[]
  matrix: CorrelationMatrix | undefined
}

type NumericStats = NonNullable<StatItem['numeric_stats']>
type BadgeVariant = 'destructive' | 'secondary' | 'default'

const NUMERIC_TYPES = ['integer', 'float', 'currency', 'percentage']
const CATEGORICAL_TYPES = ['categorical', 'string', 'boolean']

function isNumeric(col: ColumnStatistic): boolean {
  return NUMERIC_TYPES.includes(col.data_type)
}

function isCategorical(col: ColumnStatistic): boolean {
  return CATEGORICAL_TYPES.includes(col.data_type)
}

function manyMissing(col: ColumnStatistic): boolean {
  return col.null_percentage > 10
}

function manyOutliers(col: ColumnStatistic): boolean {
  return orZero(col.outlier_percentage) > 5
}

function hasIssue(col: ColumnStatistic): boolean {
  return manyMissing(col) || manyOutliers(col)
}

/** Share of cells that hold a value, as the tile shows it. */
function completeness(statistics: StatisticsData): string {
  const cells = statistics.row_count * statistics.column_count
  return ((1 - statistics.missing_value_summary.total_missing_values / cells) * 100).toFixed(1)
}

/** "12.0% missing • 6.0% outliers", either half alone when only one applies. */
function issueText(col: ColumnStatistic): string {
  const parts: string[] = []
  if (manyMissing(col)) parts.push(`${col.null_percentage.toFixed(1)}% missing`)
  if (manyOutliers(col)) parts.push(`${orZero(col.outlier_percentage).toFixed(1)}% outliers`)
  return parts.join(' • ')
}

function orZero(value: number | undefined): number {
  return value || 0
}

function numericStats(col: ColumnStatistic): NumericStats | undefined {
  if (col.mean === undefined) return undefined
  return {
    min: orZero(col.min_value),
    max: orZero(col.max_value),
    // A stored null (nothing to average) is not undefined: it still gets a block, at zero.
    mean: orZero(col.mean),
    median: orZero(col.median),
    // Backend computes no mode; StatItem requires one and the heatmap ignores it.
    mode: 0,
    std_dev: orZero(col.std_dev),
  }
}

/** A column in the StatItem shape CorrelationHeatmap consumes. */
function toStatItem(col: ColumnStatistic): StatItem {
  return {
    field_name: col.column_name,
    field_type: isNumeric(col) ? 'numeric' : col.data_type,
    count: col.total_count,
    missing_values: col.null_count,
    unique_values: col.unique_count,
    numeric_stats: numericStats(col),
  }
}

function cardinalityVariant(uniquePercentage: number): BadgeVariant {
  if (uniquePercentage > 90) return 'destructive'
  if (uniquePercentage > 50) return 'secondary'
  return 'default'
}

/** Two decimals, or N/A for a figure processing could not compute (stored as null). */
function fixed(value: number | undefined): string {
  if (value == null) return 'N/A'
  return value.toFixed(2)
}

export function StatisticsDashboard(props: StatisticsDashboardProps) {
  const { datasetId, statistics } = props
  const columns = statistics.column_statistics
  const numericCards = columns
    .filter(isNumeric)
    .map((col) => <NumericCard key={col.column_name} col={col} datasetId={datasetId} />)
  const categoricalCards = columns
    .filter(isCategorical)
    .map((col) => <CategoricalCard key={col.column_name} col={col} />)

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Tile icon={Database} value={statistics.row_count.toLocaleString()} label="Rows" />
        <Tile icon={BarChart3} value={statistics.column_count} label="Columns" />
        <Tile icon={Percent} value={`${completeness(statistics)}%`} label="Complete" />
        <Tile icon={Target} value={statistics.memory_usage_mb.toFixed(1)} label="MB" />
      </div>

      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="numeric">Numeric</TabsTrigger>
          <TabsTrigger value="categorical">Categorical</TabsTrigger>
          <TabsTrigger value="correlations">Correlations</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <MissingValues summary={statistics.missing_value_summary} />
          <QualityIssues columns={columns} />
        </TabsContent>

        <TabsContent value="numeric" className="space-y-4">
          <div className="grid gap-4">{numericCards}</div>
        </TabsContent>

        <TabsContent value="categorical" className="space-y-4">
          <div className="grid gap-4">{categoricalCards}</div>
        </TabsContent>

        <TabsContent value="correlations">
          <Correlations columns={columns} matrix={statistics.correlation_matrix} />
        </TabsContent>
      </Tabs>
    </div>
  )
}

function Tile(props: TileProps) {
  const { icon: Icon, value, label } = props
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center space-x-2">
          <Icon className="h-4 w-4 text-muted-foreground" />
          <div>
            <p className="text-2xl font-bold">{value}</p>
            <p className="text-xs text-muted-foreground">{label}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function MissingValues(props: { summary: MissingValueSummary }) {
  const { summary } = props
  return (
    <Card>
      <CardHeader>
        <CardTitle>Missing Values</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <p className="text-2xl font-bold text-red-600">{summary.total_missing_values.toLocaleString()}</p>
            <p className="text-sm text-muted-foreground">Total Missing</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-yellow-600">{summary.columns_with_missing}</p>
            <p className="text-sm text-muted-foreground">Columns Affected</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-green-600">{summary.complete_columns}</p>
            <p className="text-sm text-muted-foreground">Complete Columns</p>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

/** The first five columns with over 10% missing or over 5% outliers. */
function QualityIssues(props: { columns: ColumnStatistic[] }) {
  const flagged = props.columns.filter(hasIssue)
  const rows = flagged.slice(0, 5).map((col) => <IssueRow key={col.column_name} col={col} />)
  const none = <p className="text-center text-muted-foreground py-8">No significant issues detected</p>
  return (
    <Card>
      <CardHeader>
        <CardTitle>Data Quality Issues</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">{flagged.length === 0 ? none : rows}</div>
      </CardContent>
    </Card>
  )
}

function IssueRow(props: ColumnProps) {
  const { col } = props
  return (
    <div className="flex items-center justify-between p-3 bg-muted rounded-lg">
      <div>
        <p className="font-medium">{col.column_name}</p>
        <p className="text-sm text-muted-foreground">{issueText(col)}</p>
      </div>
      <AlertTriangle className="h-5 w-5 text-yellow-600" />
    </div>
  )
}

function ColumnHeader(props: ColumnProps) {
  const { col } = props
  return (
    <CardHeader>
      <CardTitle className="text-base">{col.column_name}</CardTitle>
      <CardDescription>
        {col.data_type} • {col.unique_count.toLocaleString()} unique values
      </CardDescription>
    </CardHeader>
  )
}

function NumericCard(props: NumericCardProps) {
  const { col, datasetId } = props
  const outliers = `${orZero(col.outlier_count)} (${orZero(col.outlier_percentage).toFixed(1)}%)`
  return (
    <Card>
      <ColumnHeader col={col} />
      <CardContent>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <Figure label="Mean" value={fixed(col.mean)} />
          <Figure label="Median" value={fixed(col.median)} />
          <Figure label="Std Dev" value={fixed(col.std_dev)} />
          <Figure label="Outliers" value={outliers} />
        </div>

        <div className="mt-4">
          <HistogramChart datasetId={datasetId} column={col.column_name} height={100} />
        </div>
      </CardContent>
    </Card>
  )
}

function Figure(props: FigureProps) {
  const { label, value } = props
  return (
    <div>
      <p className="text-muted-foreground">{label}</p>
      <p className="font-semibold">{value}</p>
    </div>
  )
}

function CategoricalCard(props: ColumnProps) {
  const { col } = props
  const frequent = col.most_frequent_values ? <FrequentValues values={col.most_frequent_values} /> : null
  return (
    <Card>
      <ColumnHeader col={col} />
      <CardContent>
        <div className="space-y-3">
          <div className="flex justify-between text-sm">
            <span>Cardinality</span>
            <Badge variant={cardinalityVariant(col.unique_percentage)}>{col.unique_percentage.toFixed(1)}%</Badge>
          </div>

          {frequent}
        </div>
      </CardContent>
    </Card>
  )
}

function FrequentValues(props: { values: FrequentValue[] }) {
  const rows = props.values.slice(0, 5).map((item, index) => (
    <div key={index} className="flex items-center justify-between text-sm">
      <span className="truncate max-w-[200px]">{String(item.value)}</span>
      <div className="flex items-center gap-2">
        <Progress value={item.percentage} className="w-16 h-2" />
        <span className="text-muted-foreground">{item.percentage.toFixed(1)}%</span>
      </div>
    </div>
  ))
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">Most Frequent Values</p>
      {rows}
    </div>
  )
}

function Correlations(props: CorrelationsProps) {
  const { columns, matrix } = props
  if (!matrix) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center h-32">
          <p className="text-muted-foreground">No correlation data available</p>
        </CardContent>
      </Card>
    )
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle>Correlation Matrix</CardTitle>
        <CardDescription>Correlation between numeric variables</CardDescription>
      </CardHeader>
      <CardContent>
        <CorrelationHeatmap stats={columns.map(toStatItem)} correlationMatrix={matrix} />
      </CardContent>
    </Card>
  )
}
