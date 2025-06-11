'use client'

import React from 'react'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { AlertCircle, CheckCircle, Database, Hash, Type, Calendar, Mail, Phone, Link, DollarSign, Percent } from 'lucide-react'

interface ColumnSchema {
  name: string
  data_type: string
  nullable: boolean
  unique: boolean
  cardinality: number
  null_count: number
  null_percentage: number
  sample_values?: any[]
}

interface SchemaViewerProps {
  schema: {
    columns: ColumnSchema[]
    row_count: number
    column_count: number
    inference_confidence?: number
  }
}

const dataTypeIcons: Record<string, React.ReactNode> = {
  integer: <Hash className="h-4 w-4" />,
  float: <Hash className="h-4 w-4" />,
  string: <Type className="h-4 w-4" />,
  text: <Type className="h-4 w-4" />,
  boolean: <CheckCircle className="h-4 w-4" />,
  date: <Calendar className="h-4 w-4" />,
  datetime: <Calendar className="h-4 w-4" />,
  email: <Mail className="h-4 w-4" />,
  phone: <Phone className="h-4 w-4" />,
  url: <Link className="h-4 w-4" />,
  currency: <DollarSign className="h-4 w-4" />,
  percentage: <Percent className="h-4 w-4" />,
  categorical: <Database className="h-4 w-4" />,
}

const dataTypeColors: Record<string, string> = {
  integer: 'bg-blue-500',
  float: 'bg-blue-600',
  string: 'bg-green-500',
  text: 'bg-green-600',
  boolean: 'bg-purple-500',
  date: 'bg-orange-500',
  datetime: 'bg-orange-600',
  email: 'bg-pink-500',
  phone: 'bg-pink-600',
  url: 'bg-indigo-500',
  currency: 'bg-yellow-500',
  percentage: 'bg-yellow-600',
  categorical: 'bg-gray-500',
  unknown: 'bg-gray-400',
}

export function SchemaViewer({ schema }: SchemaViewerProps) {
  const getDataTypeIcon = (dataType: string) => {
    return dataTypeIcons[dataType] || <Database className="h-4 w-4" />
  }

  const getDataTypeColor = (dataType: string) => {
    return dataTypeColors[dataType] || dataTypeColors.unknown
  }

  const formatSampleValues = (values?: any[]) => {
    if (!values || values.length === 0) return 'N/A'
    return values.slice(0, 3).map(v => 
      v === null ? '<null>' : String(v)
    ).join(', ') + (values.length > 3 ? '...' : '')
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Schema Information</CardTitle>
        <CardDescription>
          {schema.column_count} columns • {schema.row_count.toLocaleString()} rows
          {schema.inference_confidence && (
            <span className="ml-2">
              • Confidence: {(schema.inference_confidence * 100).toFixed(1)}%
            </span>
          )}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Column Name</TableHead>
                <TableHead>Data Type</TableHead>
                <TableHead>Nullable</TableHead>
                <TableHead>Unique</TableHead>
                <TableHead>Cardinality</TableHead>
                <TableHead>Missing %</TableHead>
                <TableHead>Sample Values</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {schema.columns.map((column) => (
                <TableRow key={column.name}>
                  <TableCell className="font-medium">{column.name}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <div className={`p-1 rounded ${getDataTypeColor(column.data_type)} text-white`}>
                        {getDataTypeIcon(column.data_type)}
                      </div>
                      <span className="text-sm">{column.data_type}</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    {column.nullable ? (
                      <Badge variant="secondary">Yes</Badge>
                    ) : (
                      <Badge variant="outline">No</Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    {column.unique ? (
                      <Badge variant="default">Yes</Badge>
                    ) : (
                      <Badge variant="outline">No</Badge>
                    )}
                  </TableCell>
                  <TableCell>{column.cardinality.toLocaleString()}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      {column.null_percentage > 0 && (
                        <AlertCircle className="h-3 w-3 text-yellow-500" />
                      )}
                      <span className={column.null_percentage > 10 ? 'text-yellow-600 font-medium' : ''}>
                        {column.null_percentage.toFixed(1)}%
                      </span>
                    </div>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground max-w-xs truncate" title={formatSampleValues(column.sample_values)}>
                    {formatSampleValues(column.sample_values)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  )
}