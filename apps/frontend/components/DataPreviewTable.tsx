'use client'

import React, { useState } from 'react'
import { useAsyncData } from '@/lib/hooks/useAsyncData'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { ChevronLeft, ChevronRight, Download } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

interface DataPreviewTableProps {
  datasetId: string
  onExport?: () => void
}

interface PreviewData {
  columns: string[]
  data: Record<string, unknown>[]
  total_rows: number
  offset: number
  rows: number
  /** A file too large to parse whole: `total_rows` is a line count, which can run a
   *  little high (a quoted newline counts twice) and never low. */
  approximate_total_rows?: boolean
  warning?: string
}

const ROWS_PER_PAGE = 50

/** What to show in place of the table, if there is no table to show. */
function unavailable(loading: boolean, error: string | null, preview: PreviewData | null | undefined) {
  if (loading) return { text: 'Loading preview data...', tone: 'text-muted-foreground' }
  if (error) return { text: `Error: ${error}`, tone: 'text-destructive' }
  if (!preview || preview.data.length === 0) return { text: 'No data available', tone: 'text-muted-foreground' }
  return null
}

/** A count for display, qualified when the server could only estimate it (#720). */
function counted(preview: PreviewData, count: number): string {
  if (preview.approximate_total_rows) return `about ${count}`
  return String(count)
}

function PreviewHeader(props: { preview: PreviewData; onExport?: VoidFunction }) {
  const { preview, onExport } = props
  const range = `${preview.offset + 1}-${preview.offset + preview.rows}`
  const shown = `Showing ${range} of ${counted(preview, preview.total_rows)} rows`
  return (
    <CardHeader>
      <div className="flex items-center justify-between">
        <div>
          <CardTitle>Data Preview</CardTitle>
          <CardDescription>{shown}</CardDescription>
          {preview.warning && <p className="mt-1 text-xs text-muted-foreground">{preview.warning}</p>}
        </div>
        {onExport && <ExportButton onExport={onExport} />}
      </div>
    </CardHeader>
  )
}

function ExportButton(props: { onExport: VoidFunction }) {
  const { onExport } = props
  return (
    <Button variant="outline" size="sm" onClick={onExport}>
      <Download className="mr-2 h-4 w-4" />
      Export
    </Button>
  )
}

interface PagerProps {
  preview: PreviewData
  page: number
  onPage(page: number): void
}

function PreviewPager(props: PagerProps) {
  const { preview, page, onPage } = props
  const pages = Math.ceil(preview.total_rows / ROWS_PER_PAGE)
  const position = `Page ${page + 1} of ${counted(preview, pages)}`
  const previous = () => onPage(page - 1)
  const next = () => onPage(page + 1)
  return (
    <div className="flex items-center justify-between mt-4">
      <p className="text-sm text-muted-foreground">{position}</p>
      <div className="flex gap-2">
        <Button variant="outline" size="sm" onClick={previous} disabled={page === 0}>
          <ChevronLeft className="h-4 w-4" />
          Previous
        </Button>
        <Button variant="outline" size="sm" onClick={next} disabled={page >= pages - 1}>
          Next
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}

function formatCellValue(value: unknown): string {
  if (value === null || value === undefined) {
    return '<null>'
  }
  if (typeof value === 'object') {
    return JSON.stringify(value)
  }
  return String(value)
}

function Unavailable(props: { status: { text: string; tone: string } }) {
  const { status } = props
  return (
    <Card>
      <CardContent className="flex items-center justify-center h-64">
        <p className={status.tone}>{status.text}</p>
      </CardContent>
    </Card>
  )
}

interface PreviewCardProps extends PagerProps {
  onExport?: VoidFunction
}

function PreviewCard(props: PreviewCardProps) {
  const { preview, page, onPage, onExport } = props
  return (
    <Card>
      <PreviewHeader preview={preview} onExport={onExport} />
      <CardContent>
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-12">#</TableHead>
                {preview.columns.map((column) => (
                  <TableHead key={column} className="min-w-[100px]">
                    {column}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {preview.data.map((row, index) => (
                <TableRow key={index}>
                  <TableCell className="font-medium text-muted-foreground">
                    {preview.offset + index + 1}
                  </TableCell>
                  {preview.columns.map((column) => (
                    <TableCell key={column} className="max-w-xs truncate" title={formatCellValue(row[column])}>
                      {formatCellValue(row[column])}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
        <PreviewPager preview={preview} page={page} onPage={onPage} />
      </CardContent>
    </Card>
  )
}

export function DataPreviewTable({ datasetId, onExport }: DataPreviewTableProps) {
  const [currentPage, setCurrentPage] = useState(0)
  const rowsPerPage = ROWS_PER_PAGE

  const validId = !!datasetId && datasetId !== 'undefined'

  const {
    data: previewData,
    loading,
    error: fetchError,
  } = useAsyncData<PreviewData>(async () => {
    const response = await fetch(
      `/api/data/${datasetId}/preview?rows=${rowsPerPage}&offset=${currentPage * rowsPerPage}`,
      {
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
      },
    )
    if (!response.ok) {
      throw new Error('Failed to fetch preview data')
    }
    return response.json()
  }, [datasetId, currentPage], { enabled: validId })

  // The old effect set this synchronously before returning early; it is a plain
  // property of the props now. AbortController is gone because the hook already
  // discards a superseded request's result.
  const error = validId ? fetchError : 'Invalid dataset ID'


  const status = unavailable(loading, error, previewData)
  if (status) return <Unavailable status={status} />
  // unavailable() answers for a missing preview, so from here there is one.
  return (
    <PreviewCard
      preview={previewData as PreviewData}
      page={currentPage}
      onPage={setCurrentPage}
      onExport={onExport}
    />
  )
}
