'use client'

import React, { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { CheckCircle } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { 
  Sparkles, 
  RefreshCw, 
  Brain,
  TrendingUp,
  AlertTriangle,
  Lightbulb,
  FileText,
  Loader2
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'

interface AIInsight {
  type: string
  title: string
  description: string
  details?: any
}

interface AISummary {
  overview: string
  issues: string[]
  relationships: string[]
  suggestions: string[]
  rawMarkdown?: string
  confidence_score?: number
  analysis_depth?: string
  model_used?: string
  processing_time?: number
}

interface AIInsightsPanelProps {
  datasetId: string
  initialSummary?: AISummary
}

export function AIInsightsPanel({ datasetId, initialSummary }: AIInsightsPanelProps) {
  const [summary, setSummary] = useState<AISummary | null>(initialSummary || null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState('overview')

  const generateSummary = async () => {
    try {
      setLoading(true)
      setError(null)
      
      const response = await fetch(`/api/ai/summarize/${datasetId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
      })

      if (!response.ok) {
        throw new Error('Failed to generate AI summary')
      }

      const data = await response.json()
      setSummary(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!summary && !loading) {
      generateSummary()
    }
  }, [datasetId])

  if (loading && !summary) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center h-64 space-y-4">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-muted-foreground">Generating AI insights...</p>
        </CardContent>
      </Card>
    )
  }

  if (error && !summary) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center h-64 space-y-4">
          <AlertTriangle className="h-8 w-8 text-destructive" />
          <p className="text-destructive">Error: {error}</p>
          <Button onClick={generateSummary} variant="outline" size="sm">
            <RefreshCw className="mr-2 h-4 w-4" />
            Retry
          </Button>
        </CardContent>
      </Card>
    )
  }

  if (!summary) {
    return null
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            <CardTitle>AI Insights</CardTitle>
          </div>
          <div className="flex items-center gap-2">
            {summary.confidence_score && (
              <Badge variant="outline">
                Confidence: {(summary.confidence_score * 100).toFixed(0)}%
              </Badge>
            )}
            {summary.model_used && (
              <Badge variant="secondary">
                {summary.model_used}
              </Badge>
            )}
            <Button 
              onClick={generateSummary} 
              variant="outline" 
              size="sm"
              disabled={loading}
            >
              {loading ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="mr-2 h-4 w-4" />
              )}
              Regenerate
            </Button>
          </div>
        </div>
        <CardDescription>
          AI-powered analysis and recommendations for your dataset
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="issues">Issues</TabsTrigger>
            <TabsTrigger value="insights">Insights</TabsTrigger>
            <TabsTrigger value="detailed">Detailed</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-4">
            <div className="rounded-lg bg-muted p-4">
              <div className="flex items-start gap-2">
                <Brain className="h-5 w-5 text-primary mt-0.5" />
                <p className="text-sm">{summary.overview}</p>
              </div>
            </div>
            
            {summary.suggestions.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-sm font-semibold flex items-center gap-2">
                  <Lightbulb className="h-4 w-4" />
                  Key Recommendations
                </h4>
                <ul className="space-y-2">
                  {summary.suggestions.slice(0, 3).map((suggestion, index) => (
                    <li key={index} className="flex items-start gap-2 text-sm">
                      <span className="text-primary">•</span>
                      <span>{suggestion}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </TabsContent>

          <TabsContent value="issues" className="space-y-4">
            {summary.issues.length > 0 ? (
              <div className="space-y-3">
                {summary.issues.map((issue, index) => (
                  <Alert key={index} variant={index === 0 ? "destructive" : "default"}>
                    <AlertTriangle className="h-4 w-4" />
                    <AlertDescription>{issue}</AlertDescription>
                  </Alert>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                <CheckCircle className="h-8 w-8 mx-auto mb-2 text-green-600" />
                <p>No significant issues detected</p>
              </div>
            )}
          </TabsContent>

          <TabsContent value="insights" className="space-y-4">
            {summary.relationships.length > 0 ? (
              <div className="space-y-3">
                <h4 className="text-sm font-semibold flex items-center gap-2">
                  <TrendingUp className="h-4 w-4" />
                  Discovered Patterns & Relationships
                </h4>
                <ul className="space-y-2">
                  {summary.relationships.map((relationship, index) => (
                    <li key={index} className="flex items-start gap-2 text-sm">
                      <span className="text-primary">→</span>
                      <span>{relationship}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                <p>No significant patterns detected</p>
              </div>
            )}
          </TabsContent>

          <TabsContent value="detailed" className="prose prose-sm dark:prose-invert max-w-none">
            {summary.rawMarkdown ? (
              <div className="rounded-lg border p-4 max-h-96 overflow-y-auto">
                <ReactMarkdown>{summary.rawMarkdown}</ReactMarkdown>
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                <FileText className="h-8 w-8 mx-auto mb-2" />
                <p>No detailed analysis available</p>
              </div>
            )}
          </TabsContent>
        </Tabs>

        {loading && (
          <div className="absolute inset-0 bg-background/50 flex items-center justify-center rounded-lg">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
        )}
      </CardContent>
    </Card>
  )
}