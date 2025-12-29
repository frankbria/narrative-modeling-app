'use client'

import React, { useEffect, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import {
  Search,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Sparkles,
  Settings,
  XCircle
} from 'lucide-react'
import { useDataIssues } from '@/hooks/useDataIssues'
import { DetectionOptions } from '@/lib/services/data-issues'
import { IssueList } from './IssueList'
import { BatchFixPanel } from './BatchFixPanel'
import { IssueSeverityBadge } from './IssueSeverityBadge'

interface DataIssueDetectorProps {
  datasetId: string
  onIssuesChange?: () => void
}

export function DataIssueDetector({ datasetId, onIssuesChange }: DataIssueDetectorProps) {
  const {
    issues,
    summary,
    selectedIssues,
    isLoading,
    isDetecting,
    isApplying,
    error,
    detectIssues,
    refreshIssues,
    selectIssue,
    deselectIssue,
    selectAllIssues,
    clearSelection,
    previewFix,
    applyFix,
    batchApplyFixes,
    clearError,
  } = useDataIssues(datasetId)

  const [detectionOptions, setDetectionOptions] = useState<DetectionOptions>({
    include_ai_analysis: true,
    check_missing_values: true,
    check_duplicates: true,
    check_outliers: true,
    check_inconsistencies: true,
    check_type_mismatches: true,
    outlier_method: 'iqr',
    outlier_threshold: 1.5,
  })

  const [activeTab, setActiveTab] = useState('issues')
  const [showOptions, setShowOptions] = useState(false)

  // Load cached issues on mount
  useEffect(() => {
    refreshIssues()
  }, [refreshIssues])

  const handleDetect = async () => {
    await detectIssues(detectionOptions)
    if (onIssuesChange) onIssuesChange()
  }

  const handleApplyFix = async (issueId: string, fixId?: string) => {
    await applyFix(issueId, fixId)
    if (onIssuesChange) onIssuesChange()
  }

  const handleBatchApply = async (autoSafeOnly?: boolean) => {
    const result = await batchApplyFixes(autoSafeOnly)
    if (onIssuesChange && result?.success) onIssuesChange()
    return result
  }

  return (
    <div className="space-y-4">
      {/* Header with detect button */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                Data Issue Detection
                {isDetecting && (
                  <Badge variant="secondary">
                    <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                    Analyzing...
                  </Badge>
                )}
              </CardTitle>
              <CardDescription>
                Detect and fix data quality issues with AI-powered analysis
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowOptions(!showOptions)}
              >
                <Settings className="h-4 w-4 mr-1" />
                Options
              </Button>
              <Button
                onClick={handleDetect}
                disabled={isDetecting || isLoading}
              >
                {isDetecting ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Search className="h-4 w-4 mr-2" />
                )}
                Detect Issues
              </Button>
            </div>
          </div>
        </CardHeader>

        {/* Detection Options */}
        {showOptions && (
          <CardContent className="border-t">
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 py-4">
              <div className="flex items-center space-x-2">
                <Switch
                  id="ai-analysis"
                  checked={detectionOptions.include_ai_analysis}
                  onCheckedChange={(checked) =>
                    setDetectionOptions(prev => ({ ...prev, include_ai_analysis: checked }))
                  }
                />
                <Label htmlFor="ai-analysis" className="flex items-center gap-1">
                  <Sparkles className="h-4 w-4" />
                  AI Analysis
                </Label>
              </div>

              <div className="flex items-center space-x-2">
                <Switch
                  id="missing-values"
                  checked={detectionOptions.check_missing_values}
                  onCheckedChange={(checked) =>
                    setDetectionOptions(prev => ({ ...prev, check_missing_values: checked }))
                  }
                />
                <Label htmlFor="missing-values">Missing Values</Label>
              </div>

              <div className="flex items-center space-x-2">
                <Switch
                  id="duplicates"
                  checked={detectionOptions.check_duplicates}
                  onCheckedChange={(checked) =>
                    setDetectionOptions(prev => ({ ...prev, check_duplicates: checked }))
                  }
                />
                <Label htmlFor="duplicates">Duplicates</Label>
              </div>

              <div className="flex items-center space-x-2">
                <Switch
                  id="outliers"
                  checked={detectionOptions.check_outliers}
                  onCheckedChange={(checked) =>
                    setDetectionOptions(prev => ({ ...prev, check_outliers: checked }))
                  }
                />
                <Label htmlFor="outliers">Outliers</Label>
              </div>

              <div className="flex items-center space-x-2">
                <Switch
                  id="inconsistencies"
                  checked={detectionOptions.check_inconsistencies}
                  onCheckedChange={(checked) =>
                    setDetectionOptions(prev => ({ ...prev, check_inconsistencies: checked }))
                  }
                />
                <Label htmlFor="inconsistencies">Inconsistencies</Label>
              </div>

              <div className="flex items-center space-x-2">
                <Switch
                  id="type-mismatches"
                  checked={detectionOptions.check_type_mismatches}
                  onCheckedChange={(checked) =>
                    setDetectionOptions(prev => ({ ...prev, check_type_mismatches: checked }))
                  }
                />
                <Label htmlFor="type-mismatches">Type Mismatches</Label>
              </div>
            </div>
          </CardContent>
        )}
      </Card>

      {/* Error display */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription className="flex items-center justify-between">
            {error}
            <Button variant="ghost" size="sm" onClick={clearError}>
              <XCircle className="h-4 w-4" />
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {/* Summary panel */}
      {summary && (
        <Card>
          <CardContent className="pt-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="text-center">
                <div className="text-3xl font-bold">{summary.total_issues}</div>
                <div className="text-sm text-muted-foreground">Total Issues</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold text-red-600">
                  {summary.critical_count + summary.high_count}
                </div>
                <div className="text-sm text-muted-foreground">Critical/High</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold text-green-600">{summary.auto_fixable_count}</div>
                <div className="text-sm text-muted-foreground">Auto-Fixable</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold text-blue-600">{summary.ai_detected_count}</div>
                <div className="text-sm text-muted-foreground">AI Detected</div>
              </div>
            </div>

            {/* Severity breakdown */}
            <div className="flex items-center justify-center gap-4 mt-4">
              {summary.critical_count > 0 && (
                <div className="flex items-center gap-1">
                  <IssueSeverityBadge severity="critical" />
                  <span className="text-sm">{summary.critical_count}</span>
                </div>
              )}
              {summary.high_count > 0 && (
                <div className="flex items-center gap-1">
                  <IssueSeverityBadge severity="high" />
                  <span className="text-sm">{summary.high_count}</span>
                </div>
              )}
              {summary.medium_count > 0 && (
                <div className="flex items-center gap-1">
                  <IssueSeverityBadge severity="medium" />
                  <span className="text-sm">{summary.medium_count}</span>
                </div>
              )}
              {summary.low_count > 0 && (
                <div className="flex items-center gap-1">
                  <IssueSeverityBadge severity="low" />
                  <span className="text-sm">{summary.low_count}</span>
                </div>
              )}
            </div>

            {/* Detection stats */}
            <div className="text-center text-sm text-muted-foreground mt-4">
              Analyzed {summary.rows_analyzed.toLocaleString()} rows across{' '}
              {summary.columns_analyzed} columns in {summary.detection_time_ms}ms
            </div>
          </CardContent>
        </Card>
      )}

      {/* Main content tabs */}
      {issues.length > 0 && (
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="issues" className="flex items-center gap-2">
              <AlertCircle className="h-4 w-4" />
              Issues ({issues.length})
            </TabsTrigger>
            <TabsTrigger value="batch" className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4" />
              Batch Fix
              {selectedIssues.size > 0 && (
                <Badge variant="secondary">{selectedIssues.size}</Badge>
              )}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="issues" className="mt-4">
            <IssueList
              issues={issues}
              selectedIssues={selectedIssues}
              onSelectIssue={selectIssue}
              onDeselectIssue={deselectIssue}
              onPreviewFix={previewFix}
              onApplyFix={handleApplyFix}
              isApplying={isApplying}
            />
          </TabsContent>

          <TabsContent value="batch" className="mt-4">
            <BatchFixPanel
              issues={issues}
              selectedIssues={selectedIssues}
              onSelectAll={selectAllIssues}
              onClearSelection={clearSelection}
              onBatchApply={handleBatchApply}
              isApplying={isApplying}
            />
          </TabsContent>
        </Tabs>
      )}

      {/* Empty state */}
      {!isDetecting && !isLoading && issues.length === 0 && !summary && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Search className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium mb-2">No Analysis Yet</h3>
            <p className="text-sm text-muted-foreground text-center max-w-md mb-4">
              Click &quot;Detect Issues&quot; to analyze your dataset for data quality issues.
              AI-powered analysis will help identify patterns and suggest fixes.
            </p>
            <Button onClick={handleDetect}>
              <Search className="h-4 w-4 mr-2" />
              Start Analysis
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Loading state */}
      {(isDetecting || isLoading) && issues.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Loader2 className="h-12 w-12 text-primary animate-spin mb-4" />
            <h3 className="text-lg font-medium mb-2">Analyzing Dataset...</h3>
            <p className="text-sm text-muted-foreground text-center max-w-md">
              Running quality checks and AI analysis. This may take a moment for large datasets.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

export default DataIssueDetector
