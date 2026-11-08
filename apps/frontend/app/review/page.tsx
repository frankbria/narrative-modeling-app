'use client'

import { useRouter } from 'next/navigation'
import { useAsyncData } from '@/lib/hooks/useAsyncData'
import { listDatasets } from '@/lib/services/datasetList'
import { DatasetPicker } from '@/components/review/DatasetPicker'

const fetchDatasets = () => listDatasets()

export default function ReviewPage() {
  const router = useRouter()
  const datasets = useAsyncData(fetchDatasets, [])

  return (
    <div className="max-w-3xl mx-auto p-2 sm:p-6 space-y-4">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight text-foreground">Review Data</h1>
        <p className="text-muted-foreground mt-2">Pick a spreadsheet to look it over.</p>
      </div>
      <DatasetPicker
        datasets={datasets.data ?? []}
        loading={datasets.loading}
        error={datasets.error}
        onRetry={datasets.reload}
        onPick={(datasetId) => router.push(`/explore/${datasetId}`)}
      />
    </div>
  )
}
