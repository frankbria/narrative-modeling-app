'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { useSession } from 'next-auth/react'
import { getAuthToken } from '@/lib/auth-helpers'
import { ModelService, ModelInfo } from '@/lib/services/model'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { 
  Brain, 
  Loader2, 
  ArrowLeft, 
  Eye, 
  BarChart3, 
  Calendar, 
  Target,
  Layers,
  TrendingUp,
  AlertCircle,
  FileText,
  Clock,
  Database
} from 'lucide-react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ModelPerformanceChart } from '@/components/ModelPerformanceChart'
import { Alert, AlertDescription } from '@/components/ui/alert'

export default function ModelDetailPage() {
  const params = useParams()
  const { data: session } = useSession()
  const router = useRouter()
  
  const modelId = params?.id as string
  const [model, setModel] = useState<ModelInfo | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (session && modelId) {
      fetchModel()
    }
  }, [session, modelId])

  const fetchModel = async () => {
    try {
      setIsLoading(true)
      const token = await getAuthToken()
      const modelData = await ModelService.getModel(modelId, token || '')
      setModel(modelData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load model')
    } finally {
      setIsLoading(false)
    }
  }

  if (!session) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Card className="w-96">
          <CardContent className="pt-6">
            <p className="text-center text-muted-foreground">
              Please log in to view model details
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
        <span className="text-lg">Loading model details...</span>
      </div>
    )
  }

  if (error || !model) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Card className="w-96">
          <CardContent className="pt-6 space-y-4">
            <AlertCircle className="h-12 w-12 text-muted-foreground mx-auto" />
            <p className="text-center text-muted-foreground">
              {error || 'Model not found'}
            </p>
            <div className="flex justify-center">
              <Link href="/model">
                <Button variant="outline">
                  <ArrowLeft className="mr-2 h-4 w-4" />
                  Back to Models
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  const formatProblemType = (type: string) => {
    return type.split('_').map(word => 
      word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ')
  }

  const getProblemTypeColor = (type: string) => {
    switch (type) {
      case 'binary_classification':
        return 'bg-blue-500'
      case 'multiclass_classification':
        return 'bg-purple-500'
      case 'regression':
        return 'bg-green-500'
      case 'time_series':
        return 'bg-orange-500'
      default:
        return 'bg-gray-500'
    }
  }

  return (
    <div className="container mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Link href="/model">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back
              </Button>
            </Link>
            <h1 className="text-3xl font-bold flex items-center gap-2">
              <Brain className="h-8 w-8" />
              {model.name}
            </h1>
          </div>
          {model.description && (
            <p className="text-muted-foreground ml-12">
              {model.description}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <Button 
            onClick={() => router.push(`/predict?model=${model.model_id}`)}
            disabled={!model.is_active}
          >
            <Eye className="mr-2 h-4 w-4" />
            Use Model
          </Button>
        </div>
      </div>

      {!model.is_active && (
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            This model is inactive and cannot be used for predictions
          </AlertDescription>
        </Alert>
      )}

      {/* Overview Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Problem Type
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Badge className={getProblemTypeColor(model.problem_type)}>
              {formatProblemType(model.problem_type)}
            </Badge>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Target Column
            </CardTitle>
          </CardHeader>
          <CardContent className="flex items-center gap-2">
            <Target className="h-4 w-4 text-muted-foreground" />
            <span className="font-medium">{model.target_column}</span>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Created
            </CardTitle>
          </CardHeader>
          <CardContent className="flex items-center gap-2">
            <Calendar className="h-4 w-4 text-muted-foreground" />
            <span className="font-medium">
              {new Date(model.created_at).toLocaleDateString()}
            </span>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Last Used
            </CardTitle>
          </CardHeader>
          <CardContent className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-muted-foreground" />
            <span className="font-medium">
              {model.last_used_at 
                ? new Date(model.last_used_at).toLocaleDateString()
                : 'Never'
              }
            </span>
          </CardContent>
        </Card>
      </div>

      {/* Detailed Information */}
      <Tabs defaultValue="performance" className="space-y-4">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="performance">Performance</TabsTrigger>
          <TabsTrigger value="features">Features</TabsTrigger>
          <TabsTrigger value="details">Details</TabsTrigger>
        </TabsList>

        <TabsContent value="performance">
          <ModelPerformanceChart
            cvScore={model.cv_score}
            testScore={model.test_score}
            problemType={model.problem_type}
            algorithm={model.algorithm}
            nFeatures={model.n_features}
            nSamplesTrain={model.n_samples_train}
          />
        </TabsContent>

        <TabsContent value="features" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Layers className="h-5 w-5" />
                Feature Information
              </CardTitle>
              <CardDescription>
                {model.n_features} features used in model training
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-muted-foreground">Total Features</p>
                    <p className="text-2xl font-bold">{model.n_features}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Training Samples</p>
                    <p className="text-2xl font-bold">{model.n_samples_train.toLocaleString()}</p>
                  </div>
                </div>
                
                <div className="space-y-2">
                  <h4 className="text-sm font-medium">Feature List</h4>
                  <div className="max-h-96 overflow-y-auto space-y-1">
                    {model.feature_names.map((feature, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between py-2 px-3 rounded-lg bg-muted/50"
                      >
                        <span className="text-sm font-mono">{feature}</span>
                        <Badge variant="outline" className="text-xs">
                          Feature {idx + 1}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="details" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5" />
                Model Details
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <p className="text-sm text-muted-foreground">Model ID</p>
                  <p className="font-mono text-sm">{model.model_id}</p>
                </div>
                <div className="space-y-2">
                  <p className="text-sm text-muted-foreground">Algorithm</p>
                  <p className="font-medium">{model.algorithm}</p>
                </div>
                <div className="space-y-2">
                  <p className="text-sm text-muted-foreground">Status</p>
                  <Badge variant={model.is_active ? 'default' : 'secondary'}>
                    {model.is_active ? 'Active' : 'Inactive'}
                  </Badge>
                </div>
                <div className="space-y-2">
                  <p className="text-sm text-muted-foreground">Data Source</p>
                  <p className="font-medium flex items-center gap-2">
                    <Database className="h-4 w-4" />
                    Dataset
                  </p>
                </div>
              </div>

              <div className="pt-4 border-t">
                <h4 className="text-sm font-medium mb-2">Performance Summary</h4>
                <div className="grid grid-cols-2 gap-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Cross-Validation Score</span>
                    <span className="font-medium">{(model.cv_score * 100).toFixed(1)}%</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Test Score</span>
                    <span className="font-medium">{(model.test_score * 100).toFixed(1)}%</span>
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t">
                <h4 className="text-sm font-medium mb-2">Training Configuration</h4>
                <div className="space-y-2 text-sm">
                  <div className="flex items-center gap-2">
                    <TrendingUp className="h-4 w-4 text-muted-foreground" />
                    <span>Automated feature engineering applied</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <BarChart3 className="h-4 w-4 text-muted-foreground" />
                    <span>Cross-validation performed</span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}