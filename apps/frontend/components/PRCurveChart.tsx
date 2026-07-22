'use client'

import React from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine
} from 'recharts'
import type { PRCurveData } from '@/lib/types/evaluation'
import { CURVE_COLORS, CURVE_DASH, CurvePointTooltip } from '@/components/ROCCurveChart'

export interface PRCurveChartProps {
  data: PRCurveData
  height?: number
}

/**
 * Per-class precision-recall curves (issue #79). For a single class a dashed
 * horizontal baseline marks the positive-class prevalence (random classifier);
 * with multiple classes per-class baselines would be noisy, so they're omitted.
 */
export function PRCurveChart({ data, height = 400 }: PRCurveChartProps) {
  const classLabels = Object.keys(data.curves)

  if (classLabels.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 bg-gray-50 rounded-lg border border-gray-200">
        <p className="text-gray-500">No precision-recall curve data available</p>
      </div>
    )
  }

  const singleClassBaseline =
    classLabels.length === 1 ? data.baseline_per_class[classLabels[0]] : undefined

  const ariaLabel =
    `Precision-recall curves for ${classLabels.length} class${classLabels.length === 1 ? '' : 'es'}: ` +
    classLabels.join(', ') +
    '. Each class is drawn with a distinct colour and line-dash pattern.'

  return (
    <div role="img" aria-label={ariaLabel}>
    <ResponsiveContainer width="100%" height={height}>
      <LineChart margin={{ top: 10, right: 30, left: 10, bottom: 25 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis
          type="number"
          dataKey="x"
          domain={[0, 1]}
          label={{ value: 'Recall', position: 'insideBottom', offset: -15 }}
        />
        <YAxis
          type="number"
          domain={[0, 1]}
          label={{ value: 'Precision', angle: -90, position: 'insideLeft' }}
        />
        <Tooltip content={<CurvePointTooltip xLabel="Recall" yLabel="Precision" />} />
        <Legend verticalAlign="top" />
        {singleClassBaseline !== undefined && (
          <ReferenceLine
            y={singleClassBaseline}
            stroke="#9CA3AF"
            strokeDasharray="5 5"
            label={{ value: 'Baseline', position: 'right', fontSize: 11 }}
          />
        )}
        {classLabels.map((label, index) => (
          <Line
            key={label}
            data={data.curves[label]}
            dataKey="y"
            name={label}
            type="monotone"
            dot={false}
            stroke={CURVE_COLORS[index % CURVE_COLORS.length]}
            strokeDasharray={CURVE_DASH[index % CURVE_DASH.length]}
            strokeWidth={2}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
    </div>
  )
}
