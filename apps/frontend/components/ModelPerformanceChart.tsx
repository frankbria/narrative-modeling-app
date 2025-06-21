'use client'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { BarChart3, TrendingUp, Activity } from 'lucide-react'

interface ModelPerformanceChartProps {
  cvScore: number
  testScore: number
  problemType: string
  algorithm: string
  nFeatures: number
  nSamplesTrain: number
}

export function ModelPerformanceChart({
  cvScore,
  testScore,
  problemType,
  algorithm,
  nFeatures,
  nSamplesTrain
}: ModelPerformanceChartProps) {
  const formatScore = (score: number) => (score * 100).toFixed(1)
  
  const getMetricName = () => {
    if (problemType.includes('classification')) return 'Accuracy'
    if (problemType === 'regression') return 'R² Score'
    return 'Score'
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5" />
            Model Performance
          </CardTitle>
          <Badge variant="outline">{algorithm}</Badge>
        </div>
        <CardDescription>
          Performance metrics for {problemType.split('_').join(' ')}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="scores" className="space-y-4">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="scores">Scores</TabsTrigger>
            <TabsTrigger value="details">Details</TabsTrigger>
          </TabsList>
          
          <TabsContent value="scores" className="space-y-4">
            <div className="space-y-4">
              {/* Cross-Validation Score */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Cross-Validation {getMetricName()}</span>
                  <span className="font-medium">{formatScore(cvScore)}%</span>
                </div>
                <div className="w-full bg-secondary rounded-full h-2">
                  <div
                    className="bg-primary h-2 rounded-full transition-all"
                    style={{ width: `${cvScore * 100}%` }}
                  />
                </div>
              </div>
              
              {/* Test Score */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Test Set {getMetricName()}</span>
                  <span className="font-medium">{formatScore(testScore)}%</span>
                </div>
                <div className="w-full bg-secondary rounded-full h-2">
                  <div
                    className="bg-green-500 h-2 rounded-full transition-all"
                    style={{ width: `${testScore * 100}%` }}
                  />
                </div>
              </div>
              
              {/* Score Comparison */}
              <div className="mt-4 p-4 bg-muted/50 rounded-lg">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Activity className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm text-muted-foreground">Generalization Gap</span>
                  </div>
                  <span className="text-sm font-medium">
                    {Math.abs(cvScore - testScore * 100).toFixed(1)}%
                  </span>
                </div>
                {Math.abs(cvScore - testScore) < 0.05 && (
                  <p className="text-xs text-muted-foreground mt-1">
                    Good generalization - model performs consistently
                  </p>
                )}
              </div>
            </div>
          </TabsContent>
          
          <TabsContent value="details" className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <p className="text-sm text-muted-foreground">Training Samples</p>
                <p className="text-2xl font-bold">{nSamplesTrain.toLocaleString()}</p>
              </div>
              <div className="space-y-1">
                <p className="text-sm text-muted-foreground">Features Used</p>
                <p className="text-2xl font-bold">{nFeatures}</p>
              </div>
              <div className="space-y-1">
                <p className="text-sm text-muted-foreground">Algorithm</p>
                <p className="font-medium">{algorithm}</p>
              </div>
              <div className="space-y-1">
                <p className="text-sm text-muted-foreground">Problem Type</p>
                <p className="font-medium">
                  {problemType.split('_').map(w => 
                    w.charAt(0).toUpperCase() + w.slice(1)
                  ).join(' ')}
                </p>
              </div>
            </div>
            
            {/* Performance Indicators */}
            <div className="space-y-2 pt-4 border-t">
              <h4 className="text-sm font-medium">Performance Analysis</h4>
              {testScore >= 0.9 && (
                <div className="flex items-center gap-2 text-sm">
                  <TrendingUp className="h-4 w-4 text-green-500" />
                  <span className="text-green-600">Excellent performance</span>
                </div>
              )}
              {testScore >= 0.8 && testScore < 0.9 && (
                <div className="flex items-center gap-2 text-sm">
                  <TrendingUp className="h-4 w-4 text-blue-500" />
                  <span className="text-blue-600">Good performance</span>
                </div>
              )}
              {testScore >= 0.7 && testScore < 0.8 && (
                <div className="flex items-center gap-2 text-sm">
                  <Activity className="h-4 w-4 text-yellow-500" />
                  <span className="text-yellow-600">Moderate performance</span>
                </div>
              )}
              {testScore < 0.7 && (
                <div className="flex items-center gap-2 text-sm">
                  <Activity className="h-4 w-4 text-orange-500" />
                  <span className="text-orange-600">Consider improving features or data</span>
                </div>
              )}
              
              {Math.abs(cvScore - testScore) > 0.1 && (
                <div className="flex items-center gap-2 text-sm mt-2">
                  <Activity className="h-4 w-4 text-yellow-500" />
                  <span className="text-yellow-600">
                    Possible {cvScore > testScore ? 'overfitting' : 'underfitting'}
                  </span>
                </div>
              )}
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}