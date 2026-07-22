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
import type { CurvePoint, ROCCurveData } from '@/lib/types/evaluation'

export interface ROCCurveChartProps {
  data: ROCCurveData
  height?: number
}

export const CURVE_COLORS = [
  '#3B82F6', // blue
  '#10B981', // green
  '#F59E0B', // amber
  '#8B5CF6', // violet
  '#EF4444', // red
  '#14B8A6', // teal
  '#EC4899', // pink
  '#6366F1' // indigo
]

// Per-series dash patterns (issue #282): a colour-independent channel so ROC/PR
// classes stay distinguishable for colour-vision-deficient viewers. Index 0 is
// solid; recharts reads '0' as no dashing.
export const CURVE_DASH = [
  '0', // solid
  '6 3',
  '2 3',
  '8 3 2 3',
  '10 4',
  '4 4',
  '1 3',
  '12 3 2 3 2 3'
]

interface CurveTooltipProps {
  active?: boolean
  payload?: Array<{ name?: string; color?: string; payload: CurvePoint }>
  xLabel: string
  yLabel: string
}

/** Shared tooltip for ROC/PR curve points: axis values plus threshold. */
export function CurvePointTooltip({ active, payload, xLabel, yLabel }: CurveTooltipProps) {
  if (!active || !payload || payload.length === 0) return null
  const point = payload[0].payload
  return (
    <div className="bg-white p-3 border border-gray-200 rounded-lg shadow-lg text-sm">
      {payload[0].name && (
        <p className="font-semibold text-gray-900 mb-1">{payload[0].name}</p>
      )}
      <p className="text-gray-600">
        {xLabel}: <span className="font-medium">{point.x.toFixed(3)}</span>
      </p>
      <p className="text-gray-600">
        {yLabel}: <span className="font-medium">{point.y.toFixed(3)}</span>
      </p>
      {point.threshold !== undefined && point.threshold !== null && (
        <p className="text-gray-600">
          Threshold: <span className="font-medium">{point.threshold.toFixed(3)}</span>
        </p>
      )}
    </div>
  )
}

/**
 * Per-class ROC curves (issue #79): one line per class with its AUC in the
 * legend, plus a dashed y=x diagonal for the random classifier.
 */
export function ROCCurveChart({ data, height = 400 }: ROCCurveChartProps) {
  const classLabels = Object.keys(data.curves)

  if (classLabels.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 bg-gray-50 rounded-lg border border-gray-200">
        <p className="text-gray-500">No ROC curve data available</p>
      </div>
    )
  }

  const seriesName = (label: string): string => {
    const auc = data.auc_per_class[label]
    return auc !== undefined ? `${label} (AUC ${auc.toFixed(2)})` : label
  }

  const ariaLabel =
    `ROC curves for ${classLabels.length} class${classLabels.length === 1 ? '' : 'es'}: ` +
    classLabels.map((l) => seriesName(l)).join(', ') +
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
          label={{ value: 'False Positive Rate', position: 'insideBottom', offset: -15 }}
        />
        <YAxis
          type="number"
          domain={[0, 1]}
          label={{ value: 'True Positive Rate', angle: -90, position: 'insideLeft' }}
        />
        <Tooltip
          content={
            <CurvePointTooltip xLabel="False Positive Rate" yLabel="True Positive Rate" />
          }
        />
        <Legend verticalAlign="top" />
        <ReferenceLine
          segment={[
            { x: 0, y: 0 },
            { x: 1, y: 1 }
          ]}
          stroke="#9CA3AF"
          strokeDasharray="5 5"
          ifOverflow="extendDomain"
        />
        {classLabels.map((label, index) => (
          <Line
            key={label}
            data={data.curves[label]}
            dataKey="y"
            name={seriesName(label)}
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
