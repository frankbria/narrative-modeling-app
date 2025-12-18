'use client'

import React, { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import {
  ChevronDown,
  Sparkles,
  Database,
  Copy,
  TrendingUp,
  Type,
  Calendar,
  Hash,
} from 'lucide-react'
import { DataIssue, FixPreviewResponse, getIssueTypeLabel } from '@/lib/services/data-issues'
import { IssueSeverityBadge } from './IssueSeverityBadge'
import { FixSuggestionCard } from './FixSuggestionCard'

interface IssueListProps {
  issues: DataIssue[]
  selectedIssues: Set<string>
  onSelectIssue: (issueId: string) => void
  onDeselectIssue: (issueId: string) => void
  onPreviewFix: (issueId: string, fixId?: string) => Promise<FixPreviewResponse | null>
  onApplyFix: (issueId: string, fixId?: string) => Promise<void>
  isApplying?: boolean
}

const issueTypeIcons: Record<string, React.ReactNode> = {
  missing_values: <Database className="h-4 w-4" />,
  duplicates: <Copy className="h-4 w-4" />,
  outliers: <TrendingUp className="h-4 w-4" />,
  inconsistent_casing: <Type className="h-4 w-4" />,
  whitespace_issues: <Type className="h-4 w-4" />,
  date_format_issues: <Calendar className="h-4 w-4" />,
  type_mismatch: <Hash className="h-4 w-4" />,
}

function getIssueIcon(issueType: string) {
  return issueTypeIcons[issueType] || <Database className="h-4 w-4" />
}

export function IssueList({
  issues,
  selectedIssues,
  onSelectIssue,
  onDeselectIssue,
  onPreviewFix,
  onApplyFix,
  isApplying = false
}: IssueListProps) {
  const [expandedIssue, setExpandedIssue] = useState<string | null>(null)

  // Group issues by severity for display
  const groupedIssues = React.useMemo(() => {
    const groups: Record<string, DataIssue[]> = {
      critical: [],
      high: [],
      medium: [],
      low: []
    }

    issues.forEach(issue => {
      if (groups[issue.severity]) {
        groups[issue.severity].push(issue)
      } else {
        groups.low.push(issue)
      }
    })

    return groups
  }, [issues])

  const handleCheckboxChange = (issueId: string, checked: boolean) => {
    if (checked) {
      onSelectIssue(issueId)
    } else {
      onDeselectIssue(issueId)
    }
  }

  const handlePreview = async (issueId: string, fixId?: string) => {
    return onPreviewFix(issueId, fixId)
  }

  const handleApply = async (issueId: string, fixId?: string) => {
    await onApplyFix(issueId, fixId)
  }

  if (issues.length === 0) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-12">
          <div className="text-4xl mb-4">✨</div>
          <h3 className="text-lg font-medium">No Issues Found</h3>
          <p className="text-sm text-muted-foreground">
            Your data looks good! No quality issues were detected.
          </p>
        </CardContent>
      </Card>
    )
  }

  return (
    <ScrollArea className="h-[600px] pr-4">
      <div className="space-y-4">
        {['critical', 'high', 'medium', 'low'].map(severity => {
          const sevIssues = groupedIssues[severity]
          if (sevIssues.length === 0) return null

          return (
            <div key={severity} className="space-y-2">
              <div className="flex items-center gap-2 sticky top-0 bg-background py-2 z-10">
                <IssueSeverityBadge severity={severity} />
                <span className="text-sm text-muted-foreground">
                  ({sevIssues.length} {sevIssues.length === 1 ? 'issue' : 'issues'})
                </span>
              </div>

              <Accordion type="single" collapsible value={expandedIssue || undefined}>
                {sevIssues.map(issue => (
                  <AccordionItem
                    key={issue.issue_id}
                    value={issue.issue_id}
                    className="border rounded-lg mb-2"
                  >
                    <AccordionTrigger
                      className="hover:no-underline px-4"
                      onClick={() => setExpandedIssue(
                        expandedIssue === issue.issue_id ? null : issue.issue_id
                      )}
                    >
                      <div className="flex items-center gap-3 flex-1 text-left">
                        <Checkbox
                          checked={selectedIssues.has(issue.issue_id)}
                          onCheckedChange={(checked) =>
                            handleCheckboxChange(issue.issue_id, checked as boolean)
                          }
                          onClick={(e) => e.stopPropagation()}
                        />

                        <div className="flex items-center gap-2">
                          {getIssueIcon(issue.issue_type)}
                          <span className="font-medium">
                            {getIssueTypeLabel(issue.issue_type)}
                          </span>
                        </div>

                        {issue.affected_column && (
                          <Badge variant="outline" className="text-xs">
                            {issue.affected_column}
                          </Badge>
                        )}

                        {issue.ai_generated && (
                          <Badge variant="secondary" className="text-xs">
                            <Sparkles className="h-3 w-3 mr-1" />
                            AI
                          </Badge>
                        )}

                        <span className="text-sm text-muted-foreground ml-auto mr-4">
                          {issue.affected_percentage.toFixed(1)}% affected
                        </span>
                      </div>
                    </AccordionTrigger>

                    <AccordionContent className="px-4 pb-4">
                      <div className="space-y-4">
                        {/* Issue description */}
                        <div>
                          <h4 className="text-sm font-medium mb-1">Description</h4>
                          <p className="text-sm text-muted-foreground">
                            {issue.description}
                          </p>
                        </div>

                        {/* Impact */}
                        {issue.impact && (
                          <div>
                            <h4 className="text-sm font-medium mb-1">Impact</h4>
                            <p className="text-sm text-muted-foreground">
                              {issue.impact}
                            </p>
                          </div>
                        )}

                        {/* AI explanation */}
                        {issue.ai_explanation && (
                          <div className="p-3 bg-blue-50 dark:bg-blue-950 rounded-md">
                            <div className="flex items-center gap-2 text-sm font-medium text-blue-700 dark:text-blue-300 mb-1">
                              <Sparkles className="h-4 w-4" />
                              AI Analysis
                            </div>
                            <p className="text-sm text-blue-600 dark:text-blue-400">
                              {issue.ai_explanation}
                            </p>
                          </div>
                        )}

                        {/* Example values */}
                        {issue.example_values && issue.example_values.length > 0 && (
                          <div>
                            <h4 className="text-sm font-medium mb-1">Example Values</h4>
                            <div className="flex flex-wrap gap-2">
                              {issue.example_values.slice(0, 5).map((val, i) => (
                                <Badge key={i} variant="outline" className="font-mono text-xs">
                                  {String(val ?? 'null')}
                                </Badge>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Stats */}
                        <div className="grid grid-cols-2 gap-4 text-sm">
                          <div>
                            <span className="text-muted-foreground">Affected Rows:</span>
                            <span className="ml-2 font-medium">{issue.affected_rows.toLocaleString()}</span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Percentage:</span>
                            <span className="ml-2 font-medium">{issue.affected_percentage.toFixed(1)}%</span>
                          </div>
                        </div>

                        {/* Suggested fixes */}
                        {issue.suggested_fixes.length > 0 && (
                          <div>
                            <h4 className="text-sm font-medium mb-2">
                              Suggested Fixes ({issue.suggested_fixes.length})
                            </h4>
                            <div className="space-y-3">
                              {issue.suggested_fixes.map(fix => (
                                <FixSuggestionCard
                                  key={fix.fix_id}
                                  issue={issue}
                                  fix={fix}
                                  onPreview={(fixId) => handlePreview(issue.issue_id, fixId)}
                                  onApply={(fixId) => handleApply(issue.issue_id, fixId)}
                                  isApplying={isApplying}
                                />
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                ))}
              </Accordion>
            </div>
          )
        })}
      </div>
    </ScrollArea>
  )
}
