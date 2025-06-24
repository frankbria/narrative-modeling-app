'use client'

import React, { useState, useEffect } from 'react'
import {
  Table,
  TableBody,
  TableCaption,
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
  data: Record<string, any>[]
  total_rows: number
  offset: number
  rows: number
}

export function DataPreviewTable({ datasetId, onExport }: DataPreviewTableProps) {
  const [previewData, setPreviewData] = useState<PreviewData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [currentPage, setCurrentPage] = useState(0)
  const rowsPerPage = 50

  useEffect(() => {
    if (datasetId && datasetId !== 'undefined') {
      fetchPreviewData()
    } else {
      setError('Invalid dataset ID')
      setLoading(false)
    }
  }, [datasetId, currentPage])

  const fetchPreviewData = async () => {
    if (!datasetId || datasetId === 'undefined') {
      setError('Invalid dataset ID')
      setLoading(false)
      return
    }
    
    try {
      setLoading(true)
      const response = await fetch(
        `/api/data/${datasetId}/preview?rows=${rowsPerPage}&offset=${currentPage * rowsPerPage}`,
        {
          headers: {
            'Content-Type': 'application/json',
          },
          credentials: 'include',
        }
      )

      if (!response.ok) {
        throw new Error('Failed to fetch preview data')
      }

      const data = await response.json()
      setPreviewData(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  const totalPages = previewData ? Math.ceil(previewData.total_rows / rowsPerPage) : 0

  const formatCellValue = (value: any): string => {
    if (value === null || value === undefined) {
      return '<null>'
    }
    if (typeof value === 'object') {
      return JSON.stringify(value)
    }
    return String(value)
  }

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center h-64">
          <p className="text-muted-foreground">Loading preview data...</p>
        </CardContent>
      </Card>
    )
  }

  if (error) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center h-64">
          <p className="text-destructive">Error: {error}</p>
        </CardContent>
      </Card>
    )
  }

  if (!previewData || previewData.data.length === 0) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center h-64">
          <p className="text-muted-foreground">No data available</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Data Preview</CardTitle>
            <CardDescription>
              Showing {previewData.offset + 1}-{previewData.offset + previewData.rows} of {previewData.total_rows} rows
            </CardDescription>
          </div>
          {onExport && (
            <Button variant="outline" size="sm" onClick={onExport}>
              <Download className="mr-2 h-4 w-4" />
              Export
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-12">#</TableHead>
                {previewData.columns.map((column) => (
                  <TableHead key={column} className="min-w-[100px]">
                    {column}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {previewData.data.map((row, index) => (
                <TableRow key={index}>
                  <TableCell className="font-medium text-muted-foreground">
                    {previewData.offset + index + 1}
                  </TableCell>
                  {previewData.columns.map((column) => (
                    <TableCell key={column} className="max-w-xs truncate" title={formatCellValue(row[column])}>
                      {formatCellValue(row[column])}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
        
        <div className="flex items-center justify-between mt-4">
          <p className="text-sm text-muted-foreground">
            Page {currentPage + 1} of {totalPages}
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage(currentPage - 1)}
              disabled={currentPage === 0}
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage(currentPage + 1)}
              disabled={currentPage >= totalPages - 1}
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}