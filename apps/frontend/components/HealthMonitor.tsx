'use client'

import React, { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Activity, AlertCircle, CheckCircle2, Clock, Database, Server } from 'lucide-react'

interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy'
  timestamp: string
  version: string
}

interface HealthMetrics {
  memory_usage: {
    current: number
    peak: number
    percentage: number
  }
  api: {
    total_requests: number
    error_rate: number
    avg_response_time: number
  }
  security: {
    total_events: number
    high_risk_detections: number
    blocked_requests: number
  }
  uploads: {
    active_sessions: number
    total_processed: number
    total_size_mb: number
  }
}

interface HealthMonitorProps {
  backendUrl?: string
  refreshInterval?: number
}

export function HealthMonitor({ 
  backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  refreshInterval = 30000 // 30 seconds
}: HealthMonitorProps) {
  const [status, setStatus] = useState<HealthStatus | null>(null)
  const [metrics, setMetrics] = useState<HealthMetrics | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date())

  const fetchHealthData = async () => {
    try {
      setError(null)
      
      // Fetch health status
      const statusResponse = await fetch(`${backendUrl}/api/v1/health/status`)
      if (!statusResponse.ok) throw new Error('Failed to fetch health status')
      const statusData = await statusResponse.json()
      setStatus(statusData)

      // Fetch health metrics
      const metricsResponse = await fetch(`${backendUrl}/api/v1/health/metrics`)
      if (!metricsResponse.ok) throw new Error('Failed to fetch health metrics')
      const metricsData = await metricsResponse.json()
      setMetrics(metricsData)

      setLastUpdate(new Date())
    } catch (err) {
      console.error('Health check error:', err)
      setError(err instanceof Error ? err.message : 'Unknown error')
      setStatus(null)
      setMetrics(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchHealthData()
    const interval = setInterval(fetchHealthData, refreshInterval)
    return () => clearInterval(interval)
  }, [backendUrl, refreshInterval])

  const getStatusIcon = () => {
    if (loading) return <Activity className="h-5 w-5 animate-pulse" />
    if (error || !status) return <AlertCircle className="h-5 w-5 text-red-500" />
    if (status.status === 'healthy') return <CheckCircle2 className="h-5 w-5 text-green-500" />
    if (status.status === 'degraded') return <AlertCircle className="h-5 w-5 text-yellow-500" />
    return <AlertCircle className="h-5 w-5 text-red-500" />
  }

  const getStatusText = () => {
    if (loading) return 'Checking...'
    if (error || !status) return 'Unhealthy'
    return status.status.charAt(0).toUpperCase() + status.status.slice(1)
  }

  const formatBytes = (bytes: number) => {
    const mb = bytes / (1024 * 1024)
    return `${mb.toFixed(2)} MB`
  }

  const formatPercentage = (value: number) => `${(value * 100).toFixed(1)}%`

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Server className="h-5 w-5" />
            System Health Monitor
          </CardTitle>
          <CardDescription>
            Real-time monitoring of backend services
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {/* Status Overview */}
            <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
              <div className="flex items-center gap-3">
                {getStatusIcon()}
                <div>
                  <p className="font-medium">System Status</p>
                  <p className="text-sm text-muted-foreground">{getStatusText()}</p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-sm text-muted-foreground">Last Update</p>
                <p className="text-sm font-medium flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  {lastUpdate.toLocaleTimeString()}
                </p>
              </div>
            </div>

            {/* Error Display */}
            {error && (
              <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
                <p className="text-sm text-red-800">{error}</p>
              </div>
            )}

            {/* Metrics Display */}
            {metrics && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Memory Usage */}
                <div className="p-4 border rounded-lg">
                  <h4 className="font-medium mb-2 flex items-center gap-2">
                    <Database className="h-4 w-4" />
                    Memory Usage
                  </h4>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Current</span>
                      <span className="font-medium">{formatBytes(metrics.memory_usage.current)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Peak</span>
                      <span className="font-medium">{formatBytes(metrics.memory_usage.peak)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Usage</span>
                      <span className="font-medium">{formatPercentage(metrics.memory_usage.percentage)}</span>
                    </div>
                  </div>
                </div>

                {/* API Performance */}
                <div className="p-4 border rounded-lg">
                  <h4 className="font-medium mb-2 flex items-center gap-2">
                    <Activity className="h-4 w-4" />
                    API Performance
                  </h4>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Total Requests</span>
                      <span className="font-medium">{metrics.api.total_requests.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Error Rate</span>
                      <span className="font-medium">{formatPercentage(metrics.api.error_rate)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Avg Response</span>
                      <span className="font-medium">{metrics.api.avg_response_time.toFixed(0)}ms</span>
                    </div>
                  </div>
                </div>

                {/* Security Events */}
                <div className="p-4 border rounded-lg">
                  <h4 className="font-medium mb-2 flex items-center gap-2">
                    <AlertCircle className="h-4 w-4" />
                    Security Events
                  </h4>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Total Events</span>
                      <span className="font-medium">{metrics.security.total_events.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">High Risk</span>
                      <span className="font-medium text-red-600">{metrics.security.high_risk_detections}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Blocked</span>
                      <span className="font-medium">{metrics.security.blocked_requests}</span>
                    </div>
                  </div>
                </div>

                {/* Upload Statistics */}
                <div className="p-4 border rounded-lg">
                  <h4 className="font-medium mb-2 flex items-center gap-2">
                    <Server className="h-4 w-4" />
                    Upload Statistics
                  </h4>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Active Sessions</span>
                      <span className="font-medium">{metrics.uploads.active_sessions}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Total Processed</span>
                      <span className="font-medium">{metrics.uploads.total_processed.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Total Size</span>
                      <span className="font-medium">{metrics.uploads.total_size_mb.toFixed(2)} MB</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Version Info */}
            {status && (
              <div className="text-sm text-muted-foreground text-center pt-2">
                Version: {status.version}
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}