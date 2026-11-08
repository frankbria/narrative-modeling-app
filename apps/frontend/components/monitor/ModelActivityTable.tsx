'use client'

import { useState } from 'react'
import Link from 'next/link'
import { Brain } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  MODEL_PAGE_SIZE,
  formatLatency,
  modelSubtitle,
  modelTitle,
  type MonitoredModel,
} from '@/lib/monitoring'

const lastUsedText = (iso?: string) => (iso ? new Date(iso).toLocaleString() : 'Never')

const STATUS = {
  true: { label: 'Receiving predictions', variant: 'default' },
  false: { label: 'No predictions yet', variant: 'secondary' },
} as const

function ModelRow({ model }: { model: MonitoredModel }) {
  const status = STATUS[String(model.predictions_24h > 0) as 'true' | 'false']
  return (
    <TableRow>
      <TableCell>
        <span className="font-medium">{modelTitle(model)}</span>
        <span className="block text-xs text-muted-foreground">{modelSubtitle(model)}</span>
      </TableCell>
      <TableCell>
        <Badge variant={status.variant}>{status.label}</Badge>
      </TableCell>
      <TableCell>{model.predictions_24h.toLocaleString()}</TableCell>
      <TableCell>{formatLatency(model.avg_latency_ms, model.predictions_24h)}</TableCell>
      <TableCell className="text-sm">{lastUsedText(model.last_used_at)}</TableCell>
      <TableCell>
        <Button asChild size="sm" variant="ghost">
          <Link href={`/monitor/${model.model_id}`}>View Details</Link>
        </Button>
      </TableCell>
    </TableRow>
  )
}

function EmptyState() {
  return (
    <div className="text-center py-8">
      <Brain className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
      <p className="text-muted-foreground">You have no trained models yet.</p>
    </div>
  )
}

function ShowMore({ remaining, onClick }: { remaining: number; onClick: VoidFunction }) {
  if (remaining <= 0) return null
  return (
    <div className="flex justify-center">
      <Button variant="outline" onClick={onClick}>
        Show more ({remaining} left)
      </Button>
    </div>
  )
}

function ModelTable({ models }: { models: MonitoredModel[] }) {
  const [shown, setShown] = useState(MODEL_PAGE_SIZE)
  const showMore = () => setShown((n) => n + MODEL_PAGE_SIZE)
  return (
    <div className="space-y-3">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Model</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Predictions (24h)</TableHead>
            <TableHead>Avg Latency</TableHead>
            <TableHead>Last Used</TableHead>
            <TableHead>Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {models.slice(0, shown).map((m) => (
            <ModelRow key={m.model_id} model={m} />
          ))}
        </TableBody>
      </Table>
      <ShowMore remaining={models.length - shown} onClick={showMore} />
    </div>
  )
}

/** The newest-active models first; the rest load a page at a time. */
export function ModelActivityTable({ models }: { models: MonitoredModel[] }) {
  if (models.length === 0) return <EmptyState />
  return <ModelTable models={models} />
}
