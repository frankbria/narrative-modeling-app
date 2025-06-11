'use client'

import React from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Slider } from '@/components/ui/slider'
import { Badge } from '@/components/ui/badge'
import { X, Download, Refresh } from 'lucide-react'

export interface ChartFilter {
  column: string
  operator: 'equals' | 'greater_than' | 'less_than' | 'contains' | 'between'
  value: string | number | [number, number]
  label?: string
}

export interface ChartControlsProps {
  columns: Array<{
    name: string
    type: 'numeric' | 'categorical' | 'datetime' | 'text'
  }>
  chartType: string
  onChartTypeChange: (type: string) => void
  filters: ChartFilter[]
  onFiltersChange: (filters: ChartFilter[]) => void
  onExport?: () => void
  onRefresh?: () => void
  showAnimations?: boolean
  onAnimationsChange?: (enabled: boolean) => void
  binCount?: number
  onBinCountChange?: (count: number) => void
  showGrid?: boolean
  onGridChange?: (enabled: boolean) => void
}

const chartTypes = [
  { value: 'histogram', label: 'Histogram' },
  { value: 'boxplot', label: 'Box Plot' },
  { value: 'scatter', label: 'Scatter Plot' },
  { value: 'line', label: 'Line Chart' },
  { value: 'correlation', label: 'Correlation Heatmap' },
  { value: 'bar', label: 'Bar Chart' },
]

const operators = [
  { value: 'equals', label: 'Equals' },
  { value: 'greater_than', label: 'Greater Than' },
  { value: 'less_than', label: 'Less Than' },
  { value: 'contains', label: 'Contains' },
  { value: 'between', label: 'Between' },
]

export function ChartControls({
  columns,
  chartType,
  onChartTypeChange,
  filters,
  onFiltersChange,
  onExport,
  onRefresh,
  showAnimations = true,
  onAnimationsChange,
  binCount = 50,
  onBinCountChange,
  showGrid = true,
  onGridChange,
}: ChartControlsProps) {
  const addFilter = () => {
    const newFilter: ChartFilter = {
      column: columns[0]?.name || '',
      operator: 'equals',
      value: '',
    }
    onFiltersChange([...filters, newFilter])
  }

  const updateFilter = (index: number, updates: Partial<ChartFilter>) => {
    const newFilters = [...filters]
    newFilters[index] = { ...newFilters[index], ...updates }
    onFiltersChange(newFilters)
  }

  const removeFilter = (index: number) => {
    onFiltersChange(filters.filter((_, i) => i !== index))
  }

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          Chart Configuration
          <div className="flex gap-2">
            {onRefresh && (
              <Button variant="outline" size="sm" onClick={onRefresh}>
                <Refresh className="h-4 w-4" />
              </Button>
            )}
            {onExport && (
              <Button variant="outline" size="sm" onClick={onExport}>
                <Download className="h-4 w-4" />
              </Button>
            )}
          </div>
        </CardTitle>
        <CardDescription>
          Configure chart type, filters, and display options
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Chart Type Selection */}
        <div className="space-y-2">
          <Label>Chart Type</Label>
          <Select value={chartType} onValueChange={onChartTypeChange}>
            <SelectTrigger>
              <SelectValue placeholder="Select chart type" />
            </SelectTrigger>
            <SelectContent>
              {chartTypes.map((type) => (
                <SelectItem key={type.value} value={type.value}>
                  {type.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Chart-specific Controls */}
        {chartType === 'histogram' && onBinCountChange && (
          <div className="space-y-2">
            <Label>Number of Bins: {binCount}</Label>
            <Slider
              value={[binCount]}
              onValueChange={(value) => onBinCountChange(value[0])}
              min={10}
              max={100}
              step={5}
              className="w-full"
            />
          </div>
        )}

        {/* Display Options */}
        <div className="space-y-4">
          <Label className="text-sm font-medium">Display Options</Label>
          
          {onGridChange && (
            <div className="flex items-center justify-between">
              <Label htmlFor="show-grid" className="text-sm">Show Grid</Label>
              <Switch
                id="show-grid"
                checked={showGrid}
                onCheckedChange={onGridChange}
              />
            </div>
          )}
          
          {onAnimationsChange && (
            <div className="flex items-center justify-between">
              <Label htmlFor="show-animations" className="text-sm">Animations</Label>
              <Switch
                id="show-animations"
                checked={showAnimations}
                onCheckedChange={onAnimationsChange}
              />
            </div>
          )}
        </div>

        {/* Filters */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <Label className="text-sm font-medium">Filters</Label>
            <Button variant="outline" size="sm" onClick={addFilter}>
              Add Filter
            </Button>
          </div>

          {filters.length === 0 && (
            <p className="text-sm text-muted-foreground">No filters applied</p>
          )}

          {filters.map((filter, index) => (
            <div key={index} className="space-y-2 p-3 border rounded-lg">
              <div className="flex items-center justify-between">
                <Badge variant="secondary">Filter {index + 1}</Badge>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => removeFilter(index)}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <Label className="text-xs">Column</Label>
                  <Select
                    value={filter.column}
                    onValueChange={(value) => updateFilter(index, { column: value })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {columns.map((col) => (
                        <SelectItem key={col.name} value={col.name}>
                          {col.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label className="text-xs">Operator</Label>
                  <Select
                    value={filter.operator}
                    onValueChange={(value: any) => updateFilter(index, { operator: value })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {operators.map((op) => (
                        <SelectItem key={op.value} value={op.value}>
                          {op.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div>
                <Label className="text-xs">Value</Label>
                {filter.operator === 'between' ? (
                  <div className="grid grid-cols-2 gap-2">
                    <Input
                      type="number"
                      placeholder="Min"
                      value={Array.isArray(filter.value) ? filter.value[0] : ''}
                      onChange={(e) => {
                        const currentValue = Array.isArray(filter.value) ? filter.value : [0, 0]
                        updateFilter(index, { 
                          value: [parseFloat(e.target.value) || 0, currentValue[1]] 
                        })
                      }}
                    />
                    <Input
                      type="number"
                      placeholder="Max"
                      value={Array.isArray(filter.value) ? filter.value[1] : ''}
                      onChange={(e) => {
                        const currentValue = Array.isArray(filter.value) ? filter.value : [0, 0]
                        updateFilter(index, { 
                          value: [currentValue[0], parseFloat(e.target.value) || 0] 
                        })
                      }}
                    />
                  </div>
                ) : (
                  <Input
                    placeholder="Filter value"
                    value={Array.isArray(filter.value) ? '' : filter.value}
                    onChange={(e) => updateFilter(index, { value: e.target.value })}
                  />
                )}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}