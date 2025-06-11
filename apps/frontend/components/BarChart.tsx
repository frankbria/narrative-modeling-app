'use client'

import React from 'react'
import { BarChart as RechartsBarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'

export interface BarChartData {
  data: Array<{
    category: string
    value: number
    [key: string]: string | number
  }>
  xLabel: string
  yLabel: string
  title?: string
  color?: string
  sortBy?: 'value' | 'category' | 'none'
  showPercentages?: boolean
}

interface BarChartProps {
  data: BarChartData
  width?: number
  height?: number
  orientation?: 'vertical' | 'horizontal'
  onBarClick?: (data: any) => void
}

export function BarChart({ 
  data, 
  width = 600, 
  height = 400,
  orientation = 'vertical',
  onBarClick 
}: BarChartProps) {
  // Sort data if specified
  const sortedData = React.useMemo(() => {
    if (data.sortBy === 'none') return data.data
    
    return [...data.data].sort((a, b) => {
      if (data.sortBy === 'value') {
        return b.value - a.value // Descending by value
      } else if (data.sortBy === 'category') {
        return a.category.localeCompare(b.category) // Ascending by category
      }
      return 0
    })
  }, [data.data, data.sortBy])

  // Calculate total for percentages
  const total = React.useMemo(() => {
    return sortedData.reduce((sum, item) => sum + item.value, 0)
  }, [sortedData])

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const value = payload[0].value
      const percentage = ((value / total) * 100).toFixed(1)
      
      return (
        <div className="bg-white p-3 border rounded shadow-lg">
          <p className="font-medium">{label}</p>
          <p style={{ color: payload[0].color }} className="text-sm">
            {`${data.yLabel}: ${value.toLocaleString()}`}
          </p>
          {data.showPercentages && (
            <p className="text-sm text-gray-500">
              {`${percentage}% of total`}
            </p>
          )}
        </div>
      )
    }
    return null
  }

  const chartProps = {
    width,
    height,
    data: sortedData,
    margin: { top: 20, right: 30, left: 60, bottom: 80 },
    onClick: onBarClick
  }

  return (
    <div className="w-full">
      {data.title && (
        <h3 className="text-lg font-semibold mb-4 text-center">{data.title}</h3>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <RechartsBarChart {...chartProps}>
          <CartesianGrid strokeDasharray="3 3" />
          
          {orientation === 'vertical' ? (
            <>
              <XAxis 
                dataKey="category"
                angle={-45}
                textAnchor="end"
                height={80}
                interval={0}
                label={{ value: data.xLabel, position: 'insideBottom', offset: -60 }}
              />
              <YAxis 
                label={{ value: data.yLabel, angle: -90, position: 'insideLeft' }}
              />
            </>
          ) : (
            <>
              <XAxis 
                type="number"
                label={{ value: data.yLabel, position: 'insideBottom', offset: -10 }}
              />
              <YAxis 
                type="category"
                dataKey="category"
                width={100}
                label={{ value: data.xLabel, angle: -90, position: 'insideLeft' }}
              />
            </>
          )}
          
          <Tooltip content={<CustomTooltip />} />
          
          <Bar 
            dataKey="value" 
            fill={data.color || "#8884d8"}
            radius={[2, 2, 0, 0]}
            cursor="pointer"
          />
        </RechartsBarChart>
      </ResponsiveContainer>
      
      {/* Summary Stats */}
      <div className="mt-4 grid grid-cols-3 gap-4 text-sm text-gray-600">
        <div className="text-center">
          <div className="font-medium">{sortedData.length}</div>
          <div>Categories</div>
        </div>
        <div className="text-center">
          <div className="font-medium">{total.toLocaleString()}</div>
          <div>Total</div>
        </div>
        <div className="text-center">
          <div className="font-medium">
            {sortedData.length > 0 ? (total / sortedData.length).toFixed(1) : 0}
          </div>
          <div>Average</div>
        </div>
      </div>
    </div>
  )
}