'use client'

import React from 'react'
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'

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
  onPointClick?: (point: any) => void
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

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload
      return (
        <div className="bg-white p-3 border rounded shadow-lg">
          <p className="font-medium">{data.label || 'Data Point'}</p>
          <p className="text-sm text-gray-600">
            {data.x.toFixed(2)}, {data.y.toFixed(2)}
          </p>
          {data.category && (
            <p className="text-sm text-gray-500">Category: {data.category}</p>
          )}
        </div>
      )
    }
    return null
  }

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
              onClick={onPointClick}
              cursor="pointer"
            />
          ))}
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  )
}