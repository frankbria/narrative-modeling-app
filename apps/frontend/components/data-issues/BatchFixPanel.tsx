'use client'

import React, { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Checkbox } from '@/components/ui/checkbox'
import { Alert, AlertDescription } from '@/components/ui/alert'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  CheckCircle2,
  XCircle,
  Play,
  Shield,
  AlertTriangle,
  Loader2,
  ListChecks
} from 'lucide-react'
import { DataIssue, BatchFixResponse } from '@/lib/services/data-issues'
import { IssueSeverityBadge } from './IssueSeverityBadge'

interface BatchFixPanelProps {
  issues: DataIssue[]
  selectedIssues: Set<string>
  onSelectAll: () => void
  onClearSelection: () => void
  onBatchApply: (autoSafeOnly?: boolean) => Promise<BatchFixResponse | null>
  isApplying: boolean
}

export function BatchFixPanel({
  issues,
  selectedIssues,
  onSelectAll,
  onClearSelection,
  onBatchApply,
  isApplying
}: BatchFixPanelProps) {
  const [showConfirmDialog, setShowConfirmDialog] = useState(false)
  const [autoSafeOnly, setAutoSafeOnly] = useState(true)
  const [lastResult, setLastResult] = useState<BatchFixResponse | null>(null)
  const [showResultDialog, setShowResultDialog] = useState(false)

  // Calculate statistics for selected issues
  const selectedIssuesList = issues.filter(i => selectedIssues.has(i.issue_id))
  const totalAffectedRows = selectedIssuesList.reduce((sum, i) => sum + i.affected_rows, 0)
  const autoFixableCount = selectedIssuesList.filter(i =>
    i.suggested_fixes.some(f => f.is_safe)
  ).length

  const severityCounts = selectedIssuesList.reduce((acc, issue) => {
    acc[issue.severity] = (acc[issue.severity] || 0) + 1
    return acc
  }, {} as Record<string, number>)

  const handleBatchApply = async () => {
    setShowConfirmDialog(false)
    const result = await onBatchApply(autoSafeOnly)
    if (result) {
      setLastResult(result)
      setShowResultDialog(true)
    }
  }

  if (selectedIssues.size === 0) {
    return (
      <Card>
        <CardContent className="py-8 text-center">
          <ListChecks className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
          <h3 className="font-medium mb-2">No Issues Selected</h3>
          <p className="text-sm text-muted-foreground mb-4">
            Select issues from the list to apply batch fixes
          </p>
          <Button variant="outline" onClick={onSelectAll}>
            Select All Issues
          </Button>
        </CardContent>
      </Card>
    )
  }

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>Batch Fix</span>
            <Badge variant="secondary">{selectedIssues.size} selected</Badge>
          </CardTitle>
          <CardDescription>
            Apply fixes to multiple issues at once
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
          {/* Summary stats */}
          <div className="grid grid-cols-2 gap-4">
            <div className="p-3 bg-muted rounded-lg">
              <div className="text-2xl font-bold">{selectedIssues.size}</div>
              <div className="text-sm text-muted-foreground">Issues selected</div>
            </div>
            <div className="p-3 bg-muted rounded-lg">
              <div className="text-2xl font-bold">{totalAffectedRows.toLocaleString()}</div>
              <div className="text-sm text-muted-foreground">Total rows affected</div>
            </div>
          </div>

          {/* Severity breakdown */}
          <div>
            <h4 className="text-sm font-medium mb-2">Severity Breakdown</h4>
            <div className="flex flex-wrap gap-2">
              {Object.entries(severityCounts).map(([severity, count]) => (
                <div key={severity} className="flex items-center gap-1">
                  <IssueSeverityBadge severity={severity} />
                  <span className="text-sm text-muted-foreground">({count})</span>
                </div>
              ))}
            </div>
          </div>

          {/* Auto-fixable indicator */}
          <div className="flex items-center gap-2 p-3 border rounded-lg">
            <Shield className="h-5 w-5 text-green-600" />
            <div className="flex-1">
              <div className="font-medium">{autoFixableCount} auto-fixable</div>
              <div className="text-sm text-muted-foreground">
                These issues have safe, automatic fixes
              </div>
            </div>
          </div>

          {/* Options */}
          <div className="space-y-3">
            <div className="flex items-center space-x-2">
              <Checkbox
                id="auto-safe"
                checked={autoSafeOnly}
                onCheckedChange={(checked) => setAutoSafeOnly(checked as boolean)}
              />
              <label
                htmlFor="auto-safe"
                className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
              >
                Only apply safe fixes (recommended)
              </label>
            </div>

            {!autoSafeOnly && (
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>
                  Warning: Applying all fixes may result in data loss. Review each fix carefully.
                </AlertDescription>
              </Alert>
            )}
          </div>
        </CardContent>

        <CardFooter className="flex justify-between">
          <Button variant="outline" onClick={onClearSelection}>
            Clear Selection
          </Button>
          <Button
            onClick={() => setShowConfirmDialog(true)}
            disabled={isApplying || (autoSafeOnly && autoFixableCount === 0)}
          >
            {isApplying ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Play className="h-4 w-4 mr-2" />
            )}
            Apply {autoSafeOnly ? autoFixableCount : selectedIssues.size} Fixes
          </Button>
        </CardFooter>
      </Card>

      {/* Confirmation Dialog */}
      <Dialog open={showConfirmDialog} onOpenChange={setShowConfirmDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirm Batch Fix</DialogTitle>
            <DialogDescription>
              You are about to apply fixes to {autoSafeOnly ? autoFixableCount : selectedIssues.size} issues.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <Alert>
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                This action will modify your dataset. A new version will be created.
              </AlertDescription>
            </Alert>

            <div className="text-sm">
              <strong>Issues to fix:</strong> {autoSafeOnly ? autoFixableCount : selectedIssues.size}<br />
              <strong>Total rows affected:</strong> {totalAffectedRows.toLocaleString()}<br />
              <strong>Mode:</strong> {autoSafeOnly ? 'Safe fixes only' : 'All selected fixes'}
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowConfirmDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleBatchApply} disabled={isApplying}>
              {isApplying ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <CheckCircle2 className="h-4 w-4 mr-2" />
              )}
              Confirm
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Result Dialog */}
      <Dialog open={showResultDialog} onOpenChange={setShowResultDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {lastResult?.success ? (
                <span className="flex items-center gap-2 text-green-600">
                  <CheckCircle2 className="h-5 w-5" />
                  Batch Fix Complete
                </span>
              ) : (
                <span className="flex items-center gap-2 text-red-600">
                  <XCircle className="h-5 w-5" />
                  Batch Fix Failed
                </span>
              )}
            </DialogTitle>
          </DialogHeader>

          {lastResult && (
            <div className="space-y-4 py-4">
              {/* Summary */}
              <div className="grid grid-cols-3 gap-4 text-center">
                <div className="p-3 bg-green-50 dark:bg-green-950 rounded-lg">
                  <div className="text-2xl font-bold text-green-600">{lastResult.successful_fixes}</div>
                  <div className="text-sm text-green-700 dark:text-green-400">Successful</div>
                </div>
                <div className="p-3 bg-red-50 dark:bg-red-950 rounded-lg">
                  <div className="text-2xl font-bold text-red-600">{lastResult.failed_fixes}</div>
                  <div className="text-sm text-red-700 dark:text-red-400">Failed</div>
                </div>
                <div className="p-3 bg-blue-50 dark:bg-blue-950 rounded-lg">
                  <div className="text-2xl font-bold text-blue-600">{lastResult.total_rows_affected.toLocaleString()}</div>
                  <div className="text-sm text-blue-700 dark:text-blue-400">Rows Fixed</div>
                </div>
              </div>

              {/* Execution time */}
              <div className="text-sm text-muted-foreground text-center">
                Completed in {lastResult.execution_time_ms}ms
              </div>

              {/* Warnings */}
              {lastResult.warnings && lastResult.warnings.length > 0 && (
                <Alert>
                  <AlertTriangle className="h-4 w-4" />
                  <AlertDescription>
                    <ul className="list-disc list-inside">
                      {lastResult.warnings.map((warning, i) => (
                        <li key={i}>{warning}</li>
                      ))}
                    </ul>
                  </AlertDescription>
                </Alert>
              )}

              {/* Error */}
              {lastResult.error && (
                <Alert variant="destructive">
                  <XCircle className="h-4 w-4" />
                  <AlertDescription>{lastResult.error}</AlertDescription>
                </Alert>
              )}
            </div>
          )}

          <DialogFooter>
            <Button onClick={() => setShowResultDialog(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
