'use client'

import React from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from '@/components/ui/table'
import { Download } from 'lucide-react'
import {
  getMethodName,
  formatExecutionTime,
  type MethodComparisonResponse
} from '@/lib/services/featureSelection'

/**
 * Props for {@link MethodComparisonView}.
 */
export interface MethodComparisonViewProps {
  /** Full multi-method comparison response to render. */
  comparison: MethodComparisonResponse
  /** Optional callback fired after a successful CSV export (mainly for testing). */
  onExportCSV?: () => void
}

/**
 * Escape a single CSV field using RFC 4180-style quoting.
 * Fields containing a comma, double-quote, or line break (LF or CR) are wrapped
 * in double-quotes with embedded quotes doubled. Mirrors the pattern in
 * SelectedFeatureSet.tsx.
 */
function escapeCsvField(field: string): string {
  if (
    field.includes(',') ||
    field.includes('"') ||
    field.includes('\n') ||
    field.includes('\r')
  ) {
    return `"${field.replace(/"/g, '""')}"`
  }
  return field
}

/**
 * MethodComparisonView
 *
 * Renders the full result of a multi-method feature-selection comparison:
 * consensus features, each method's selected features and top scores side-by-side,
 * a pairwise overlap matrix, recommendations, and a CSV export of the comparison.
 */
export function MethodComparisonView({ comparison, onExportCSV }: MethodComparisonViewProps) {
  const { results, consensus_features, overlap_matrix, recommendations, dataset_id } = comparison

  const methodNames = results.map((r) => r.method)

  const downloadCSV = () => {
    const headers = ['Method', 'Feature', 'Score', 'Rank', 'Selected']
    const rows = results.flatMap((methodResult) =>
      methodResult.top_features.map((feature) => [
        escapeCsvField(getMethodName(methodResult.method)),
        escapeCsvField(feature.feature_name),
        feature.score.toFixed(6),
        feature.rank.toString(),
        feature.selected ? 'Yes' : 'No'
      ])
    )

    const csv = [
      headers.map(escapeCsvField).join(','),
      ...rows.map((r) => r.join(','))
    ].join('\n')

    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `method-comparison-${dataset_id}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)

    onExportCSV?.()
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div>
            <CardTitle>Method Comparison</CardTitle>
            <CardDescription>
              Comparing {results.length} feature-selection methods side-by-side
            </CardDescription>
          </div>
          <Button onClick={downloadCSV} variant="outline" size="sm">
            <Download className="h-4 w-4 mr-2" />
            Export CSV
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Recommendations */}
        {recommendations && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <h4 className="text-sm font-semibold text-blue-900 mb-2">Recommendation</h4>
            <p className="text-sm text-blue-800">{recommendations}</p>
          </div>
        )}

        {/* Consensus Features */}
        <div>
          <h4 className="text-sm font-semibold text-gray-900 mb-2">
            Consensus Features ({consensus_features.length})
          </h4>
          {consensus_features.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {consensus_features.map((feature) => (
                <Badge key={feature} variant="default" className="font-mono">
                  {feature}
                </Badge>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-500">
              No features were selected by all methods.
            </p>
          )}
        </div>

        {/* Side-by-side method results */}
        <div>
          <h4 className="text-sm font-semibold text-gray-900 mb-3">Methods</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {results.map((methodResult) => (
              <div
                key={methodResult.method}
                className="border rounded-lg p-4 space-y-3"
                data-testid={`method-card-${methodResult.method}`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold">{getMethodName(methodResult.method)}</span>
                  <span className="text-xs text-gray-500">
                    {formatExecutionTime(methodResult.execution_time_ms)}
                  </span>
                </div>
                <p className="text-xs text-gray-600">
                  {methodResult.selected_features.length} features selected
                </p>
                <div className="border rounded-md overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Feature</TableHead>
                        <TableHead className="text-right">Score</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {methodResult.top_features.map((feature) => (
                        <TableRow key={feature.feature_name}>
                          <TableCell className="font-mono text-xs">
                            {feature.feature_name}
                          </TableCell>
                          <TableCell className="text-right">
                            <Badge
                              variant={feature.selected ? 'default' : 'outline'}
                            >
                              {feature.score.toFixed(4)}
                            </Badge>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Overlap Matrix */}
        {methodNames.length > 0 && (
          <div>
            <h4 className="text-sm font-semibold text-gray-900 mb-3">
              Feature Overlap Matrix
            </h4>
            <p className="text-xs text-gray-500 mb-2">
              Number of selected features shared between each pair of methods.
            </p>
            <div className="border rounded-lg overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Method</TableHead>
                    {methodNames.map((name) => (
                      <TableHead key={name} className="text-right">
                        {getMethodName(name)}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {methodNames.map((rowMethod) => (
                    <TableRow key={rowMethod}>
                      <TableCell className="font-medium">
                        {getMethodName(rowMethod)}
                      </TableCell>
                      {methodNames.map((colMethod) => (
                        <TableCell key={colMethod} className="text-right">
                          {overlap_matrix?.[rowMethod]?.[colMethod] ?? '—'}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
