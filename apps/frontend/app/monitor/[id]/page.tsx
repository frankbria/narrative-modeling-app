'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { useSession } from 'next-auth/react'
import { getAuthToken } from '@/lib/auth-helpers'
import { ProductionService, ModelMetrics } from '@/lib/services/production'
import { ModelService, ModelInfo } from '@/lib/services/model'
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
  BarChart3,
  PieChart,
  Target,
  Brain
} from 'lucide-react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
// Chart imports would go here when implementing charts

interface PredictionLog {
  prediction_id: string
  timestamp: string
  prediction: any
  probability?: number
  latency_ms: number
  api_key_id?: string
}

export default function ModelMonitoringPage() {
  const params = useParams()
  const { data: session } = useSession()
  const router = useRouter()
  
  const modelId = params?.id as string
  const [model, setModel] = useState<ModelInfo | null>(null)
  const [metrics, setMetrics] = useState<ModelMetrics | null>(null)
  const [predictionLogs, setPredictionLogs] = useState<PredictionLog[]>([])
  const [distribution, setDistribution] = useState<any>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [timeWindow, setTimeWindow] = useState('24')

  useEffect(() => {
    if (session && modelId) {
      fetchModelData()
    }
  }, [session, modelId, timeWindow])

  const fetchModelData = async () => {
    try {
      setIsLoading(true)
      const token = await getAuthToken()
      
      const [modelData, metricsData, logsData, distData] = await Promise.all([
        ModelService.getModel(modelId, token),
        ProductionService.getModelMetrics(modelId, parseInt(timeWindow), token),
        ProductionService.getPredictionLogs(modelId, 100, token),
        ProductionService.getPredictionDistribution(modelId, parseInt(timeWindow), token)
      ])
      
      setModel(modelData)
      setMetrics(metricsData)
      setPredictionLogs(logsData.logs)
      setDistribution(distData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load model monitoring data')
    } finally {
      setIsLoading(false)
    }
  }

  const formatLatency = (ms: number) => {
    if (ms < 1) return '<1ms'
    if (ms < 1000) return `${Math.round(ms)}ms`
    return `${(ms / 1000).toFixed(2)}s`
  }

  const formatPrediction = (prediction: any) => {
    if (typeof prediction === 'number') {
      return prediction.toFixed(4)
    }
    return String(prediction)
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
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="predictions">Recent Predictions</TabsTrigger>
          <TabsTrigger value="distribution">Distribution</TabsTrigger>
          <TabsTrigger value="performance">Performance</TabsTrigger>
        </TabsList>

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
                    {Object.entries(distribution.distribution)
                      .sort(([, a], [, b]) => (b as number) - (a as number))
                      .slice(0, 10)
                      .map(([value, count]) => (
                        <div key={value} className="flex items-center justify-between">
                          <span className="text-sm">{value}</span>
                          <div className="flex items-center gap-2">
                            <div className="w-32 bg-secondary rounded-full h-2">
                              <div
                                className="bg-primary h-2 rounded-full transition-all"
                                style={{ 
                                  width: `${((count as number) / distribution.total) * 100}%` 
                                }}
                              />
                            </div>
                            <span className="text-sm text-muted-foreground w-16 text-right">
                              {count as number}
                            </span>
                          </div>
                        </div>
                      ))
                    }
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
                <h4 className="text-sm font-medium mb-2">Response Time Trend</h4>
                <p className="text-sm text-muted-foreground mb-4">
                  Average latency: {formatLatency(metrics.avg_latency_ms)}
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