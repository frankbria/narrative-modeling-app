"use client";

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { SampleDatasetSelector } from '@/components/SampleDatasetSelector';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { HugeiconsIcon } from '@hugeicons/react';
import { ArrowRight01Icon, BookOpen01Icon, CheckmarkCircle01Icon, FileEditIcon, HelpCircleIcon, Loading03Icon, NextIcon, Target02Icon } from '@hugeicons/core-free-icons';

interface StepInfo {
  step_id: string;
  title: string;
  description: string;
  step_type: string;
  status: 'not_started' | 'in_progress' | 'completed' | 'skipped';
  order: number;
  is_required: boolean;
  is_skippable: boolean;
  estimated_duration: string;
  completion_criteria: string[];
  instructions: string[];
  help_text?: string;
  code_examples?: Array<{ title: string; code: string }>;
  completed_at?: string;
}

interface OnboardingStepProps {
  step: StepInfo;
  onComplete: (stepId: string, completionData?: Record<string, unknown>) => void;
  onSkip: (stepId: string) => void;
  isCompleting: boolean;
}

export function OnboardingStep({ step, onComplete, onSkip, isCompleting }: OnboardingStepProps) {
  const router = useRouter();
  const [showSamples, setShowSamples] = useState(false);
  const [completionData] = useState<Record<string, unknown>>({});

  const getStepTypeColor = (stepType: string) => {
    switch (stepType) {
      case 'welcome': return 'bg-primary/10 text-primary';
      case 'upload_data': return 'bg-success/10 text-success';
      case 'explore_data': return 'bg-primary/10 text-primary';
      case 'train_model': return 'bg-warning/10 text-warning';
      case 'make_predictions': return 'bg-primary/10 text-primary';
      case 'export_model': return 'bg-primary/10 text-primary';
      case 'completion': return 'bg-warning/10 text-warning';
      default: return 'bg-muted text-foreground';
    }
  };

  const handleComplete = () => {
    onComplete(step.step_id, completionData);
  };

  const renderStepContent = () => {
    switch (step.step_type) {
      case 'welcome':
        return (
          <div className="space-y-4">
            {/* Welcome-video placeholder removed (#281): no player or video
                content existed, so the "Watch Introduction" button was inert. */}
            <div className="prose dark:prose-invert max-w-none">
              <h3>Before you start</h3>
              <p>
                This walkthrough takes one spreadsheet from upload to a deployed model.
                Each step explains what it does to your data before it does it.
              </p>
              
              <h4>What makes us different:</h4>
              <ul>
                <li><strong>No Coding Required:</strong> Build models with clicks, not code</li>
                <li><strong>AutoML Technology:</strong> AI automatically finds the best algorithms</li>
                <li><strong>Production Ready:</strong> Export models for real-world use</li>
                <li><strong>Secure & Private:</strong> Your data is protected with enterprise security</li>
              </ul>
            </div>
          </div>
        );

      case 'upload_data':
        return (
          <div className="space-y-4">
            <Alert>
              <HugeiconsIcon icon={FileEditIcon} className="h-4 w-4" />
              <AlertDescription>
                Ready to upload your first dataset? We support CSV files with headers.
                Don&apos;t have data? Try our sample datasets below!
              </AlertDescription>
            </Alert>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Upload Your Data</CardTitle>
                  <CardDescription>
                    Have a CSV file ready? Upload it here to get started.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Button className="w-full" onClick={() => {
                    router.push('/upload');
                  }}>
                    <HugeiconsIcon icon={FileEditIcon} className="mr-2 h-4 w-4" />
                    Upload CSV File
                  </Button>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Try Sample Data</CardTitle>
                  <CardDescription>
                    New to ML? Start with our curated sample datasets.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Button
                    variant="outline"
                    className="w-full"
                    aria-expanded={showSamples}
                    onClick={() => setShowSamples((v) => !v)}
                  >
                    <HugeiconsIcon icon={Target02Icon} className="mr-2 h-4 w-4" />
                    Browse Samples
                  </Button>
                </CardContent>
              </Card>
            </div>

            {showSamples && (
              <SampleDatasetSelector
                onDatasetSelected={(datasetId) => {
                  // Load complete — advance to the newly created dataset.
                  router.push(`/explore/${datasetId}`);
                }}
              />
            )}

            {step.code_examples && (
              <div>
                <h4 className="font-medium mb-2">Expected CSV Format:</h4>
                <div className="bg-muted p-3 rounded-md font-mono text-sm">
                  <pre>{step.code_examples[0]?.code}</pre>
                </div>
              </div>
            )}
          </div>
        );

      case 'explore_data':
        return (
          <div className="space-y-4">
            <div className="prose dark:prose-invert max-w-none">
              <h3>Understand Your Data</h3>
              <p>
                Data exploration is crucial for building great models. Our platform 
                automatically analyzes your data and provides insights.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <Card>
                <CardContent className="pt-6">
                  <div className="text-center">
                    <h4 className="font-medium">Statistics</h4>
                    <p className="text-sm text-muted-foreground">
                      View summary statistics for all columns
                    </p>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="pt-6">
                  <div className="text-center">
                    <h4 className="font-medium">Quality Check</h4>
                    <p className="text-sm text-muted-foreground">
                      Identify missing values and outliers
                    </p>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="pt-6">
                  <div className="text-center">
                    <h4 className="font-medium">Visualizations</h4>
                    <p className="text-sm text-muted-foreground">
                      Create charts to understand patterns
                    </p>
                  </div>
                </CardContent>
              </Card>
            </div>

            <Button className="w-full" onClick={() => {
              router.push('/explore');
            }}>
              Explore Your Data
              <HugeiconsIcon icon={ArrowRight01Icon} className="ml-2 h-4 w-4" />
            </Button>
          </div>
        );

      case 'train_model':
        return (
          <div className="space-y-4">
            <div className="prose dark:prose-invert max-w-none">
              <h3>Train Your Model</h3>
              <p>
                This is where the magic happens! Our AutoML technology will:
              </p>
              <ul>
                <li>Automatically select the best algorithms for your data</li>
                <li>Optimize hyperparameters for peak performance</li>
                <li>Validate results using cross-validation</li>
                <li>Provide detailed performance metrics</li>
              </ul>
            </div>

            <Alert>
              <HugeiconsIcon icon={Loading03Icon} className="h-4 w-4" />
              <AlertDescription>
                Model training typically takes 2-5 minutes depending on your data size.
                Grab a coffee and watch the progress!
              </AlertDescription>
            </Alert>

            <Button className="w-full" onClick={() => {
              router.push('/model');
            }}>
              Start Training
              <HugeiconsIcon icon={ArrowRight01Icon} className="ml-2 h-4 w-4" />
            </Button>
          </div>
        );

      case 'make_predictions':
        return (
          <div className="space-y-4">
            <div className="prose dark:prose-invert max-w-none">
              <h3>Make Predictions</h3>
              <p>
                Now that your model is trained, it&apos;s time to put it to work! 
                You can make predictions on new data and see your model in action.
              </p>
            </div>

            <div className="bg-primary/10 p-4 rounded-lg">
              <h4 className="font-medium text-primary mb-2">What you&apos;ll see:</h4>
              <ul className="text-primary text-sm space-y-1">
                <li>• Prediction values for your inputs</li>
                <li>• Confidence scores showing model certainty</li>
                <li>• Feature importance rankings</li>
                <li>• Model performance metrics</li>
              </ul>
            </div>

            <Button className="w-full" onClick={() => {
              router.push('/predict');
            }}>
              Make Predictions
              <HugeiconsIcon icon={ArrowRight01Icon} className="ml-2 h-4 w-4" />
            </Button>
          </div>
        );

      case 'export_model':
        return (
          <div className="space-y-4">
            <div className="prose dark:prose-invert max-w-none">
              <h3>Export & Deploy</h3>
              <p>
                Ready to use your model in production? Export it in multiple 
                formats for different use cases.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Card>
                <CardContent className="pt-6">
                  <h4 className="font-medium mb-2">Python Code</h4>
                  <p className="text-sm text-muted-foreground mb-3">
                    Standalone Python class for integration
                  </p>
                  <Button variant="outline" size="sm" className="w-full">
                    Download Python
                  </Button>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="pt-6">
                  <h4 className="font-medium mb-2">Docker Container</h4>
                  <p className="text-sm text-muted-foreground mb-3">
                    Ready-to-deploy API container
                  </p>
                  <Button variant="outline" size="sm" className="w-full">
                    Download Docker
                  </Button>
                </CardContent>
              </Card>
            </div>
          </div>
        );

      default:
        return (
          <div className="prose dark:prose-invert max-w-none">
            <p>{step.description}</p>
          </div>
        );
    }
  };

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div>
              <CardTitle className="flex items-center gap-2">
                {step.title}
                <Badge variant="secondary" className={getStepTypeColor(step.step_type)}>
                  Step {step.order}
                </Badge>
              </CardTitle>
              <CardDescription className="mt-1">
                {step.description}
              </CardDescription>
            </div>
          </div>
          
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <HugeiconsIcon icon={Loading03Icon} className="h-4 w-4" />
            {step.estimated_duration}
          </div>
        </div>

        {step.status === 'completed' && (
          <Alert className="border-success/30 bg-success/10">
            <HugeiconsIcon icon={CheckmarkCircle01Icon} className="h-4 w-4 text-success" />
            <AlertDescription className="text-success">
              Step completed successfully!
            </AlertDescription>
          </Alert>
        )}
      </CardHeader>

      <CardContent className="space-y-6">
        <Tabs defaultValue="content" className="w-full">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="content">Content</TabsTrigger>
            <TabsTrigger value="instructions">Instructions</TabsTrigger>
            <TabsTrigger value="criteria">Criteria</TabsTrigger>
            <TabsTrigger value="help">Help</TabsTrigger>
          </TabsList>

          <TabsContent value="content" className="mt-6">
            {renderStepContent()}
          </TabsContent>

          <TabsContent value="instructions" className="mt-6 space-y-4">
            <h3 className="font-medium">Step-by-step instructions:</h3>
            <ol className="space-y-2">
              {step.instructions.map((instruction, index) => (
                <li key={index} className="flex gap-3">
                  <span className="flex-shrink-0 w-6 h-6 bg-primary/10 text-primary rounded-full flex items-center justify-center text-sm font-medium">
                    {index + 1}
                  </span>
                  <span>{instruction}</span>
                </li>
              ))}
            </ol>
          </TabsContent>

          <TabsContent value="criteria" className="mt-6 space-y-4">
            <h3 className="font-medium">Completion criteria:</h3>
            <ul className="space-y-2">
              {step.completion_criteria.map((criteria, index) => (
                <li key={index} className="flex items-start gap-2">
                  <HugeiconsIcon icon={Target02Icon} className="h-4 w-4 text-primary mt-0.5 flex-shrink-0" />
                  <span>{criteria}</span>
                </li>
              ))}
            </ul>
          </TabsContent>

          <TabsContent value="help" className="mt-6 space-y-4">
            {step.help_text && (
              <Alert>
                <HugeiconsIcon icon={HelpCircleIcon} className="h-4 w-4" />
                <AlertDescription>{step.help_text}</AlertDescription>
              </Alert>
            )}

            {step.code_examples && (
              <div>
                <h4 className="font-medium mb-2">Code Examples:</h4>
                {step.code_examples.map((example, index) => (
                  <div key={index} className="mb-4">
                    <h5 className="text-sm font-medium mb-1">{example.title}</h5>
                    <div className="bg-muted p-3 rounded-md">
                      <pre className="text-sm font-mono">{example.code}</pre>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* "Watch Tutorial" button removed (#281): no tutorial video
                existed. Documentation link points to the real /quickstart. */}
            <div className="grid grid-cols-1 gap-4">
              <Button asChild variant="outline" className="w-full">
                <Link href="/quickstart">
                  <HugeiconsIcon icon={BookOpen01Icon} className="mr-2 h-4 w-4" />
                  View Documentation
                </Link>
              </Button>
            </div>
          </TabsContent>
        </Tabs>

        {/* Action Buttons */}
        <div className="flex flex-col sm:flex-row gap-3 pt-4 border-t">
          {step.status !== 'completed' && (
            <>
              <Button 
                onClick={handleComplete}
                disabled={isCompleting}
                className="flex-1"
              >
                {isCompleting ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2" />
                    Completing...
                  </>
                ) : (
                  <>
                    <HugeiconsIcon icon={CheckmarkCircle01Icon} className="mr-2 h-4 w-4" />
                    Mark as Complete
                  </>
                )}
              </Button>

              {step.is_skippable && (
                <Button 
                  variant="outline" 
                  onClick={() => onSkip(step.step_id)}
                  disabled={isCompleting}
                >
                  <HugeiconsIcon icon={NextIcon} className="mr-2 h-4 w-4" />
                  Skip Step
                </Button>
              )}
            </>
          )}

          {step.status === 'completed' && (
            <Button variant="outline" className="flex-1" disabled>
              <HugeiconsIcon icon={CheckmarkCircle01Icon} className="mr-2 h-4 w-4 text-success" />
              Completed
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}