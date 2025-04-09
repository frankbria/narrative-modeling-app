import React from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

interface StatsCardProps {
  stats: Array<{
    field: string
    type: 'numeric' | 'date' | 'text'
    count: number
    missing: number
    unique: number
    min?: number | string | null
    max?: number | string | null
    mean?: number | null
    median?: number | null
    mode?: number[] | null
    std?: number | null
    minLength?: number
    maxLength?: number
    avgLength?: number
  }>
}

export function StatsCard({ stats }: StatsCardProps) {
  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>Descriptive Statistics</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Field</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Count</TableHead>
                <TableHead>Missing</TableHead>
                <TableHead>Unique</TableHead>
                <TableHead>Min</TableHead>
                <TableHead>Max</TableHead>
                <TableHead>Mean</TableHead>
                <TableHead>Median</TableHead>
                <TableHead>Mode</TableHead>
                <TableHead>Std Dev</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {stats.map((stat, index) => (
                <TableRow key={index}>
                  <TableCell className="font-medium">{stat.field}</TableCell>
                  <TableCell className="capitalize">{stat.type}</TableCell>
                  <TableCell>{stat.count}</TableCell>
                  <TableCell>{stat.missing}</TableCell>
                  <TableCell>{stat.unique}</TableCell>
                  <TableCell>
                    {stat.type === 'numeric' && typeof stat.min === 'number'
                      ? stat.min.toFixed(2)
                      : stat.type === 'date' && stat.min
                      ? stat.min
                      : stat.type === 'text' && stat.minLength !== undefined
                      ? `${stat.minLength} chars`
                      : '-'}
                  </TableCell>
                  <TableCell>
                    {stat.type === 'numeric' && typeof stat.max === 'number'
                      ? stat.max.toFixed(2)
                      : stat.type === 'date' && stat.max
                      ? stat.max
                      : stat.type === 'text' && stat.maxLength !== undefined
                      ? `${stat.maxLength} chars`
                      : '-'}
                  </TableCell>
                  <TableCell>
                    {stat.type === 'numeric' && stat.mean !== null && stat.mean !== undefined
                      ? stat.mean.toFixed(2)
                      : stat.type === 'text' && stat.avgLength !== undefined
                      ? `${stat.avgLength.toFixed(1)} chars`
                      : '-'}
                  </TableCell>
                  <TableCell>
                    {stat.type === 'numeric' && stat.median !== null && stat.median !== undefined
                      ? stat.median.toFixed(2)
                      : '-'}
                  </TableCell>
                  <TableCell>
                    {stat.type === 'numeric' && stat.mode && stat.mode.length > 0
                      ? stat.mode.map(m => m.toFixed(2)).join(', ')
                      : '-'}
                  </TableCell>
                  <TableCell>
                    {stat.type === 'numeric' && stat.std !== null && stat.std !== undefined
                      ? stat.std.toFixed(2)
                      : '-'}
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