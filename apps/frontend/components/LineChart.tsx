'use client'

import React from 'react'
import { LineChart as RechartsLineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, Brush } from 'recharts'

export interface LineChartData {
  data: Array<{
    x: string | number
    [key: string]: string | number
  }>
  lines: Array<{
    dataKey: string
    label: string
    color?: string
  }>
  xLabel: string
  yLabel: string
  title?: string
  showBrush?: boolean
}

interface LineChartProps {
  data: LineChartData
  width?: number
  height?: number
  onPointClick?: (data: Record<string, unknown>) => void
}

// Defined at module scope, not inside LineChart: a component created during
// render gets a new identity every render, which remounts the tooltip subtree
// (react-hooks/static-components). recharts clones the `content` element and
// injects active/payload/label, so `xLabel` is passed in explicitly instead of
// being closed over.
function CustomTooltip({
  active,
  payload,
  label,
  xLabel,
}: {
  active?: boolean
  payload?: Array<{ name: string; value: number | string; color: string }>
  label?: string | number
  xLabel?: string
}) {
  if (active && payload && payload.length) {
    return (
      <div className="bg-white p-3 border rounded shadow-lg">
        <p className="font-medium">{`${xLabel}: ${label}`}</p>
        {payload.map((entry, index: number) => (
          <p key={index} style={{ color: entry.color }} className="text-sm">
            {`${entry.name}: ${typeof entry.value === 'number' ? entry.value.toFixed(2) : entry.value}`}
          </p>
        ))}
      </div>
    )
  }
  return null
}

export function LineChart({
  data,
  width = 600,
  height = 400,
  onPointClick
}: LineChartProps) {
  const colors = ['#8884d8', '#82ca9d', '#ffc658', '#ff7c7c', '#8dd1e1', '#d084d0']

  // recharts' onClick passes a CategoricalChartState; adapt it to the simpler
  // Record<string, unknown> shape exposed by this component's onPointClick prop.
  const handleChartClick = onPointClick
    ? (state: unknown) => onPointClick((state ?? {}) as Record<string, unknown>)
    : undefined

  return (
    <div className="w-full">
      {data.title && (
        <h3 className="text-lg font-semibold mb-4 text-center">{data.title}</h3>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <RechartsLineChart
          width={width}
          height={height}
          data={data.data}
          margin={{ top: 20, right: 30, left: 60, bottom: 60 }}
          onClick={handleChartClick}
        >
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis 
            dataKey="x"
            label={{ value: data.xLabel, position: 'insideBottom', offset: -10 }}
          />
          <YAxis 
            label={{ value: data.yLabel, angle: -90, position: 'insideLeft' }}
          />
          <Tooltip content={<CustomTooltip xLabel={data.xLabel} />} />
          {data.lines.length > 1 && <Legend />}
          
          {data.lines.map((line, index) => (
            <Line
              key={line.dataKey}
              type="monotone"
              dataKey={line.dataKey}
              stroke={line.color || colors[index % colors.length]}
              strokeWidth={2}
              dot={{ r: 4 }}
              activeDot={{ r: 6 }}
              name={line.label}
            />
          ))}
          
          {data.showBrush && (
            <Brush dataKey="x" height={30} stroke="#8884d8" />
          )}
        </RechartsLineChart>
      </ResponsiveContainer>
    </div>
  )
}