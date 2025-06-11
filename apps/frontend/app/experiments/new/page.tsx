"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { ArrowLeft, Plus, Trash2, AlertCircle } from "lucide-react";
import { abTestingService, CreateExperimentRequest } from "@/lib/services/abTesting";
import { modelService } from "@/lib/services/model";

interface VariantConfig {
  modelId: string;
  name: string;
  trafficPercentage: number;
}

export default function NewExperimentPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [models, setModels] = useState<any[]>([]);
  const [error, setError] = useState("");

  // Form state
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [primaryMetric, setPrimaryMetric] = useState("accuracy");
  const [variants, setVariants] = useState<VariantConfig[]>([
    { modelId: "", name: "Control", trafficPercentage: 50 },
    { modelId: "", name: "Treatment A", trafficPercentage: 50 },
  ]);
  const [minSampleSize, setMinSampleSize] = useState(1000);
  const [confidenceLevel, setConfidenceLevel] = useState(95);
  const [enableDuration, setEnableDuration] = useState(false);
  const [testDurationHours, setTestDurationHours] = useState(168); // 7 days

  useEffect(() => {
    loadModels();
  }, []);

  const loadModels = async () => {
    try {
      const data = await modelService.listModels();
      // Filter only active models
      setModels(data.filter((model: any) => model.is_active));
    } catch (error) {
      console.error("Failed to load models:", error);
      setError("Failed to load models");
    }
  };

  const addVariant = () => {
    const newVariant: VariantConfig = {
      modelId: "",
      name: `Treatment ${String.fromCharCode(65 + variants.length - 1)}`,
      trafficPercentage: 0,
    };
    setVariants([...variants, newVariant]);
    redistributeTraffic([...variants, newVariant]);
  };

  const removeVariant = (index: number) => {
    const newVariants = variants.filter((_, i) => i !== index);
    setVariants(newVariants);
    redistributeTraffic(newVariants);
  };

  const updateVariant = (index: number, updates: Partial<VariantConfig>) => {
    const newVariants = [...variants];
    newVariants[index] = { ...newVariants[index], ...updates };
    setVariants(newVariants);
  };

  const redistributeTraffic = (variantList: VariantConfig[]) => {
    if (variantList.length === 0) return;
    
    const equalTraffic = 100 / variantList.length;
    const newVariants = variantList.map(v => ({
      ...v,
      trafficPercentage: parseFloat(equalTraffic.toFixed(1)),
    }));
    
    // Adjust for rounding errors
    const total = newVariants.reduce((sum, v) => sum + v.trafficPercentage, 0);
    if (total !== 100) {
      newVariants[0].trafficPercentage += 100 - total;
    }
    
    setVariants(newVariants);
  };

  const handleTrafficChange = (index: number, value: number) => {
    const newVariants = [...variants];
    newVariants[index].trafficPercentage = value;
    
    // Redistribute remaining traffic among other variants
    const totalOthers = 100 - value;
    const otherCount = variants.length - 1;
    
    if (otherCount > 0) {
      const perOther = totalOthers / otherCount;
      newVariants.forEach((v, i) => {
        if (i !== index) {
          v.trafficPercentage = parseFloat(perOther.toFixed(1));
        }
      });
    }
    
    setVariants(newVariants);
  };

  const totalTraffic = variants.reduce((sum, v) => sum + v.trafficPercentage, 0);
  const isValidTraffic = Math.abs(totalTraffic - 100) < 0.1;

  const handleSubmit = async () => {
    // Validation
    if (!name.trim()) {
      setError("Experiment name is required");
      return;
    }

    if (variants.some(v => !v.modelId)) {
      setError("Please select a model for each variant");
      return;
    }

    if (!isValidTraffic) {
      setError("Traffic percentages must sum to 100%");
      return;
    }

    // Check for duplicate models
    const modelIds = variants.map(v => v.modelId);
    if (new Set(modelIds).size !== modelIds.length) {
      setError("Each variant must use a different model");
      return;
    }

    try {
      setLoading(true);
      setError("");

      const request: CreateExperimentRequest = {
        name,
        description: description || undefined,
        model_ids: variants.map(v => v.modelId),
        primary_metric: primaryMetric,
        traffic_split: variants.map(v => v.trafficPercentage),
        min_sample_size: minSampleSize,
        confidence_level: confidenceLevel / 100,
        test_duration_hours: enableDuration ? testDurationHours : undefined,
      };

      const experiment = await abTestingService.createExperiment(request);
      router.push(`/experiments/${experiment.experiment_id}`);
    } catch (error) {
      console.error("Failed to create experiment:", error);
      setError("Failed to create experiment");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => router.push("/experiments")}
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-3xl font-bold">Create New Experiment</h1>
          <p className="text-muted-foreground mt-1">
            Set up an A/B test to compare model performance
          </p>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Basic Information */}
      <Card>
        <CardHeader>
          <CardTitle>Basic Information</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Experiment Name</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Homepage Recommendation Model Test"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">Description (Optional)</Label>
            <Textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe the purpose and hypothesis of this experiment..."
              rows={3}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="metric">Primary Metric</Label>
            <Select value={primaryMetric} onValueChange={setPrimaryMetric}>
              <SelectTrigger id="metric">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="accuracy">Accuracy</SelectItem>
                <SelectItem value="precision">Precision</SelectItem>
                <SelectItem value="recall">Recall</SelectItem>
                <SelectItem value="f1_score">F1 Score</SelectItem>
                <SelectItem value="error_rate">Error Rate</SelectItem>
                <SelectItem value="avg_latency">Average Latency</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Variants Configuration */}
      <Card>
        <CardHeader>
          <CardTitle>Variants</CardTitle>
          <CardDescription>
            Configure the models to test and their traffic allocation
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {variants.map((variant, index) => (
            <Card key={index}>
              <CardContent className="p-4 space-y-4">
                <div className="flex items-center justify-between">
                  <h4 className="font-medium">{variant.name}</h4>
                  {variants.length > 2 && (
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => removeVariant(index)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>

                <div className="space-y-2">
                  <Label>Model</Label>
                  <Select
                    value={variant.modelId}
                    onValueChange={(value) => updateVariant(index, { modelId: value })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select a model" />
                    </SelectTrigger>
                    <SelectContent>
                      {models.map((model) => (
                        <SelectItem 
                          key={model.model_id} 
                          value={model.model_id}
                          disabled={variants.some(v => v.modelId === model.model_id && v !== variant)}
                        >
                          {model.name} (v{model.version})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <div className="flex justify-between">
                    <Label>Traffic Percentage</Label>
                    <span className="text-sm font-medium">
                      {variant.trafficPercentage.toFixed(1)}%
                    </span>
                  </div>
                  <Slider
                    value={[variant.trafficPercentage]}
                    onValueChange={([value]) => handleTrafficChange(index, value)}
                    min={0}
                    max={100}
                    step={0.1}
                  />
                </div>
              </CardContent>
            </Card>
          ))}

          <Button
            variant="outline"
            onClick={addVariant}
            className="w-full"
            disabled={variants.length >= models.length}
          >
            <Plus className="h-4 w-4 mr-2" />
            Add Variant
          </Button>

          {!isValidTraffic && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                Traffic percentages must sum to 100% (currently {totalTraffic.toFixed(1)}%)
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Test Settings */}
      <Card>
        <CardHeader>
          <CardTitle>Test Settings</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="sample-size">Minimum Sample Size per Variant</Label>
            <Input
              id="sample-size"
              type="number"
              value={minSampleSize}
              onChange={(e) => setMinSampleSize(parseInt(e.target.value) || 0)}
              min={100}
              step={100}
            />
            <p className="text-sm text-muted-foreground">
              The experiment will need at least this many predictions per variant
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="confidence">Confidence Level</Label>
            <div className="flex items-center gap-2">
              <Slider
                id="confidence"
                value={[confidenceLevel]}
                onValueChange={([value]) => setConfidenceLevel(value)}
                min={80}
                max={99}
                step={1}
              />
              <span className="w-12 text-sm font-medium">{confidenceLevel}%</span>
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="duration-toggle">Set Maximum Duration</Label>
              <Switch
                id="duration-toggle"
                checked={enableDuration}
                onCheckedChange={setEnableDuration}
              />
            </div>
            {enableDuration && (
              <div className="space-y-2">
                <Input
                  type="number"
                  value={testDurationHours}
                  onChange={(e) => setTestDurationHours(parseInt(e.target.value) || 0)}
                  min={1}
                  step={24}
                />
                <p className="text-sm text-muted-foreground">
                  Maximum test duration in hours ({(testDurationHours / 24).toFixed(1)} days)
                </p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Actions */}
      <div className="flex justify-end gap-4">
        <Button
          variant="outline"
          onClick={() => router.push("/experiments")}
        >
          Cancel
        </Button>
        <Button
          onClick={handleSubmit}
          disabled={loading || !isValidTraffic}
        >
          {loading ? "Creating..." : "Create Experiment"}
        </Button>
      </div>
    </div>
  );
}