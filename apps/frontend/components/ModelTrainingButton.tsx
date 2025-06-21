'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { Slider } from '@/components/ui/slider'
import { Brain, Loader2 } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { ModelService, TrainModelRequest } from '@/lib/services/model'
import { useAuth } from '@clerk/nextjs'
import { Alert, AlertDescription } from '@/components/ui/alert'

interface ModelTrainingButtonProps {
  datasetId: string
  columns: string[]
  onTrainingStarted?: () => void
}

export function ModelTrainingButton({
  datasetId,
  columns,
  onTrainingStarted
}: ModelTrainingButtonProps) {
  const [open, setOpen] = useState(false)
  const [isTraining, setIsTraining] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { getToken } = useAuth()
  const router = useRouter()

  // Form state
  const [targetColumn, setTargetColumn] = useState('')
  const [modelName, setModelName] = useState('')
  const [description, setDescription] = useState('')
  
  // Feature engineering config
  const [handleMissing, setHandleMissing] = useState(true)
  const [scaleFeatures, setScaleFeatures] = useState(true)
  const [encodeCategorical, setEncodeCategorical] = useState(true)
  const [createInteractions, setCreateInteractions] = useState(false)
  const [selectFeatures, setSelectFeatures] = useState(true)
  const [maxFeatures, setMaxFeatures] = useState([50])
  
  // Training config
  const [maxModels, setMaxModels] = useState([5])
  const [cvFolds, setCvFolds] = useState([5])
  const [testSize, setTestSize] = useState([0.2])

  const handleTrain = async () => {
    if (!targetColumn) {
      setError('Please select a target column')
      return
    }

    setIsTraining(true)
    setError(null)

    try {
      const token = await getToken()
      
      const request: TrainModelRequest = {
        dataset_id: datasetId,
        target_column: targetColumn,
        name: modelName || `Model for ${targetColumn}`,
        description: description || undefined,
        feature_config: {
          handle_missing: handleMissing,
          scale_features: scaleFeatures,
          encode_categorical: encodeCategorical,
          create_interactions: createInteractions,
          select_features: selectFeatures,
          max_features: selectFeatures ? maxFeatures[0] : undefined
        },
        training_config: {
          max_models: maxModels[0],
          cv_folds: cvFolds[0],
          test_size: testSize[0]
        }
      }

      const response = await ModelService.trainModel(request, token)
      
      // Close dialog and redirect to models page
      setOpen(false)
      onTrainingStarted?.()
      
      // Show success message and redirect
      router.push('/model')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start training')
    } finally {
      setIsTraining(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button className="gap-2">
          <Brain className="h-4 w-4" />
          Train Model
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Train Machine Learning Model</DialogTitle>
          <DialogDescription>
            Configure and train a model on your dataset using AutoML
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* Basic Configuration */}
          <div className="space-y-4">
            <h3 className="text-sm font-medium">Basic Configuration</h3>
            
            <div className="space-y-2">
              <Label htmlFor="target">Target Column *</Label>
              <Select value={targetColumn} onValueChange={setTargetColumn}>
                <SelectTrigger id="target">
                  <SelectValue placeholder="Select column to predict" />
                </SelectTrigger>
                <SelectContent>
                  {columns.map((col) => (
                    <SelectItem key={col} value={col}>
                      {col}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="name">Model Name</Label>
              <Input
                id="name"
                value={modelName}
                onChange={(e) => setModelName(e.target.value)}
                placeholder="My Prediction Model"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe what this model predicts..."
                rows={3}
              />
            </div>
          </div>

          {/* Feature Engineering */}
          <div className="space-y-4">
            <h3 className="text-sm font-medium">Feature Engineering</h3>
            
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label htmlFor="handle-missing">Handle Missing Values</Label>
                <Switch
                  id="handle-missing"
                  checked={handleMissing}
                  onCheckedChange={setHandleMissing}
                />
              </div>

              <div className="flex items-center justify-between">
                <Label htmlFor="scale">Scale Features</Label>
                <Switch
                  id="scale"
                  checked={scaleFeatures}
                  onCheckedChange={setScaleFeatures}
                />
              </div>

              <div className="flex items-center justify-between">
                <Label htmlFor="encode">Encode Categories</Label>
                <Switch
                  id="encode"
                  checked={encodeCategorical}
                  onCheckedChange={setEncodeCategorical}
                />
              </div>

              <div className="flex items-center justify-between">
                <Label htmlFor="interactions">Create Interactions</Label>
                <Switch
                  id="interactions"
                  checked={createInteractions}
                  onCheckedChange={setCreateInteractions}
                />
              </div>

              <div className="flex items-center justify-between">
                <Label htmlFor="select-features">Feature Selection</Label>
                <Switch
                  id="select-features"
                  checked={selectFeatures}
                  onCheckedChange={setSelectFeatures}
                />
              </div>

              {selectFeatures && (
                <div className="space-y-2">
                  <Label>Max Features: {maxFeatures[0]}</Label>
                  <Slider
                    value={maxFeatures}
                    onValueChange={setMaxFeatures}
                    min={10}
                    max={100}
                    step={10}
                  />
                </div>
              )}
            </div>
          </div>

          {/* Training Configuration */}
          <div className="space-y-4">
            <h3 className="text-sm font-medium">Training Configuration</h3>
            
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>Models to Train: {maxModels[0]}</Label>
                <Slider
                  value={maxModels}
                  onValueChange={setMaxModels}
                  min={1}
                  max={10}
                  step={1}
                />
              </div>

              <div className="space-y-2">
                <Label>Cross-Validation Folds: {cvFolds[0]}</Label>
                <Slider
                  value={cvFolds}
                  onValueChange={setCvFolds}
                  min={3}
                  max={10}
                  step={1}
                />
              </div>

              <div className="space-y-2">
                <Label>Test Set Size: {Math.round(testSize[0] * 100)}%</Label>
                <Slider
                  value={testSize}
                  onValueChange={setTestSize}
                  min={0.1}
                  max={0.4}
                  step={0.05}
                />
              </div>
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-4 border-t">
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button onClick={handleTrain} disabled={isTraining || !targetColumn}>
            {isTraining ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Starting Training...
              </>
            ) : (
              'Start Training'
            )}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}