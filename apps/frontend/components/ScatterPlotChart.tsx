'use client'

import React from 'react'
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import type { ScatterPointItem } from 'recharts'

export interface ScatterPlotData {
  data: Array<{
    x: number
    y: number
    label?: string
    category?: string
  }>
  xLabel: string
  yLabel: string
  title?: string
}

interface ScatterPlotChartProps {
  data: ScatterPlotData
  width?: number
  height?: number
  onPointClick?: (point: Record<string, unknown>) => void
}

// Module scope, not inside ScatterPlotChart: a component created during render
// gets a fresh identity each render and remounts the tooltip subtree
// (react-hooks/static-components). It closes over nothing, so lifting it needs
// no extra props.
function CustomTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: { x: number; y: number; label?: string; category?: string } }> }) {
  if (active && payload && payload.length) {
    const point = payload[0].payload
    return (
      <div className="bg-white p-3 border rounded shadow-lg">
        <p className="font-medium">{point.label || 'Data Point'}</p>
        <p className="text-sm text-gray-600">
          {point.x.toFixed(2)}, {point.y.toFixed(2)}
        </p>
        {point.category && (
          <p className="text-sm text-gray-500">Category: {point.category}</p>
        )}
      </div>
    )
  }
  return null
}

export function ScatterPlotChart({
  data,
  width = 600,
  height = 400,
  onPointClick
}: ScatterPlotChartProps) {
  const colors = ['#8884d8', '#82ca9d', '#ffc658', '#ff7c7c', '#8dd1e1']
  
  // Group data by category if available
  const groupedData = data.data.reduce((acc, point) => {
    const category = point.category || 'default'
    if (!acc[category]) {
      acc[category] = []
    }
    acc[category].push(point)
    return acc
  }, {} as Record<string, typeof data.data>)

  return (
    <div className="w-full">
      {data.title && (
        <h3 className="text-lg font-semibold mb-4 text-center">{data.title}</h3>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <ScatterChart
          width={width}
          height={height}
          margin={{ top: 20, right: 20, bottom: 60, left: 60 }}
        >
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis 
            type="number" 
            dataKey="x"
            name={data.xLabel}
            label={{ value: data.xLabel, position: 'insideBottom', offset: -10 }}
          />
          <YAxis 
            type="number" 
            dataKey="y"
            name={data.yLabel}
            label={{ value: data.yLabel, angle: -90, position: 'insideLeft' }}
          />
          <Tooltip content={<CustomTooltip />} />
          {Object.keys(groupedData).length > 1 && <Legend />}
          
          {Object.entries(groupedData).map(([category, points], index) => (
            <Scatter
              key={category}
              name={category === 'default' ? data.title || 'Data' : category}
              data={points}
              fill={colors[index % colors.length]}
              // recharts 3 narrows the Scatter onClick argument to ScatterPointItem,
              // which has no string index signature, so the v2 code stopped
              // compiling. The caller wants the datum, so hand it `payload` — and
              // skip the call entirely when there is none, rather than reporting an
              // empty click the caller cannot tell from a real one. Typed against
              // recharts' own export instead of casting through `unknown`.
              onClick={
                onPointClick
                  ? (point: ScatterPointItem) => {
                      const entry = point.payload as
                        | Record<string, unknown>
                        | undefined
                      if (entry) onPointClick(entry)
                    }
                  : undefined
              }
              cursor="pointer"
            />
          ))}
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  )
}