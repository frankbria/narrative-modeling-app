import React, { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { HistogramModal } from './HistogramModal'
import { BoxplotModal } from './BoxplotModal'
import { Button } from '@/components/ui/button'

interface NumericStats {
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
  q1?: number
  q3?: number
  outliers?: number[]
}

interface DateStats {
  min_date: string
  max_date: string
}

interface TextStats {
  avg_length: number
  sample_values: string[]
}

interface StatsCardProps {
  title?: string;
  stats: {
    field_name: string;
    field_type: string;
    count: number;
    missing_values: number;
    unique_values: number;
    numeric_stats?: NumericStats;
    categorical_stats?: {
      unique_categories: number;
      top_values: Array<{ value: string; count: number }>;
    };
    date_stats?: DateStats;
    text_stats?: TextStats;
  };
}

export function StatsCard({ title, stats }: StatsCardProps) {
  const [showHistogram, setShowHistogram] = useState(false)
  const [showBoxplot, setShowBoxplot] = useState(false)

  const renderCategoricalStats = () => {
    if (!stats.categorical_stats) return null

    return (
      <div className="border-t pt-4">
        <h3 className="text-sm font-medium mb-2">Categorical Statistics</h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-sm text-gray-500">Unique Categories</p>
            <p className="font-medium">{stats.categorical_stats.unique_categories}</p>
          </div>
        </div>
        <div className="mt-2">
          <p className="text-sm text-gray-500">Top Values</p>
          <ul className="list-disc list-inside text-sm">
            {stats.categorical_stats.top_values.map((item, index) => (
              <li key={index}>
                {item.value}: {item.count}
              </li>
            ))}
          </ul>
        </div>
      </div>
    )
  }

  const renderDateStats = () => {
    if (!stats.date_stats) return null

    return (
      <div className="border-t pt-4">
        <h3 className="text-sm font-medium mb-2">Date Statistics</h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-sm text-gray-500">Min Date</p>
            <p className="font-medium">{new Date(stats.date_stats.min_date).toLocaleDateString()}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Max Date</p>
            <p className="font-medium">{new Date(stats.date_stats.max_date).toLocaleDateString()}</p>
          </div>
        </div>
      </div>
    )
  }

  const renderTextStats = () => {
    if (!stats.text_stats) return null

    return (
      <div className="border-t pt-4">
        <h3 className="text-sm font-medium mb-2">Text Statistics</h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-sm text-gray-500">Average Length</p>
            <p className="font-medium">{stats.text_stats.avg_length.toFixed(2)}</p>
          </div>
        </div>
        <div className="mt-2">
          <p className="text-sm text-gray-500">Sample Values</p>
          <ul className="list-disc list-inside text-sm">
            {stats.text_stats.sample_values.map((value, index) => (
              <li key={index}>{value}</li>
            ))}
          </ul>
        </div>
      </div>
    )
  }

  return (
    <Card className="bg-white shadow-sm">
      <CardHeader className="pb-2">
        <CardTitle className="text-lg font-bold">{title || stats.field_name}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-gray-500">Type</p>
              <p className="font-medium">{stats.field_type}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Count</p>
              <p className="font-medium">{stats.count}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Missing Values</p>
              <p className="font-medium">{stats.missing_values}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Unique Values</p>
              <p className="font-medium">{stats.unique_values}</p>
            </div>
          </div>

          {stats.numeric_stats && (
            <div className="border-t pt-4">
              <h3 className="text-sm font-medium mb-2">Numeric Statistics</h3>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-gray-500">Min</p>
                  <p className="font-medium">{stats.numeric_stats.min.toFixed(2)}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Max</p>
                  <p className="font-medium">{stats.numeric_stats.max.toFixed(2)}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Mean</p>
                  <p className="font-medium">{stats.numeric_stats.mean.toFixed(2)}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Median</p>
                  <p className="font-medium">{stats.numeric_stats.median.toFixed(2)}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Mode</p>
                  <p className="font-medium">{stats.numeric_stats.mode.toFixed(2)}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Std Dev</p>
                  <p className="font-medium">{stats.numeric_stats.std_dev.toFixed(2)}</p>
                </div>
              </div>
              <div className="mt-4 flex space-x-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowHistogram(true)}
                >
                  View Histogram
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowBoxplot(true)}
                >
                  View Boxplot
                </Button>
              </div>
            </div>
          )}

          {renderCategoricalStats()}
          {renderDateStats()}
          {renderTextStats()}
        </div>
      </CardContent>

      <HistogramModal
        isOpen={showHistogram}
        onClose={() => setShowHistogram(false)}
        columnName={stats.field_name}
        histogramData={stats.numeric_stats?.histogram ? {
          bin_edges: stats.numeric_stats.histogram.bins,
          bin_counts: stats.numeric_stats.histogram.counts,
          bin_width: stats.numeric_stats.histogram.bins.length > 1 
            ? stats.numeric_stats.histogram.bins[1] - stats.numeric_stats.histogram.bins[0] 
            : 1,
          min_value: stats.numeric_stats.min,
          max_value: stats.numeric_stats.max
        } : undefined}
      />

      <BoxplotModal
        isOpen={showBoxplot}
        onClose={() => setShowBoxplot(false)}
        columnName={stats.field_name}
        boxplotData={{
          min: stats.numeric_stats?.min || 0,
          q1: stats.numeric_stats?.q1 || 0,
          median: stats.numeric_stats?.median || 0,
          q3: stats.numeric_stats?.q3 || 0,
          max: stats.numeric_stats?.max || 0,
          outliers: stats.numeric_stats?.outliers || []
        }}
      />
    </Card>
  )
} 