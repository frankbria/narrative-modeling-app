'use client'

import React from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { HugeiconsIcon } from '@/components/ui/icon'
import { AlertCircleIcon, CancelCircleIcon, CheckmarkCircle02Icon } from '@hugeicons/core-free-icons'


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

export function QualityReportCard({ report }: QualityReportProps) {
  return (
    <div className="space-y-4">
      {/* Critical Issues */}
      {report.critical_issues.length > 0 && (
        <Alert variant="destructive">
          <HugeiconsIcon icon={CancelCircleIcon} className="h-4 w-4" />
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
          <HugeiconsIcon icon={AlertCircleIcon} className="h-4 w-4" />
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
                  <HugeiconsIcon icon={CheckmarkCircle02Icon} className="h-4 w-4 text-success mt-0.5 flex-shrink-0" />
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