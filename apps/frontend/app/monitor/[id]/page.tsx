'use client'

import { useState } from 'react'
import { useAsyncData } from '@/lib/hooks/useAsyncData'
import { useParams } from 'next/navigation'
import { useSession } from 'next-auth/react'
import { getAuthToken } from '@/lib/auth-helpers'
import { ProductionService } from '@/lib/services/production'
import { ModelService } from '@/lib/services/model'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Activity,
  Loader2,
  ArrowLeft,
  TrendingUp,
  Clock,
  Zap,
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  PieChart,
  Target,
  Brain,
  LineChart as LineChartIcon
} from 'lucide-react'
import Link from 'next/link'
import { LineChart } from '@/components/LineChart'
import { BarChart } from '@/components/BarChart'

export default function ModelMonitoringPage() {
  const params = useParams()
  const { data: session } = useSession()
  
  const modelId = params?.id as string
  const [timeWindow, setTimeWindow] = useState('24')

  const {
    data: monitorData,
    loading: isLoading,
    error,
    reload: fetchModelData,
  } = useAsyncData(
    async () => {
      const token = await getAuthToken()
      const hours = parseInt(timeWindow)
      const [modelData, metricsData, logsData, distData, timelineData, healthData] =
        await Promise.all([
          ModelService.getModel(modelId, token),
          ProductionService.getModelMetrics(modelId, hours, token),
          ProductionService.getPredictionLogs(modelId, 100, token),
          ProductionService.getPredictionDistribution(modelId, hours, token),
          ProductionService.getUsageTimeline(modelId, hours, token),
          ProductionService.getDeploymentHealth(modelId, hours, token),
        ])
      return {
        model: modelData,
        metrics: metricsData,
        predictionLogs: logsData.logs,
        distribution: distData,
        timeline: timelineData,
        health: healthData,
      }
    },
    [modelId, timeWindow],
    { enabled: !!modelId, errorMessage: 'Failed to load model monitoring data' },
  )

  const model = monitorData?.model ?? null
  const metrics = monitorData?.metrics ?? null
  const predictionLogs = monitorData?.predictionLogs ?? []
  const distribution = monitorData?.distribution ?? null
  const timeline = monitorData?.timeline ?? null
  const health = monitorData?.health ?? null

  const formatLatency = (ms: number) => {
    if (ms < 1) return '<1ms'
    if (ms < 1000) return `${Math.round(ms)}ms`
    return `${(ms / 1000).toFixed(2)}s`
  }

  const formatPrediction = (prediction: unknown) => {
    if (typeof prediction === 'number') {
      return prediction.toFixed(4)
    }
    return String(prediction)
  }

  const healthStyle = (status: string) => {
    switch (status) {
      case 'healthy':
        return { className: 'bg-green-500', Icon: CheckCircle2, label: 'Healthy' }
      case 'degraded':
        return { className: 'bg-yellow-500', Icon: AlertTriangle, label: 'Degraded' }
      case 'unhealthy':
        return { className: 'bg-red-500', Icon: AlertCircle, label: 'Unhealthy' }
      default:
        return { className: 'bg-gray-400', Icon: Activity, label: 'No Data' }
    }
  }

  if (!session) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Card className="w-96">
          <CardContent className="pt-6">
            <p className="text-center text-muted-foreground">
              Please log in to view model monitoring
            </p>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin mr-3 text-primary" />
        <span className="text-lg">Loading monitoring data...</span>
      </div>
    )
  }

  if (error || !model || !metrics) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Card className="w-96">
          <CardContent className="pt-6 space-y-4">
            <AlertCircle className="h-12 w-12 text-muted-foreground mx-auto" />
            <p className="text-center text-muted-foreground">
              {error || 'Model not found'}
            </p>
            <div className="flex justify-center">
              <Link href="/monitor">
                <Button variant="outline">
                  <ArrowLeft className="mr-2 h-4 w-4" />
                  Back to Monitoring
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  const hs = health ? healthStyle(health.status) : null
  const HealthIcon = hs?.Icon

  return (
    <div className="container mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Link href="/monitor">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back
              </Button>
            </Link>
            <h1 className="text-3xl font-bold flex items-center gap-2">
              <Activity className="h-8 w-8" />
              {model.name} Monitoring
            </h1>
          </div>
          {model.description && (
            <p className="text-muted-foreground ml-12">
              {model.description}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Select value={timeWindow} onValueChange={setTimeWindow}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1">1 hour</SelectItem>
              <SelectItem value="6">6 hours</SelectItem>
              <SelectItem value="24">24 hours</SelectItem>
              <SelectItem value="168">7 days</SelectItem>
            </SelectContent>
          </Select>
          <Button onClick={fetchModelData}>Refresh</Button>
        </div>
      </div>

      {/* Deployment Health + Alerts */}
      {health && hs && (
        <Card>
          <CardContent className="pt-6 space-y-3">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div className="flex items-center gap-3">
                <Badge variant="default" className={hs.className}>
                  {HealthIcon && <HealthIcon className="h-4 w-4 mr-1" />}
                  {hs.label}
                </Badge>
                <span className="text-sm text-muted-foreground">
                  Error rate {(health.error_rate * 100).toFixed(1)}% ·{' '}
                  {health.requests.toLocaleString()} requests · last{' '}
                  {health.last_request_at
                    ? new Date(health.last_request_at).toLocaleString()
                    : 'never'}
                </span>
              </div>
            </div>
            {health.alerts.length > 0 && (
              <div className="space-y-2">
                {health.alerts.map((alert, i) => (
                  <div
                    key={`${alert.type}-${i}`}
                    className="flex items-start gap-2 text-sm"
                    data-testid="health-alert"
                  >
                    {alert.level === 'critical' ? (
                      <AlertCircle className="h-4 w-4 text-red-500 mt-0.5" />
                    ) : (
                      <AlertTriangle className="h-4 w-4 text-yellow-500 mt-0.5" />
                    )}
                    <span>{alert.message}</span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Metrics Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Predictions
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-primary" />
              {metrics.total_predictions.toLocaleString()}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Last {timeWindow} hours
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Avg Response Time
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold flex items-center gap-2">
              <Zap className="h-5 w-5 text-yellow-500" />
              {formatLatency(metrics.avg_latency_ms)}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Per prediction
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Predictions/Hour
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold flex items-center gap-2">
              <Clock className="h-5 w-5 text-blue-500" />
              {metrics.predictions_per_hour.toFixed(1)}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Average rate
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Avg Confidence
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold flex items-center gap-2">
              <Target className="h-5 w-5 text-green-500" />
              {metrics.avg_confidence > 0 
                ? `${(metrics.avg_confidence * 100).toFixed(1)}%`
                : 'N/A'
              }
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {model.problem_type.includes('classification') ? 'Classification' : 'Not applicable'}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Detailed Tabs */}
      <Tabs defaultValue="predictions" className="space-y-4">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="predictions">Recent Predictions</TabsTrigger>
          <TabsTrigger value="timeline">Timeline</TabsTrigger>
          <TabsTrigger value="distribution">Distribution</TabsTrigger>
          <TabsTrigger value="performance">Performance</TabsTrigger>
        </TabsList>

        <TabsContent value="timeline">
          <Card>
            <CardHeader>
              <CardTitle>Usage Over Time</CardTitle>
              <CardDescription>
                Request volume and average latency over the last {timeWindow} hours
              </CardDescription>
            </CardHeader>
            <CardContent>
              {!timeline || timeline.buckets.every((b) => b.requests === 0) ? (
                <div className="text-center py-8">
                  <LineChartIcon className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                  <p className="text-muted-foreground">No usage data in the selected time window</p>
                </div>
              ) : (
                <div className="w-full overflow-x-auto">
                  <LineChart
                    height={360}
                    data={{
                      data: timeline.buckets.map((b) => ({
                        x: new Date(b.timestamp).toLocaleTimeString([], {
                          hour: '2-digit',
                          minute: '2-digit',
                        }),
                        Requests: b.requests,
                        Errors: b.errors,
                        'Avg Latency (ms)': b.avg_latency_ms,
                      })),
                      lines: [
                        { dataKey: 'Requests', label: 'Requests', color: '#3b82f6' },
                        { dataKey: 'Errors', label: 'Errors', color: '#ef4444' },
                        { dataKey: 'Avg Latency (ms)', label: 'Avg Latency (ms)', color: '#f59e0b' },
                      ],
                      xLabel: 'Time',
                      yLabel: 'Count / ms',
                      showBrush: timeline.buckets.length > 24,
                    }}
                  />
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="predictions">
          <Card>
            <CardHeader>
              <CardTitle>Recent Predictions</CardTitle>
              <CardDescription>
                Last 100 predictions made by this model
              </CardDescription>
            </CardHeader>
            <CardContent>
              {predictionLogs.length === 0 ? (
                <div className="text-center py-8">
                  <Brain className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                  <p className="text-muted-foreground">No predictions in the selected time window</p>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Time</TableHead>
                      <TableHead>Prediction</TableHead>
                      {model.problem_type.includes('classification') && (
                        <TableHead>Confidence</TableHead>
                      )}
                      <TableHead>Latency</TableHead>
                      <TableHead>API Key</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {predictionLogs.map((log) => (
                      <TableRow key={log.prediction_id}>
                        <TableCell className="text-sm">
                          {new Date(log.timestamp).toLocaleString()}
                        </TableCell>
                        <TableCell className="font-medium">
                          {formatPrediction(log.prediction)}
                        </TableCell>
                        {model.problem_type.includes('classification') && (
                          <TableCell>
                            {log.probability 
                              ? `${(log.probability * 100).toFixed(1)}%`
                              : '-'
                            }
                          </TableCell>
                        )}
                        <TableCell>
                          {formatLatency(log.latency_ms)}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {log.api_key_id ? log.api_key_id.slice(0, 8) + '...' : 'UI'}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="distribution">
          <Card>
            <CardHeader>
              <CardTitle>Prediction Distribution</CardTitle>
              <CardDescription>
                Distribution of prediction values over the last {timeWindow} hours
              </CardDescription>
            </CardHeader>
            <CardContent>
              {!distribution || distribution.total === 0 ? (
                <div className="text-center py-8">
                  <PieChart className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                  <p className="text-muted-foreground">No distribution data available</p>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="grid grid-cols-3 gap-4 mb-6">
                    <div>
                      <p className="text-sm text-muted-foreground">Total Predictions</p>
                      <p className="text-2xl font-bold">{distribution.total}</p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Unique Values</p>
                      <p className="text-2xl font-bold">{distribution.unique_values}</p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Most Common</p>
                      <p className="text-2xl font-bold">
                        {distribution.most_common || 'N/A'}
                      </p>
                    </div>
                  </div>
                  
                  <div className="space-y-2">
                    <h4 className="text-sm font-medium">Value Distribution</h4>
                    <div className="w-full overflow-x-auto">
                      <BarChart
                        height={360}
                        orientation="horizontal"
                        data={{
                          data: Object.entries(distribution.distribution)
                            .sort(([, a], [, b]) => (b as number) - (a as number))
                            .slice(0, 10)
                            .map(([value, count]) => ({
                              category: value,
                              value: count as number,
                            })),
                          xLabel: 'Prediction Value',
                          yLabel: 'Count',
                          sortBy: 'value',
                          showPercentages: true,
                        }}
                      />
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="performance">
          <Card>
            <CardHeader>
              <CardTitle>Performance Analysis</CardTitle>
              <CardDescription>
                Model performance metrics and trends
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div>
                <h4 className="text-sm font-medium mb-2">Latency Percentiles</h4>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                  {(['p50', 'p90', 'p95', 'p99'] as const).map((p) => (
                    <div key={p} data-testid={`latency-${p}`}>
                      <p className="text-xs text-muted-foreground uppercase">{p}</p>
                      <p className="text-lg font-bold">
                        {formatLatency(metrics.latency_percentiles?.[p] ?? 0)}
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <h4 className="text-sm font-medium mb-2">Response Time Trend</h4>
                <p className="text-sm text-muted-foreground mb-4">
                  Average latency: {formatLatency(metrics.avg_latency_ms)} · Error rate:{' '}
                  {(metrics.error_rate * 100).toFixed(1)}% ({metrics.error_count} errors)
                </p>
                {metrics.avg_latency_ms < 100 ? (
                  <Badge variant="default" className="bg-green-500">
                    Excellent Performance
                  </Badge>
                ) : metrics.avg_latency_ms < 500 ? (
                  <Badge variant="default" className="bg-blue-500">
                    Good Performance
                  </Badge>
                ) : (
                  <Badge variant="default" className="bg-yellow-500">
                    Consider Optimization
                  </Badge>
                )}
              </div>

              <div>
                <h4 className="text-sm font-medium mb-2">Model Information</h4>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="text-muted-foreground">Algorithm</p>
                    <p className="font-medium">{model.algorithm}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Problem Type</p>
                    <p className="font-medium">
                      {model.problem_type.split('_').map(w => 
                        w.charAt(0).toUpperCase() + w.slice(1)
                      ).join(' ')}
                    </p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Test Score</p>
                    <p className="font-medium">{(model.test_score * 100).toFixed(1)}%</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Features</p>
                    <p className="font-medium">{model.n_features}</p>
                  </div>
                </div>
              </div>

              <div>
                <h4 className="text-sm font-medium mb-2">Recommendations</h4>
                <div className="space-y-2">
                  {metrics.predictions_per_hour < 1 && (
                    <div className="flex items-start gap-2 text-sm">
                      <AlertCircle className="h-4 w-4 text-yellow-500 mt-0.5" />
                      <p>Low usage detected. Consider promoting this model or reviewing its use case.</p>
                    </div>
                  )}
                  {metrics.avg_latency_ms > 1000 && (
                    <div className="flex items-start gap-2 text-sm">
                      <AlertCircle className="h-4 w-4 text-orange-500 mt-0.5" />
                      <p>High latency detected. Consider optimizing the model or upgrading infrastructure.</p>
                    </div>
                  )}
                  {metrics.avg_confidence > 0 && metrics.avg_confidence < 0.7 && (
                    <div className="flex items-start gap-2 text-sm">
                      <AlertCircle className="h-4 w-4 text-yellow-500 mt-0.5" />
                      <p>Low average confidence. Review model performance and consider retraining.</p>
                    </div>
                  )}
                  {metrics.predictions_per_hour > 0 && metrics.avg_latency_ms < 100 && metrics.avg_confidence > 0.8 && (
                    <div className="flex items-start gap-2 text-sm">
                      <TrendingUp className="h-4 w-4 text-green-500 mt-0.5" />
                      <p>Model is performing well with good latency and confidence scores.</p>
                    </div>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}