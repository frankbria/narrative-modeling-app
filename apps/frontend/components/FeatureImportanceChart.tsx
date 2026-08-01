'use client'

import React from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell
} from 'recharts'
import type { FeatureScore } from '@/lib/services/featureSelection'

export interface FeatureImportanceChartProps {
  features: FeatureScore[]
  height?: number
  showOnlySelected?: boolean
  onFeatureClick?: (feature: FeatureScore) => void
  highlightThreshold?: number
}

// Module scope, not inside the chart component: a component created during
// render gets a fresh identity each render and remounts the tooltip subtree
// (react-hooks/static-components). It closes over nothing, so lifting it needs
// no extra props.
function CustomTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: FeatureScore }> }) {
  if (active && payload && payload.length) {
    const feature: FeatureScore = payload[0].payload
    return (
      <div className="bg-white p-4 border border-gray-200 rounded-lg shadow-lg">
        <p className="font-semibold text-gray-900">{feature.feature_name}</p>
        <p className="text-sm text-gray-600 mt-1">
          Score: <span className="font-medium">{feature.score.toFixed(4)}</span>
        </p>
        <p className="text-sm text-gray-600">
          Rank: <span className="font-medium">#{feature.rank}</span>
        </p>
        <p className="text-sm mt-1">
          {feature.selected ? (
            <span className="text-green-600 font-medium">✓ Selected</span>
          ) : (
            <span className="text-gray-500">Not selected</span>
          )}
        </p>
      </div>
    )
  }
  return null
}

export function FeatureImportanceChart({
  features,
  height = 500,
  showOnlySelected = false,
  onFeatureClick,
  highlightThreshold = 0.5
}: FeatureImportanceChartProps) {
  // Filter and sort features
  const chartData = React.useMemo(() => {
    const filtered = showOnlySelected
      ? features.filter((f) => f.selected)
      : features

    // Sort by score descending
    return [...filtered].sort((a, b) => b.score - a.score)
  }, [features, showOnlySelected])

  // Color scale based on importance
  const getBarColor = (score: number, selected: boolean) => {
    if (!selected) return '#9CA3AF' // Gray for unselected

    if (score >= 0.8) return '#10B981' // Green for high importance
    if (score >= highlightThreshold) return '#3B82F6' // Blue for medium importance
    return '#F59E0B' // Orange for low importance
  }


  if (chartData.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 bg-gray-50 rounded-lg border border-gray-200">
        <p className="text-gray-500">No feature importance data available</p>
      </div>
    )
  }

  return (
    <div className="w-full">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Feature Importance</h3>
          <p className="text-sm text-gray-600">
            Showing {chartData.length} feature{chartData.length !== 1 ? 's' : ''}
          </p>
        </div>
        <div className="flex gap-4 text-sm">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-sm bg-green-500"></div>
            <span className="text-gray-600">High (≥0.8)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-sm bg-blue-500"></div>
            <span className="text-gray-600">Medium (≥{highlightThreshold})</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-sm bg-orange-500"></div>
            <span className="text-gray-600">Low (&lt;{highlightThreshold})</span>
          </div>
          {!showOnlySelected && (
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-sm bg-gray-400"></div>
              <span className="text-gray-600">Unselected</span>
            </div>
          )}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={height}>
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ top: 5, right: 30, left: 150, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" domain={[0, 1]} />
          <YAxis
            type="category"
            dataKey="feature_name"
            width={140}
            tick={{ fontSize: 12 }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Bar
            dataKey="score"
            onClick={(data) => onFeatureClick && onFeatureClick(data)}
            cursor={onFeatureClick ? 'pointer' : 'default'}
          >
            {chartData.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={getBarColor(entry.score, entry.selected)}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
