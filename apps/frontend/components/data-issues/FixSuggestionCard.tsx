'use client'

import React, { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Alert, AlertDescription } from '@/components/ui/alert'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Sparkles,
  Eye,
  Play,
  Shield,
  AlertTriangle,
  CheckCircle2,
  Loader2
} from 'lucide-react'
import { SuggestedFix, DataIssue, FixPreviewResponse } from '@/lib/services/data-issues'

interface FixSuggestionCardProps {
  issue: DataIssue
  fix: SuggestedFix
  onPreview: (fixId: string) => Promise<FixPreviewResponse | null>
  onApply: (fixId: string) => Promise<void>
  isApplying?: boolean
}

export function FixSuggestionCard({
  issue,
  fix,
  onPreview,
  onApply,
  isApplying = false
}: FixSuggestionCardProps) {
  const [previewData, setPreviewData] = useState<FixPreviewResponse | null>(null)
  const [isLoadingPreview, setIsLoadingPreview] = useState(false)
  const [showPreview, setShowPreview] = useState(false)

  const handlePreview = async () => {
    setIsLoadingPreview(true)
    const preview = await onPreview(fix.fix_id)
    setPreviewData(preview)
    setIsLoadingPreview(false)
    if (preview?.success) {
      setShowPreview(true)
    }
  }

  const handleApply = async () => {
    await onApply(fix.fix_id)
  }

  return (
    <Card className="border-l-4 border-l-blue-500">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            {fix.transformation_type.replace(/_/g, ' ')}
            {fix.ai_generated && (
              <Badge variant="secondary" className="text-xs">
                <Sparkles className="h-3 w-3 mr-1" />
                AI Suggested
              </Badge>
            )}
          </CardTitle>
          <div className="flex items-center gap-1">
            {fix.is_safe ? (
              <Badge variant="outline" className="text-green-700 border-green-300">
                <Shield className="h-3 w-3 mr-1" />
                Safe
              </Badge>
            ) : (
              <Badge variant="outline" className="text-yellow-700 border-yellow-300">
                <AlertTriangle className="h-3 w-3 mr-1" />
                Review
              </Badge>
            )}
          </div>
        </div>
        <CardDescription>{fix.explanation}</CardDescription>
      </CardHeader>

      <CardContent className="space-y-3">
        {/* Impact indicators */}
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-muted-foreground">Rows affected:</span>
            <span className="ml-2 font-medium">{fix.estimated_rows_affected.toLocaleString()}</span>
          </div>
          <div>
            <span className="text-muted-foreground">Confidence:</span>
            <span className="ml-2 font-medium">{Math.round(fix.confidence_score * 100)}%</span>
          </div>
        </div>

        {/* Data loss warning */}
        {fix.estimated_data_loss > 0 && (
          <Alert variant={fix.estimated_data_loss > 10 ? 'destructive' : 'default'}>
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>
              This fix may result in {fix.estimated_data_loss.toFixed(1)}% data loss
            </AlertDescription>
          </Alert>
        )}

        {/* Confidence bar */}
        <div className="space-y-1">
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>Confidence Score</span>
            <span>{Math.round(fix.confidence_score * 100)}%</span>
          </div>
          <Progress value={fix.confidence_score * 100} className="h-2" />
        </div>
      </CardContent>

      <CardFooter className="gap-2">
        <Dialog open={showPreview} onOpenChange={setShowPreview}>
          <DialogTrigger asChild>
            <Button
              variant="outline"
              size="sm"
              onClick={handlePreview}
              disabled={isLoadingPreview || isApplying}
            >
              {isLoadingPreview ? (
                <Loader2 className="h-4 w-4 mr-1 animate-spin" />
              ) : (
                <Eye className="h-4 w-4 mr-1" />
              )}
              Preview
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Fix Preview</DialogTitle>
              <DialogDescription>
                Preview how your data will look after applying this fix
              </DialogDescription>
            </DialogHeader>

            {previewData && (
              <div className="space-y-4">
                {/* Impact summary */}
                <div className="grid grid-cols-3 gap-4">
                  <Card>
                    <CardContent className="pt-4">
                      <div className="text-2xl font-bold">{previewData.affected_rows}</div>
                      <div className="text-sm text-muted-foreground">Rows affected</div>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="pt-4">
                      <div className="text-2xl font-bold">{previewData.affected_columns.length}</div>
                      <div className="text-sm text-muted-foreground">Columns affected</div>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="pt-4">
                      <div className="text-2xl font-bold">{previewData.estimated_data_loss.toFixed(1)}%</div>
                      <div className="text-sm text-muted-foreground">Data loss</div>
                    </CardContent>
                  </Card>
                </div>

                {/* Warnings */}
                {previewData.warnings && previewData.warnings.length > 0 && (
                  <Alert>
                    <AlertTriangle className="h-4 w-4" />
                    <AlertDescription>
                      <ul className="list-disc list-inside">
                        {previewData.warnings.map((warning, i) => (
                          <li key={i}>{warning}</li>
                        ))}
                      </ul>
                    </AlertDescription>
                  </Alert>
                )}

                {/* Before/After tables */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <h4 className="font-medium mb-2">Before</h4>
                    {previewData.preview_data_before && (
                      <div className="border rounded-md overflow-auto max-h-64">
                        <Table>
                          <TableHeader>
                            <TableRow>
                              {Object.keys(previewData.preview_data_before[0] || {}).slice(0, 5).map(key => (
                                <TableHead key={key}>{key}</TableHead>
                              ))}
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {previewData.preview_data_before.slice(0, 10).map((row, i) => (
                              <TableRow key={i}>
                                {Object.values(row).slice(0, 5).map((val, j) => (
                                  <TableCell key={j} className="font-mono text-xs">
                                    {String(val ?? 'null')}
                                  </TableCell>
                                ))}
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>
                    )}
                  </div>
                  <div>
                    <h4 className="font-medium mb-2">After</h4>
                    {previewData.preview_data_after && (
                      <div className="border rounded-md overflow-auto max-h-64">
                        <Table>
                          <TableHeader>
                            <TableRow>
                              {Object.keys(previewData.preview_data_after[0] || {}).slice(0, 5).map(key => (
                                <TableHead key={key}>{key}</TableHead>
                              ))}
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {previewData.preview_data_after.slice(0, 10).map((row, i) => (
                              <TableRow key={i}>
                                {Object.values(row).slice(0, 5).map((val, j) => (
                                  <TableCell key={j} className="font-mono text-xs">
                                    {String(val ?? 'null')}
                                  </TableCell>
                                ))}
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex justify-end">
                  <Button onClick={handleApply} disabled={isApplying}>
                    {isApplying ? (
                      <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                    ) : (
                      <CheckCircle2 className="h-4 w-4 mr-1" />
                    )}
                    Apply Fix
                  </Button>
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>

        <Button
          size="sm"
          onClick={handleApply}
          disabled={isApplying}
          className="flex-1"
        >
          {isApplying ? (
            <Loader2 className="h-4 w-4 mr-1 animate-spin" />
          ) : (
            <Play className="h-4 w-4 mr-1" />
          )}
          Apply Fix
        </Button>
      </CardFooter>
    </Card>
  )
}
