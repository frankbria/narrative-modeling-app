import type { ReactNode } from 'react'
import Link from 'next/link'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { DatasetListItem } from '@/lib/services/datasetList'

type PickerProps = {
  datasets: DatasetListItem[]
  loading: boolean
  error: string | null
  onRetry: VoidFunction
  onPick(datasetId: string): void
}

type PickerView = 'loading' | 'error' | 'empty' | 'list'

const pickerView = ({ loading, error, datasets }: PickerProps): PickerView =>
  loading ? 'loading' : error ? 'error' : datasets.length ? 'list' : 'empty'

const addedOn = (iso: string): string => new Date(iso).toLocaleDateString()

const VIEWS: Record<PickerView, (props: PickerProps) => ReactNode> = {
  loading: () => (
    <p className="flex items-center gap-2 text-muted-foreground" role="status">
      <Loader2 className="h-4 w-4 animate-spin text-primary" /> Loading your datasets...
    </p>
  ),
  error: ({ error, onRetry }) => (
    <div role="alert" className="space-y-3">
      <p className="text-destructive">{error}</p>
      <Button variant="outline" onClick={onRetry}>Try again</Button>
    </div>
  ),
  empty: () => (
    <div className="space-y-3">
      <p className="text-muted-foreground">You have not loaded a spreadsheet yet.</p>
      <Button asChild><Link href="/upload">Load Data</Link></Button>
    </div>
  ),
  list: ({ datasets, onPick }) => (
    <ul className="space-y-2">
      {datasets.map((dataset) => (
        <li key={dataset.dataset_id}>
          <button
            type="button"
            onClick={() => onPick(dataset.dataset_id)}
            className="w-full rounded-lg border border-border p-3 text-left transition-all hover:bg-muted focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
          >
            <span className="block font-medium text-foreground">{dataset.filename}</span>
            <span className="block text-sm text-muted-foreground">
              {dataset.num_rows} rows × {dataset.num_columns} columns · added {addedOn(dataset.created_at)}
            </span>
          </button>
        </li>
      ))}
    </ul>
  ),
}

export function DatasetPicker(props: PickerProps) {
  return <>{VIEWS[pickerView(props)](props)}</>
}
