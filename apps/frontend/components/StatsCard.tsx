import React, { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { HistogramModal } from './HistogramModal'

interface StatsCardProps {
  stats: {
    field_name: string
    field_type: string
    count: number
    missing_values: number
    unique_values: number
    numeric_stats?: {
      min: number
      max: number
      mean: number
      median: number
      mode: number
      std_dev: number
      histogram?: {
        bins: number[]
        counts: number[]
      }
    }
    categorical_stats?: {
      top_values: Array<{
        value: string
        count: number
      }>
    }
    date_stats?: {
      min_date: string
      max_date: string
    }
    text_stats?: {
      avg_length: number
      sample_values: string[]
    }
  }
}

export function StatsCard({ stats }: StatsCardProps) {
  const [isHistogramOpen, setIsHistogramOpen] = useState(false)

  const renderNumericStats = () => {
    if (!stats.numeric_stats) return null

    return (
      <>
        <tr>
          <td className="py-2 font-medium">Min</td>
          <td className="py-2">{stats.numeric_stats.min.toFixed(2)}</td>
        </tr>
        <tr>
          <td className="py-2 font-medium">Max</td>
          <td className="py-2">{stats.numeric_stats.max.toFixed(2)}</td>
        </tr>
        <tr>
          <td className="py-2 font-medium">Mean</td>
          <td className="py-2">{stats.numeric_stats.mean.toFixed(2)}</td>
        </tr>
        <tr>
          <td className="py-2 font-medium">Median</td>
          <td className="py-2">{stats.numeric_stats.median.toFixed(2)}</td>
        </tr>
        <tr>
          <td className="py-2 font-medium">Mode</td>
          <td className="py-2">{stats.numeric_stats.mode.toFixed(2)}</td>
        </tr>
        <tr>
          <td className="py-2 font-medium">Standard Deviation</td>
          <td className="py-2">{stats.numeric_stats.std_dev.toFixed(2)}</td>
        </tr>
        {stats.numeric_stats.histogram && (
          <tr>
            <td className="py-2 font-medium">Histogram</td>
            <td className="py-2">
              <button
                onClick={() => setIsHistogramOpen(true)}
                className="px-3 py-1 bg-blue-500 text-white rounded-md hover:bg-blue-600 transition-colors"
              >
                View Histogram
              </button>
            </td>
          </tr>
        )}
      </>
    )
  }

  const renderCategoricalStats = () => {
    if (!stats.categorical_stats) return null

    return (
      <>
        <tr>
          <td className="py-2 font-medium">Top Values</td>
          <td className="py-2">
            <ul className="list-disc list-inside">
              {stats.categorical_stats.top_values.map((item, index) => (
                <li key={index}>
                  {item.value}: {item.count}
                </li>
              ))}
            </ul>
          </td>
        </tr>
      </>
    )
  }

  const renderDateStats = () => {
    if (!stats.date_stats) return null

    return (
      <>
        <tr>
          <td className="py-2 font-medium">Earliest Date</td>
          <td className="py-2">{new Date(stats.date_stats.min_date).toLocaleDateString()}</td>
        </tr>
        <tr>
          <td className="py-2 font-medium">Latest Date</td>
          <td className="py-2">{new Date(stats.date_stats.max_date).toLocaleDateString()}</td>
        </tr>
      </>
    )
  }

  const renderTextStats = () => {
    if (!stats.text_stats) return null

    return (
      <>
        <tr>
          <td className="py-2 font-medium">Average Length</td>
          <td className="py-2">{stats.text_stats.avg_length.toFixed(2)} characters</td>
        </tr>
        <tr>
          <td className="py-2 font-medium">Sample Values</td>
          <td className="py-2">
            <ul className="list-disc list-inside">
              {stats.text_stats.sample_values.map((value, index) => (
                <li key={index} className="truncate max-w-xs">{value}</li>
              ))}
            </ul>
          </td>
        </tr>
      </>
    )
  }

  return (
    <>
      <Card className="w-full bg-white shadow-md rounded-lg overflow-hidden">
        <CardHeader className="bg-gray-50 border-b">
          <CardTitle className="text-lg font-semibold">
            {stats.field_name}
            <span className="ml-2 text-sm text-gray-500">({stats.field_type})</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4">
          <table className="w-full">
            <tbody>
              <tr>
                <td className="py-2 font-medium">Count</td>
                <td className="py-2">{stats.count}</td>
              </tr>
              <tr>
                <td className="py-2 font-medium">Missing Values</td>
                <td className="py-2">{stats.missing_values}</td>
              </tr>
              <tr>
                <td className="py-2 font-medium">Unique Values</td>
                <td className="py-2">{stats.unique_values}</td>
              </tr>
              {renderNumericStats()}
              {renderCategoricalStats()}
              {renderDateStats()}
              {renderTextStats()}
            </tbody>
          </table>
        </CardContent>
      </Card>

      {stats.numeric_stats?.histogram && (
        <HistogramModal
          isOpen={isHistogramOpen}
          onClose={() => setIsHistogramOpen(false)}
          columnName={stats.field_name}
          histogramData={{
            bin_edges: stats.numeric_stats.histogram.bins,
            bin_counts: stats.numeric_stats.histogram.counts,
            bin_width: (stats.numeric_stats.max - stats.numeric_stats.min) / stats.numeric_stats.histogram.bins.length,
            min_value: stats.numeric_stats.min,
            max_value: stats.numeric_stats.max
          }}
        />
      )}
    </>
  )
} 