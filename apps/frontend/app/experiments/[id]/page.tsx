"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { 
  ArrowLeft, 
  Play, 
  Pause, 
  CheckCircle, 
  TrendingUp, 
  TrendingDown,
  Users,
  Clock,
  Target,
  RefreshCw
} from "lucide-react";
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell
} from "recharts";
import { abTestingService, ABTest, ExperimentMetrics } from "@/lib/services/abTesting";
import { formatDistanceToNow, format } from "date-fns";

export default function ExperimentDetailsPage() {
  const params = useParams();
  const router = useRouter();
  const experimentId = params.id as string;

  const [experiment, setExperiment] = useState<ABTest | null>(null);
  const [metrics, setMetrics] = useState<ExperimentMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (experimentId) {
      loadExperiment();
      loadMetrics();
    }
  }, [experimentId]);

  const loadExperiment = async () => {
    try {
      const data = await abTestingService.getExperiment(experimentId);
      setExperiment(data);
    } catch (error) {
      console.error("Failed to load experiment:", error);
      setError("Failed to load experiment");
    }
  };

  const loadMetrics = async () => {
    try {
      setLoading(true);
      const data = await abTestingService.getExperimentMetrics(experimentId);
      setMetrics(data);
    } catch (error) {
      console.error("Failed to load metrics:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleStart = async () => {
    try {
      setActionLoading(true);
      await abTestingService.startExperiment(experimentId);
      await loadExperiment();
    } catch (error) {
      console.error("Failed to start experiment:", error);
      setError("Failed to start experiment");
    } finally {
      setActionLoading(false);
    }
  };

  const handlePause = async () => {
    try {
      setActionLoading(true);
      await abTestingService.pauseExperiment(experimentId);
      await loadExperiment();
    } catch (error) {
      console.error("Failed to pause experiment:", error);
      setError("Failed to pause experiment");
    } finally {
      setActionLoading(false);
    }
  };

  const handleComplete = async () => {
    try {
      setActionLoading(true);
      const result = await abTestingService.completeExperiment(experimentId);
      await loadExperiment();
      setError(""); // Show success message instead
    } catch (error) {
      console.error("Failed to complete experiment:", error);
      setError("Failed to complete experiment");
    } finally {
      setActionLoading(false);
    }
  };

  if (loading && !metrics) {
    return (
      <div className="p-6 max-w-7xl mx-auto">
        <div className="text-center py-8">Loading experiment...</div>
      </div>
    );
  }

  if (!experiment || !metrics) {
    return (
      <div className="p-6 max-w-7xl mx-auto">
        <div className="text-center py-8">Experiment not found</div>
      </div>
    );
  }

  const getStatusBadge = (status: string) => {
    const statusConfig = {
      draft: { variant: "secondary" as const, color: "#6b7280" },
      running: { variant: "default" as const, color: "#3b82f6" },
      paused: { variant: "warning" as const, color: "#f59e0b" },
      completed: { variant: "success" as const, color: "#10b981" },
      archived: { variant: "outline" as const, color: "#6b7280" },
    };

    const config = statusConfig[status as keyof typeof statusConfig] || statusConfig.draft;
    
    return (
      <Badge variant={config.variant}>
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </Badge>
    );
  };

  const getCompletionProgress = () => {
    if (!metrics) return 0;
    
    const targetPredictions = experiment.min_sample_size * experiment.variants.length;
    return Math.min((metrics.total_predictions / targetPredictions) * 100, 100);
  };

  const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'];

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => router.push("/experiments")}
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <div className="flex items-center gap-2 mb-2">
              <h1 className="text-3xl font-bold">{experiment.name}</h1>
              {getStatusBadge(experiment.status)}
              {experiment.winner_variant_id && (
                <Badge variant="success">Winner Found</Badge>
              )}
            </div>
            {experiment.description && (
              <p className="text-muted-foreground">{experiment.description}</p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="icon"
            onClick={loadMetrics}
            disabled={loading}
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>

          {experiment.status === 'draft' && (
            <Button onClick={handleStart} disabled={actionLoading}>
              <Play className="h-4 w-4 mr-2" />
              Start Experiment
            </Button>
          )}

          {experiment.status === 'running' && (
            <>
              <Button variant="outline" onClick={handlePause} disabled={actionLoading}>
                <Pause className="h-4 w-4 mr-2" />
                Pause
              </Button>
              <Button onClick={handleComplete} disabled={actionLoading}>
                <CheckCircle className="h-4 w-4 mr-2" />
                Complete
              </Button>
            </>
          )}

          {experiment.status === 'paused' && (
            <Button onClick={handleStart} disabled={actionLoading}>
              <Play className="h-4 w-4 mr-2" />
              Resume
            </Button>
          )}
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Predictions</CardTitle>
            <Target className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics.total_predictions.toLocaleString()}</div>
            <p className="text-xs text-muted-foreground">
              Target: {(experiment.min_sample_size * experiment.variants.length).toLocaleString()}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Progress</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{getCompletionProgress().toFixed(0)}%</div>
            <Progress value={getCompletionProgress()} className="mt-2" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Duration</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {metrics.duration 
                ? `${Math.floor(metrics.duration / 3600)}h`
                : '0h'
              }
            </div>
            <p className="text-xs text-muted-foreground">
              {experiment.started_at 
                ? `Started ${formatDistanceToNow(new Date(experiment.started_at))} ago`
                : 'Not started'
              }
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Primary Metric</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-lg font-bold">{experiment.primary_metric}</div>
            {metrics.comparison && (
              <div className="flex items-center gap-1 text-sm">
                {metrics.comparison.lift_percentage > 0 ? (
                  <TrendingUp className="h-3 w-3 text-green-600" />
                ) : (
                  <TrendingDown className="h-3 w-3 text-red-600" />
                )}
                <span className={metrics.comparison.lift_percentage > 0 ? 'text-green-600' : 'text-red-600'}>
                  {metrics.comparison.lift_percentage > 0 ? '+' : ''}
                  {metrics.comparison.lift_percentage.toFixed(1)}%
                </span>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="overview" className="w-full">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="variants">Variants</TabsTrigger>
          {metrics.comparison && <TabsTrigger value="comparison">Comparison</TabsTrigger>}
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Traffic Distribution */}
            <Card>
              <CardHeader>
                <CardTitle>Traffic Distribution</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie
                      data={metrics.variants.map((v, i) => ({
                        name: v.name,
                        value: v.traffic_percentage,
                        fill: COLORS[i % COLORS.length]
                      }))}
                      cx="50%"
                      cy="50%"
                      outerRadius={80}
                      dataKey="value"
                      label={({ name, value }) => `${name}: ${value}%`}
                    >
                      {metrics.variants.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            {/* Predictions by Variant */}
            <Card>
              <CardHeader>
                <CardTitle>Predictions by Variant</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={metrics.variants}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="total_predictions" fill="#3b82f6" />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="variants" className="space-y-4">
          <div className="grid gap-4">
            {metrics.variants.map((variant, index) => (
              <Card key={variant.variant_id} className={
                variant.variant_id === experiment.winner_variant_id
                  ? 'border-green-500 bg-green-50 dark:bg-green-900/10'
                  : ''
              }>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2">
                      {variant.name}
                      {variant.variant_id === experiment.winner_variant_id && (
                        <Badge variant="success">Winner</Badge>
                      )}
                    </CardTitle>
                    <Badge variant="outline">{variant.traffic_percentage}% traffic</Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <div>
                      <p className="text-sm text-muted-foreground">Predictions</p>
                      <p className="text-2xl font-bold">{variant.total_predictions.toLocaleString()}</p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Error Rate</p>
                      <p className="text-2xl font-bold">{(variant.error_rate * 100).toFixed(2)}%</p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Avg Latency</p>
                      <p className="text-2xl font-bold">{variant.avg_latency_ms.toFixed(0)}ms</p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Model ID</p>
                      <p className="text-sm font-mono">{variant.model_id}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {metrics.comparison && (
          <TabsContent value="comparison" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Statistical Analysis</CardTitle>
                <CardDescription>
                  Comparing {metrics.variants[0].name} vs {metrics.variants[1].name}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div className="text-center">
                    <p className="text-sm text-muted-foreground mb-2">Lift</p>
                    <div className={`text-3xl font-bold ${
                      metrics.comparison.lift_percentage > 0 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {metrics.comparison.lift_percentage > 0 ? '+' : ''}
                      {metrics.comparison.lift_percentage.toFixed(1)}%
                    </div>
                  </div>
                  
                  <div className="text-center">
                    <p className="text-sm text-muted-foreground mb-2">Confidence</p>
                    <div className="text-3xl font-bold">
                      {(metrics.comparison.confidence_level * 100).toFixed(0)}%
                    </div>
                  </div>
                  
                  <div className="text-center">
                    <p className="text-sm text-muted-foreground mb-2">Significant</p>
                    <div className={`text-3xl font-bold ${
                      metrics.comparison.is_significant ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {metrics.comparison.is_significant ? 'Yes' : 'No'}
                    </div>
                  </div>
                </div>

                <div className="mt-6 pt-6 border-t">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <h4 className="font-medium mb-2">{metrics.variants[0].name} (Control)</h4>
                      <p className="text-2xl font-bold">{(metrics.comparison.variant_a_rate * 100).toFixed(2)}%</p>
                      <p className="text-sm text-muted-foreground">
                        {metrics.variants[0].total_predictions.toLocaleString()} predictions
                      </p>
                    </div>
                    
                    <div>
                      <h4 className="font-medium mb-2">{metrics.variants[1].name} (Treatment)</h4>
                      <p className="text-2xl font-bold">{(metrics.comparison.variant_b_rate * 100).toFixed(2)}%</p>
                      <p className="text-sm text-muted-foreground">
                        {metrics.variants[1].total_predictions.toLocaleString()} predictions
                      </p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
}