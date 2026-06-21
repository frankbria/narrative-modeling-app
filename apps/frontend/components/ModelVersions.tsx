'use client'

/**
 * Model version history (issue #78).
 *
 * Renders a model's version family (all models trained on the same dataset under
 * the same name) as a browser table with promote-to-production / rollback
 * actions, per-row lineage (dataset version + features), and an optional
 * side-by-side comparison of 2+ selected versions reusing {@link ModelComparisonTable}.
 */

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { getAuthToken } from '@/lib/auth-helpers'
import { ModelService } from '@/lib/services/model'
import type {
  ModelVersionEntry,
  ModelVersionListResponse,
  ModelEvaluationSummary,
} from '@/lib/types/evaluation'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ModelComparisonTable } from '@/components/ModelComparisonTable'
import { Loader2, GitBranch, CheckCircle2, AlertCircle } from 'lucide-react'

interface ModelVersionsProps {
  /** Any model in the family to display versions for. */
  modelId: string
}

export function ModelVersions({ modelId }: ModelVersionsProps) {
  const [data, setData] = useState<ModelVersionListResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [promoting, setPromoting] = useState<string | null>(null)
  const [selected, setSelected] = useState<string[]>([])
  const [comparison, setComparison] = useState<ModelEvaluationSummary[] | null>(null)

  const load = useCallback(async () => {
    try {
      setIsLoading(true)
      setError(null)
      const token = await getAuthToken()
      setData(await ModelService.getModelVersions(modelId, token || ''))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load versions')
    } finally {
      setIsLoading(false)
    }
  }, [modelId])

  useEffect(() => {
    // Reset per-model selection/comparison when navigating between models.
    setSelected([])
    setComparison(null)
    load()
  }, [load])

  const handlePromote = async (id: string) => {
    try {
      setPromoting(id)
      setError(null)
      const token = await getAuthToken()
      await ModelService.promoteModelVersion(id, token || '')
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to promote version')
    } finally {
      setPromoting(null)
    }
  }

  // The /ml/compare backend accepts at most 5 models, so cap selection there.
  const MAX_COMPARE = 5

  const toggleSelect = (id: string) => {
    setComparison(null)
    setSelected((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id)
      if (prev.length >= MAX_COMPARE) return prev // ignore beyond the limit
      return [...prev, id]
    })
  }

  const handleCompare = async () => {
    try {
      setError(null)
      const token = await getAuthToken()
      const result = await ModelService.compareModels(selected, token || '')
      setComparison(result.models)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to compare versions')
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12" role="status">
        <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
      </div>
    )
  }

  if (error && !data) {
    return (
      <div className="flex items-center gap-2 text-red-600 py-6">
        <AlertCircle className="h-5 w-5" /> {error}
      </div>
    )
  }

  if (!data || data.versions.length === 0) {
    return <p className="text-gray-500 py-6">No versions found for this model.</p>
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <GitBranch className="h-5 w-5" />
            Version History
          </CardTitle>
          <CardDescription>
            {data.total} version{data.total === 1 ? '' : 's'} of &ldquo;{data.name}&rdquo;
            {' '}trained on this dataset. Select 2–5 to compare; promote any version to
            production (promoting an older version rolls back).
          </CardDescription>
        </CardHeader>
        <CardContent>
          {error && (
            <div className="flex items-center gap-2 text-red-600 mb-3 text-sm">
              <AlertCircle className="h-4 w-4" /> {error}
            </div>
          )}
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="versions-table">
              <thead>
                <tr className="border-b text-left text-gray-500">
                  <th className="py-2 pr-2"></th>
                  <th className="py-2 pr-2">Version</th>
                  <th className="py-2 pr-2">Status</th>
                  <th className="py-2 pr-2">Algorithm</th>
                  <th className="py-2 pr-2">CV</th>
                  <th className="py-2 pr-2">Test</th>
                  <th className="py-2 pr-2">Dataset version</th>
                  <th className="py-2 pr-2">Features</th>
                  <th className="py-2 pr-2">Created</th>
                  <th className="py-2 pr-2"></th>
                </tr>
              </thead>
              <tbody>
                {data.versions.map((v: ModelVersionEntry) => (
                  <tr key={v.model_id} className="border-b last:border-0">
                    <td className="py-2 pr-2">
                      <input
                        type="checkbox"
                        aria-label={`Select version ${v.version_number}`}
                        checked={selected.includes(v.model_id)}
                        disabled={
                          !selected.includes(v.model_id) &&
                          selected.length >= MAX_COMPARE
                        }
                        onChange={() => toggleSelect(v.model_id)}
                      />
                    </td>
                    <td className="py-2 pr-2 font-medium">
                      <Link href={`/model/${v.model_id}`} className="hover:underline">
                        v{v.version_number}
                      </Link>
                    </td>
                    <td className="py-2 pr-2">
                      {v.is_production ? (
                        <Badge className="bg-green-600 hover:bg-green-600">
                          <CheckCircle2 className="h-3 w-3 mr-1" /> Production
                        </Badge>
                      ) : v.is_active ? (
                        <Badge variant="secondary">Active</Badge>
                      ) : (
                        <Badge variant="outline">Inactive</Badge>
                      )}
                    </td>
                    <td className="py-2 pr-2">{v.algorithm}</td>
                    <td className="py-2 pr-2">{v.cv_score?.toFixed(3) ?? '—'}</td>
                    <td className="py-2 pr-2">{v.test_score?.toFixed(3) ?? '—'}</td>
                    <td className="py-2 pr-2">{v.dataset_version_id ?? '—'}</td>
                    <td className="py-2 pr-2">{v.feature_names.length}</td>
                    <td className="py-2 pr-2 whitespace-nowrap">
                      {v.created_at ? new Date(v.created_at).toLocaleDateString() : '—'}
                    </td>
                    <td className="py-2 pr-2">
                      {!v.is_production && (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={promoting === v.model_id}
                          onClick={() => handlePromote(v.model_id)}
                          data-testid={`promote-${v.model_id}`}
                        >
                          {promoting === v.model_id ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            'Promote'
                          )}
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {selected.length >= 2 && (
            <div className="mt-4">
              <Button size="sm" onClick={handleCompare} data-testid="compare-versions">
                Compare {selected.length} versions
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {comparison && comparison.length >= 2 && (
        <Card>
          <CardHeader>
            <CardTitle>Side-by-side comparison</CardTitle>
          </CardHeader>
          <CardContent>
            <ModelComparisonTable models={comparison} />
          </CardContent>
        </Card>
      )}
    </div>
  )
}
