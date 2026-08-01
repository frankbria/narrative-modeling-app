'use client'

import React from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer
} from 'recharts'
import type { RankedFeature } from '@/lib/types/evaluation'

export interface ShapSummaryChartProps {
  /** Mean |SHAP| per feature, any order (sorted internally, descending). */
  features: RankedFeature[]
  /** Optional plain-language summary of the top drivers (issue #80). */
  plainLanguage?: string
  /** "tree" | "linear" — shown as a small badge when provided. */
  explainerType?: string | null
  height?: number
  /** Cap the number of bars (top-N by importance); 0/undefined = all. */
  maxFeatures?: number
}

/**
 * SHAP summary plot (issue #80): a horizontal bar chart of each feature's mean
 * absolute SHAP value — how much, on average, the feature moves the model's
 * output. Uses Recharts, matching the evaluate page's other charts (P2.3).
 */
// Module scope, not inside the chart component: a component created during
// render gets a fresh identity each render and remounts the tooltip subtree
// (react-hooks/static-components). It closes over nothing, so lifting it needs
// no extra props.
function CustomTooltip({
  active,
  payload
}: {
  active?: boolean
  payload?: Array<{ payload: RankedFeature }>
}) {
  if (active && payload && payload.length) {
    const feature = payload[0].payload
    return (
      <div className="bg-white p-4 border border-gray-200 rounded-lg shadow-lg">
        <p className="font-semibold text-gray-900">{feature.feature_name}</p>
        <p className="text-sm text-gray-600 mt-1">
          Mean |SHAP|:{' '}
          <span className="font-medium">{feature.importance.toFixed(4)}</span>
        </p>
      </div>
    )
  }
  return null
}

export function ShapSummaryChart({
  features,
  plainLanguage,
  explainerType,
  height = 360,
  maxFeatures
}: ShapSummaryChartProps) {
  const chartData = React.useMemo(() => {
    const sorted = [...features].sort((a, b) => b.importance - a.importance)
    return maxFeatures && maxFeatures > 0 ? sorted.slice(0, maxFeatures) : sorted
  }, [features, maxFeatures])

  if (chartData.length === 0) {
    return (
      <div
        data-testid="shap-empty"
        className="flex items-center justify-center h-64 bg-gray-50 rounded-lg border border-gray-200"
      >
        <p className="text-gray-500">No SHAP data available</p>
      </div>
    )
  }

  return (
    <div className="w-full" data-testid="shap-summary-chart">
      <div className="mb-2 flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">
            SHAP Feature Impact
          </h3>
          <p className="text-sm text-gray-600">
            Average impact of each feature on the model&apos;s output
          </p>
        </div>
        {explainerType && (
          <span className="text-xs px-2 py-1 rounded-full bg-purple-100 text-purple-700 font-medium">
            {explainerType} explainer
          </span>
        )}
      </div>

      {plainLanguage && (
        <p
          data-testid="shap-plain-language"
          className="mb-3 text-sm text-gray-700 bg-purple-50 border border-purple-100 rounded-md px-3 py-2"
        >
          {plainLanguage}
        </p>
      )}

      <ResponsiveContainer width="100%" height={height}>
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ top: 5, right: 30, left: 150, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" />
          <YAxis
            type="category"
            dataKey="feature_name"
            width={140}
            tick={{ fontSize: 12 }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Bar dataKey="importance" fill="#8B5CF6" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
