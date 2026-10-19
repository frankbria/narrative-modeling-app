'use client'

import { useState, type ChangeEvent, type FormEvent } from 'react'
import { useAsyncData } from '@/lib/hooks/useAsyncData'
import { getRefundWindow } from '@/lib/services/admin'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

interface FieldProps {
  label: string
  value: string
}

function Field(props: FieldProps) {
  const { label, value } = props
  return (
    <div>
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="text-lg font-semibold tabular-nums">{value}</dd>
    </div>
  )
}

/** Refund-window eligibility for any tenant (#746). Read-only: refunds stay in Stripe. */
export function RefundLookup() {
  const [draft, setDraft] = useState('')
  const [userId, setUserId] = useState('')
  const { data, loading, error } = useAsyncData(() => getRefundWindow(userId), [userId], {
    enabled: userId !== '',
  })

  const submit = (event: FormEvent) => {
    event.preventDefault()
    setUserId(draft.trim())
  }

  const edit = (event: ChangeEvent<HTMLInputElement>) => setDraft(event.target.value)

  return (
    <Card>
      <CardHeader>
        <CardTitle>Refund window</CardTitle>
        <CardDescription>Look up a tenant by user id</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <form onSubmit={submit} className="flex items-end gap-2">
          <div className="flex-1 space-y-1">
            <Label htmlFor="refund-user-id">User id</Label>
            <Input id="refund-user-id" value={draft} onChange={edit} />
          </div>
          <Button type="submit">Look up</Button>
        </form>
        {loading && <p className="text-muted-foreground">Loading…</p>}
        {error && <p className="text-destructive">{error}</p>}
        {data && (
          <dl className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <Field label="Refund eligibility" value={data.refund_eligible ? 'Eligible' : 'Not eligible'} />
            <Field label="Refund window ends" value={data.refund_window_ends_at ?? '—'} />
            <Field label="First paid" value={data.first_paid_at ?? '—'} />
          </dl>
        )}
      </CardContent>
    </Card>
  )
}
