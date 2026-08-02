'use client'

import React from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '@/components/ui/select'
import { Slider } from '@/components/ui/slider'
import {
  type SelectionMethod,
  type ProblemType,
  getMethodName,
  getMethodDescription,
  getMethodUseCase
} from '@/lib/services/featureSelection'

export interface SelectionConfig {
  method: SelectionMethod
  targetColumn: string
  topK?: number
  threshold?: number
  correlationThreshold: number
  problemType?: ProblemType
  sampleSize?: number
}

export interface SelectionControlsProps {
  config: SelectionConfig
  onChange: (config: SelectionConfig) => void
  onRunSelection: () => void
  onCompare: () => void
  columns: string[]
  isLoading?: boolean
  disabled?: boolean
}

const METHODS: SelectionMethod[] = [
  'correlation',
  'mutual_info',
  'random_forest',
  'rfe',
  'lasso',
  'statistical'
]

export function SelectionControls({
  config,
  onChange,
  onRunSelection,
  onCompare,
  columns,
  isLoading = false,
  disabled = false
}: SelectionControlsProps) {
  const updateConfig = (updates: Partial<SelectionConfig>) => {
    onChange({ ...config, ...updates })
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Feature Selection Configuration</CardTitle>
        <CardDescription>
          Choose a selection algorithm and configure parameters
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Target Column Selection */}
        <div className="space-y-2">
          <Label htmlFor="target-column">Target Column *</Label>
          <Select
            value={config.targetColumn}
            onValueChange={(value) => updateConfig({ targetColumn: value })}
            disabled={disabled}
          >
            <SelectTrigger id="target-column">
              <SelectValue placeholder="Select target column" />
            </SelectTrigger>
            <SelectContent>
              {columns.map((col) => (
                <SelectItem key={col} value={col}>
                  {col}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            The column you want to predict
          </p>
        </div>

        {/* Selection Method */}
        <div className="space-y-2">
          <Label htmlFor="method">Selection Algorithm *</Label>
          <Select
            value={config.method}
            onValueChange={(value) => updateConfig({ method: value as SelectionMethod })}
            disabled={disabled}
          >
            <SelectTrigger id="method">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {METHODS.map((method) => (
                <SelectItem key={method} value={method}>
                  {getMethodName(method)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            {getMethodDescription(config.method)}
          </p>
          <p className="text-xs text-blue-600">
            {getMethodUseCase(config.method)}
          </p>
        </div>

        {/* Problem Type */}
        <div className="space-y-2">
          <Label htmlFor="problem-type">Problem Type</Label>
          <Select
            value={config.problemType || 'auto'}
            onValueChange={(value) =>
              updateConfig({
                problemType: value === 'auto' ? undefined : (value as ProblemType)
              })
            }
            disabled={disabled}
          >
            <SelectTrigger id="problem-type">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="auto">Auto-detect</SelectItem>
              <SelectItem value="classification">Classification</SelectItem>
              <SelectItem value="regression">Regression</SelectItem>
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            Auto-detect will analyze target column to determine problem type
          </p>
        </div>

        {/* Top K Features */}
        <div className="space-y-2">
          <Label htmlFor="top-k">Number of Features to Select</Label>
          <Input
            id="top-k"
            type="number"
            min="1"
            placeholder="e.g., 10"
            value={config.topK || ''}
            onChange={(e) =>
              updateConfig({
                topK: e.target.value ? parseInt(e.target.value) : undefined
              })
            }
            disabled={disabled}
          />
          <p className="text-xs text-muted-foreground">
            Leave empty to use threshold-based selection
          </p>
        </div>

        {/* Importance Threshold */}
        {!config.topK && (
          <div className="space-y-2">
            <Label htmlFor="threshold">
              Importance Threshold: {config.threshold?.toFixed(2) || '0.50'}
            </Label>
            <Slider
              id="threshold"
              min={0}
              max={1}
              step={0.05}
              value={[config.threshold || 0.5]}
              onValueChange={(value) => updateConfig({ threshold: value[0] })}
              disabled={disabled}
              className="py-4"
            />
            <p className="text-xs text-muted-foreground">
              Features with importance above this threshold will be selected
            </p>
          </div>
        )}

        {/* Correlation Threshold for Redundancy */}
        <div className="space-y-2">
          <Label htmlFor="correlation-threshold">
            Correlation Threshold: {config.correlationThreshold.toFixed(2)}
          </Label>
          <Slider
            id="correlation-threshold"
            min={0.5}
            max={1}
            step={0.05}
            value={[config.correlationThreshold]}
            onValueChange={(value) => updateConfig({ correlationThreshold: value[0] })}
            disabled={disabled}
            className="py-4"
          />
          <p className="text-xs text-muted-foreground">
            Features with correlation above this threshold are considered redundant
          </p>
        </div>

        {/* Sample Size for Large Datasets */}
        <div className="space-y-2">
          <Label htmlFor="sample-size">Sample Size (optional)</Label>
          <Input
            id="sample-size"
            type="number"
            min="100"
            placeholder="Leave empty to use full dataset"
            value={config.sampleSize || ''}
            onChange={(e) =>
              updateConfig({
                sampleSize: e.target.value ? parseInt(e.target.value) : undefined
              })
            }
            disabled={disabled}
          />
          <p className="text-xs text-muted-foreground">
            For very large datasets, sample a subset for faster processing
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex gap-3 pt-4">
          <Button
            onClick={onRunSelection}
            disabled={disabled || isLoading || !config.targetColumn}
            className="flex-1"
          >
            {isLoading ? 'Running Selection...' : 'Run Feature Selection'}
          </Button>
          <Button
            onClick={onCompare}
            variant="outline"
            disabled={disabled || isLoading || !config.targetColumn}
          >
            Compare Methods
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
