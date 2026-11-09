'use client'

import { useState } from 'react'
import { useAsyncData } from '@/lib/hooks/useAsyncData'
import { useSession } from 'next-auth/react'
import { getAuthToken } from '@/lib/auth-helpers'
import { ProductionService } from '@/lib/services/production'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { HugeiconsIcon } from '@/components/ui/icon'
import { Activity01Icon, AlertCircleIcon, Key01Icon, Loading03Icon } from '@hugeicons/core-free-icons'
import Link from 'next/link'
import { ModelActivityTable } from '@/components/monitor/ModelActivityTable'
import { averageLatencyText, modelsWithPredictions } from '@/lib/monitoring'

export default function MonitoringPage() {
  const { data: session } = useSession()
  // `useSession().data` is a NEW OBJECT on every render, and useAsyncData keys
  // its effect on dep identity — passing `session` re-fetched on every render,
  // forever, behind a spinner that never cleared (#402). Depend on the user id,
  // which is a string and therefore stable, and keep `enabled` on the session
  // itself so the request still waits for auth.
  const userId = session?.user?.id
  const [activeTab, setActiveTab] = useState('overview')

  const {
    data: monitoring,
    loading: isLoading,
    error,
    reload: fetchMonitoringData,
  } = useAsyncData(
    async () => {
      const token = await getAuthToken()
      const [stats, keyUsage] = await Promise.all([
        ProductionService.getUsageOverview(token),
        ProductionService.getAPIKeyUsage(token),
      ])
      return { stats, keyUsage }
    },
    [userId],
    { enabled: !!session },
  )
  const usageStats = monitoring?.stats ?? null
  const apiKeyUsage = monitoring?.keyUsage ?? []

  if (!session) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Card className="w-96">
          <CardContent className="pt-6">
            <p className="text-center text-muted-foreground">
              Please log in to view monitoring dashboard
            </p>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <HugeiconsIcon icon={Loading03Icon} className="h-8 w-8 animate-spin mr-3 text-primary" />
        <span className="text-lg">Loading monitoring data...</span>
      </div>
    )
  }

  if (error || !usageStats) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Card className="w-96">
          <CardContent className="pt-6 space-y-4">
            <HugeiconsIcon icon={AlertCircleIcon} className="h-12 w-12 text-muted-foreground mx-auto" />
            <p className="text-center text-muted-foreground">
              {error || 'Failed to load monitoring data'}
            </p>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <HugeiconsIcon icon={Activity01Icon} className="h-8 w-8" />
            Model Monitoring
          </h1>
          <p className="text-muted-foreground mt-1">
            Monitor performance and usage of your deployed models
          </p>
        </div>
        <div className="flex gap-2">
          <Link href="/settings/api">
            <Button variant="outline">
              <HugeiconsIcon icon={Key01Icon} className="mr-2 h-4 w-4" />
              API Keys
            </Button>
          </Link>
          <Button onClick={fetchMonitoringData}>
            Refresh
          </Button>
        </div>
      </div>

      {/* Overview Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Models
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{usageStats.total_models}</div>
            <p className="text-xs text-muted-foreground mt-1">
              {modelsWithPredictions(usageStats.models).length} received predictions
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Predictions (24h)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {usageStats.total_predictions_24h.toLocaleString()}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Total predictions
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              API Keys
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{usageStats.total_api_keys}</div>
            <p className="text-xs text-muted-foreground mt-1">
              {usageStats.active_api_keys} active
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
            <div className="text-2xl font-bold">
              {averageLatencyText(usageStats.models)}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Only models that made predictions
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="overview">Model Performance</TabsTrigger>
          <TabsTrigger value="api-keys">API Key Usage</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Model Activity</CardTitle>
              <CardDescription>
                Performance metrics for your deployed models over the last 24 hours
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ModelActivityTable models={usageStats.models} />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="api-keys" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>API Key Usage</CardTitle>
              <CardDescription>
                Usage statistics for your API keys over the last 24 hours
              </CardDescription>
            </CardHeader>
            <CardContent>
              {apiKeyUsage.length === 0 ? (
                <div className="text-center py-8">
                  <HugeiconsIcon icon={Key01Icon} className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                  <p className="text-muted-foreground">No API key usage in the last 24 hours</p>
                  <Link href="/settings/api">
                    <Button variant="outline" className="mt-4">
                      Create API Key
                    </Button>
                  </Link>
                </div>
              ) : (
                <div className="space-y-4">
                  {apiKeyUsage.map((key) => (
                    <div key={key.api_key_id} className="border rounded-lg p-4">
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="font-medium">{key.name}</h4>
                        <Badge variant="outline">
                          {key.requests_last_24h} / {key.rate_limit} per hour
                        </Badge>
                      </div>
                      
                      <div className="space-y-2">
                        <div className="flex items-center justify-between text-sm">
                          <span className="text-muted-foreground">Usage Rate</span>
                          <span className="font-medium">{key.usage_percentage}%</span>
                        </div>
                        <Progress value={key.usage_percentage} className="h-2" />
                      </div>
                      
                      <div className="mt-3 flex items-center justify-between">
                        <div className="text-sm text-muted-foreground">
                          Total requests: {key.total_requests.toLocaleString()}
                        </div>
                        <div className="text-sm text-muted-foreground">
                          Models accessed: {key.models_accessed.length}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}