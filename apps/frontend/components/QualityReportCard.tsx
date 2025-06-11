'use client'

import React from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { 
  CheckCircle2, 
  AlertCircle, 
  XCircle, 
  BarChart3,
  Shield,
  Clock,
  Database,
  GitBranch,
  Zap
} from 'lucide-react'

interface QualityDimensionScore {
  dimension: string
  score: number
}

interface QualityIssue {
  dimension: string
  column?: string
  severity: 'low' | 'medium' | 'high'
  description: string
  affected_rows: number
  affected_percentage: number
}

interface QualityReportProps {
  report: {
    overall_quality_score: number
    dimension_scores: Record<string, number>
    critical_issues: QualityIssue[]
    warnings: QualityIssue[]
    recommendations: string[]
  }
}

const dimensionIcons: Record<string, React.ReactNode> = {
  completeness: <Database className="h-4 w-4" />,
  consistency: <GitBranch className="h-4 w-4" />,
  accuracy: <BarChart3 className="h-4 w-4" />,
  validity: <Shield className="h-4 w-4" />,
  uniqueness: <Zap className="h-4 w-4" />,
  timeliness: <Clock className="h-4 w-4" />,
}

const getScoreColor = (score: number): string => {
  if (score >= 0.9) return 'text-green-600'
  if (score >= 0.7) return 'text-yellow-600'
  return 'text-red-600'
}

const getScoreIcon = (score: number) => {
  if (score >= 0.9) return <CheckCircle2 className="h-5 w-5 text-green-600" />
  if (score >= 0.7) return <AlertCircle className="h-5 w-5 text-yellow-600" />
  return <XCircle className="h-5 w-5 text-red-600" />
}

const getSeverityColor = (severity: string): string => {
  switch (severity) {
    case 'high': return 'destructive'
    case 'medium': return 'secondary'
    case 'low': return 'outline'
    default: return 'outline'
  }
}

export function QualityReportCard({ report }: QualityReportProps) {
  const overallScore = report.overall_quality_score * 100

  return (
    <div className="space-y-4">
      {/* Overall Score Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            Data Quality Score
            {getScoreIcon(report.overall_quality_score)}
          </CardTitle>
          <CardDescription>
            Overall assessment of data quality across all dimensions
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className={`text-2xl font-bold ${getScoreColor(report.overall_quality_score)}`}>
                {overallScore.toFixed(1)}%
              </span>
              <Badge variant={overallScore >= 80 ? 'default' : overallScore >= 60 ? 'secondary' : 'destructive'}>
                {overallScore >= 80 ? 'Good' : overallScore >= 60 ? 'Fair' : 'Poor'}
              </Badge>
            </div>
            <Progress value={overallScore} className="h-3" />
          </div>
        </CardContent>
      </Card>

      {/* Dimension Scores */}
      <Card>
        <CardHeader>
          <CardTitle>Quality Dimensions</CardTitle>
          <CardDescription>
            Detailed breakdown by quality dimension
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4">
            {Object.entries(report.dimension_scores).map(([dimension, score]) => (
              <div key={dimension} className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {dimensionIcons[dimension] || <BarChart3 className="h-4 w-4" />}
                    <span className="text-sm font-medium capitalize">{dimension}</span>
                  </div>
                  <span className={`text-sm font-bold ${getScoreColor(score)}`}>
                    {(score * 100).toFixed(0)}%
                  </span>
                </div>
                <Progress value={score * 100} className="h-2" />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Critical Issues */}
      {report.critical_issues.length > 0 && (
        <Alert variant="destructive">
          <XCircle className="h-4 w-4" />
          <AlertTitle>Critical Issues ({report.critical_issues.length})</AlertTitle>
          <AlertDescription>
            <ul className="mt-2 space-y-1">
              {report.critical_issues.slice(0, 3).map((issue, index) => (
                <li key={index} className="text-sm">
                  • {issue.description} ({issue.affected_percentage.toFixed(1)}% affected)
                </li>
              ))}
              {report.critical_issues.length > 3 && (
                <li className="text-sm text-muted-foreground">
                  ... and {report.critical_issues.length - 3} more issues
                </li>
              )}
            </ul>
          </AlertDescription>
        </Alert>
      )}

      {/* Warnings */}
      {report.warnings.length > 0 && (
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Warnings ({report.warnings.length})</AlertTitle>
          <AlertDescription>
            <ul className="mt-2 space-y-1">
              {report.warnings.slice(0, 3).map((warning, index) => (
                <li key={index} className="text-sm">
                  • {warning.description}
                  {warning.column && <span className="text-muted-foreground"> (column: {warning.column})</span>}
                </li>
              ))}
              {report.warnings.length > 3 && (
                <li className="text-sm text-muted-foreground">
                  ... and {report.warnings.length - 3} more warnings
                </li>
              )}
            </ul>
          </AlertDescription>
        </Alert>
      )}

      {/* Recommendations */}
      {report.recommendations.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Recommendations</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {report.recommendations.map((recommendation, index) => (
                <li key={index} className="flex items-start gap-2">
                  <CheckCircle2 className="h-4 w-4 text-green-600 mt-0.5 flex-shrink-0" />
                  <span className="text-sm">{recommendation}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  )
}