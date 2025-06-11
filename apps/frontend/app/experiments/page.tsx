"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import { 
  Plus, 
  Play, 
  Pause, 
  CheckCircle, 
  BarChart3, 
  TrendingUp,
  Users,
  Clock,
  Beaker
} from "lucide-react";
import { abTestingService, ABTest } from "@/lib/services/abTesting";
import { formatDistanceToNow } from "date-fns";

export default function ExperimentsPage() {
  const router = useRouter();
  const [experiments, setExperiments] = useState<ABTest[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("all");

  useEffect(() => {
    loadExperiments();
  }, [activeTab]);

  const loadExperiments = async () => {
    try {
      setLoading(true);
      const status = activeTab === "all" ? undefined : activeTab;
      const data = await abTestingService.listExperiments(status);
      setExperiments(data);
    } catch (error) {
      console.error("Failed to load experiments:", error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status: string) => {
    const statusConfig = {
      draft: { variant: "secondary" as const, icon: Beaker },
      running: { variant: "default" as const, icon: Play },
      paused: { variant: "warning" as const, icon: Pause },
      completed: { variant: "success" as const, icon: CheckCircle },
      archived: { variant: "outline" as const, icon: Clock },
    };

    const config = statusConfig[status as keyof typeof statusConfig] || statusConfig.draft;
    const Icon = config.icon;

    return (
      <Badge variant={config.variant} className="flex items-center gap-1">
        <Icon className="h-3 w-3" />
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </Badge>
    );
  };

  const getCompletionProgress = (experiment: ABTest) => {
    if (!experiment.variants.length) return 0;
    
    const totalPredictions = experiment.variants.reduce(
      (sum, variant) => sum + variant.total_predictions,
      0
    );
    const targetPredictions = experiment.min_sample_size * experiment.variants.length;
    
    return Math.min((totalPredictions / targetPredictions) * 100, 100);
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">A/B Testing</h1>
          <p className="text-muted-foreground mt-1">
            Compare model performance and find the best variant
          </p>
        </div>
        <Button onClick={() => router.push("/experiments/new")}>
          <Plus className="h-4 w-4 mr-2" />
          New Experiment
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Experiments</CardTitle>
            <Beaker className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{experiments.length}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Running</CardTitle>
            <Play className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {experiments.filter(e => e.status === 'running').length}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Completed</CardTitle>
            <CheckCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {experiments.filter(e => e.status === 'completed').length}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Avg. Lift</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {experiments
                .filter(e => e.lift_percentage)
                .reduce((sum, e) => sum + (e.lift_percentage || 0), 0) / 
                Math.max(experiments.filter(e => e.lift_percentage).length, 1)
                .toFixed(1)}%
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Experiments List */}
      <Card>
        <CardHeader>
          <CardTitle>Experiments</CardTitle>
        </CardHeader>
        <CardContent>
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList>
              <TabsTrigger value="all">All</TabsTrigger>
              <TabsTrigger value="running">Running</TabsTrigger>
              <TabsTrigger value="completed">Completed</TabsTrigger>
              <TabsTrigger value="draft">Draft</TabsTrigger>
            </TabsList>

            <TabsContent value={activeTab} className="mt-4">
              {loading ? (
                <div className="text-center py-8">Loading experiments...</div>
              ) : experiments.length === 0 ? (
                <div className="text-center py-8">
                  <p className="text-muted-foreground mb-4">No experiments found</p>
                  <Button onClick={() => router.push("/experiments/new")}>
                    Create your first experiment
                  </Button>
                </div>
              ) : (
                <div className="space-y-4">
                  {experiments.map((experiment) => (
                    <Card
                      key={experiment.experiment_id}
                      className="cursor-pointer hover:bg-muted/50 transition-colors"
                      onClick={() => router.push(`/experiments/${experiment.experiment_id}`)}
                    >
                      <CardContent className="p-6">
                        <div className="flex items-start justify-between">
                          <div className="space-y-2 flex-1">
                            <div className="flex items-center gap-2">
                              <h3 className="font-semibold text-lg">{experiment.name}</h3>
                              {getStatusBadge(experiment.status)}
                              {experiment.winner_variant_id && (
                                <Badge variant="success">
                                  Winner Found
                                </Badge>
                              )}
                            </div>
                            
                            {experiment.description && (
                              <p className="text-sm text-muted-foreground">
                                {experiment.description}
                              </p>
                            )}

                            <div className="flex items-center gap-4 text-sm text-muted-foreground">
                              <div className="flex items-center gap-1">
                                <Users className="h-4 w-4" />
                                {experiment.variants.length} variants
                              </div>
                              <div className="flex items-center gap-1">
                                <BarChart3 className="h-4 w-4" />
                                {experiment.primary_metric}
                              </div>
                              <div className="flex items-center gap-1">
                                <Clock className="h-4 w-4" />
                                Created {formatDistanceToNow(new Date(experiment.created_at))} ago
                              </div>
                            </div>

                            {experiment.status === 'running' && (
                              <div className="space-y-1">
                                <div className="flex justify-between text-sm">
                                  <span>Progress</span>
                                  <span>{getCompletionProgress(experiment).toFixed(0)}%</span>
                                </div>
                                <Progress value={getCompletionProgress(experiment)} className="h-2" />
                              </div>
                            )}

                            {experiment.status === 'completed' && experiment.lift_percentage && (
                              <div className="flex items-center gap-4 mt-2">
                                <div className="text-sm">
                                  <span className="text-muted-foreground">Lift: </span>
                                  <span className={`font-semibold ${
                                    experiment.lift_percentage > 0 ? 'text-green-600' : 'text-red-600'
                                  }`}>
                                    {experiment.lift_percentage > 0 ? '+' : ''}
                                    {experiment.lift_percentage.toFixed(1)}%
                                  </span>
                                </div>
                                {experiment.statistical_significance && (
                                  <div className="text-sm">
                                    <span className="text-muted-foreground">Confidence: </span>
                                    <span className="font-semibold">
                                      {(experiment.statistical_significance * 100).toFixed(0)}%
                                    </span>
                                  </div>
                                )}
                              </div>
                            )}
                          </div>

                          {/* Variant Summary */}
                          <div className="ml-4 space-y-2">
                            {experiment.variants.map((variant) => (
                              <div
                                key={variant.variant_id}
                                className={`text-sm p-2 rounded ${
                                  variant.variant_id === experiment.winner_variant_id
                                    ? 'bg-green-100 dark:bg-green-900/20'
                                    : 'bg-muted'
                                }`}
                              >
                                <div className="font-medium">{variant.name}</div>
                                <div className="text-muted-foreground">
                                  {variant.traffic_percentage}% traffic
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
}