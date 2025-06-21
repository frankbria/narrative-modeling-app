"use client";

import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  CheckCircle, 
  Play, 
  Skip, 
  Clock, 
  BookOpen, 
  Video,
  Code,
  ArrowRight,
  ArrowLeft,
  HelpCircle,
  Target,
  FileText
} from 'lucide-react';

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
  video_url?: string;
  completed_at?: string;
}

interface OnboardingStepProps {
  step: StepInfo;
  onComplete: (stepId: string, completionData?: any) => void;
  onSkip: (stepId: string) => void;
  isCompleting: boolean;
}

export function OnboardingStep({ step, onComplete, onSkip, isCompleting }: OnboardingStepProps) {
  const [showDetails, setShowDetails] = useState(false);
  const [completionData, setCompletionData] = useState<any>({});

  const getStepTypeColor = (stepType: string) => {
    switch (stepType) {
      case 'welcome': return 'bg-blue-100 text-blue-800';
      case 'upload_data': return 'bg-green-100 text-green-800';
      case 'explore_data': return 'bg-purple-100 text-purple-800';
      case 'train_model': return 'bg-orange-100 text-orange-800';
      case 'make_predictions': return 'bg-red-100 text-red-800';
      case 'export_model': return 'bg-indigo-100 text-indigo-800';
      case 'completion': return 'bg-yellow-100 text-yellow-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getStepTypeIcon = (stepType: string) => {
    switch (stepType) {
      case 'welcome': return '👋';
      case 'upload_data': return '📁';
      case 'explore_data': return '🔍';
      case 'train_model': return '🤖';
      case 'make_predictions': return '🎯';
      case 'export_model': return '📦';
      case 'completion': return '🎉';
      default: return '📋';
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
            {step.video_url && (
              <div className="aspect-video bg-gray-100 rounded-lg flex items-center justify-center">
                <div className="text-center">
                  <Video className="h-12 w-12 mx-auto mb-2 text-gray-400" />
                  <p className="text-gray-600">Welcome Video</p>
                  <Button variant="outline" className="mt-2">
                    <Play className="mr-2 h-4 w-4" />
                    Watch Introduction
                  </Button>
                </div>
              </div>
            )}
            
            <div className="prose max-w-none">
              <h3>Welcome to the Platform! 🚀</h3>
              <p>
                You're about to discover how easy it is to build machine learning models 
                without any coding experience. Our AI-powered platform will guide you 
                through every step of the process.
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
              <FileText className="h-4 w-4" />
              <AlertDescription>
                Ready to upload your first dataset? We support CSV files with headers.
                Don't have data? Try our sample datasets below!
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
                    // Navigate to upload page
                    window.location.href = '/load';
                  }}>
                    <FileText className="mr-2 h-4 w-4" />
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
                  <Button variant="outline" className="w-full" onClick={() => {
                    // Show sample data selector
                    setShowDetails(true);
                  }}>
                    <Target className="mr-2 h-4 w-4" />
                    Browse Samples
                  </Button>
                </CardContent>
              </Card>
            </div>

            {step.code_examples && (
              <div>
                <h4 className="font-medium mb-2">Expected CSV Format:</h4>
                <div className="bg-gray-50 p-3 rounded-md font-mono text-sm">
                  <pre>{step.code_examples[0]?.code}</pre>
                </div>
              </div>
            )}
          </div>
        );

      case 'explore_data':
        return (
          <div className="space-y-4">
            <div className="prose max-w-none">
              <h3>Understand Your Data 📊</h3>
              <p>
                Data exploration is crucial for building great models. Our platform 
                automatically analyzes your data and provides insights.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <Card>
                <CardContent className="pt-6">
                  <div className="text-center">
                    <div className="text-2xl mb-2">📈</div>
                    <h4 className="font-medium">Statistics</h4>
                    <p className="text-sm text-gray-600">
                      View summary statistics for all columns
                    </p>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="pt-6">
                  <div className="text-center">
                    <div className="text-2xl mb-2">🔍</div>
                    <h4 className="font-medium">Quality Check</h4>
                    <p className="text-sm text-gray-600">
                      Identify missing values and outliers
                    </p>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="pt-6">
                  <div className="text-center">
                    <div className="text-2xl mb-2">📊</div>
                    <h4 className="font-medium">Visualizations</h4>
                    <p className="text-sm text-gray-600">
                      Create charts to understand patterns
                    </p>
                  </div>
                </CardContent>
              </Card>
            </div>

            <Button className="w-full" onClick={() => {
              // Navigate to explore page
              window.location.href = '/explore';
            }}>
              Explore Your Data
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </div>
        );

      case 'train_model':
        return (
          <div className="space-y-4">
            <div className="prose max-w-none">
              <h3>Train Your Model 🤖</h3>
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
              <Clock className="h-4 w-4" />
              <AlertDescription>
                Model training typically takes 2-5 minutes depending on your data size.
                Grab a coffee and watch the progress!
              </AlertDescription>
            </Alert>

            <Button className="w-full" onClick={() => {
              // Navigate to model training
              window.location.href = '/model';
            }}>
              Start Training
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </div>
        );

      case 'make_predictions':
        return (
          <div className="space-y-4">
            <div className="prose max-w-none">
              <h3>Make Predictions 🎯</h3>
              <p>
                Now that your model is trained, it's time to put it to work! 
                You can make predictions on new data and see your model in action.
              </p>
            </div>

            <div className="bg-blue-50 p-4 rounded-lg">
              <h4 className="font-medium text-blue-900 mb-2">What you'll see:</h4>
              <ul className="text-blue-800 text-sm space-y-1">
                <li>• Prediction values for your inputs</li>
                <li>• Confidence scores showing model certainty</li>
                <li>• Feature importance rankings</li>
                <li>• Model performance metrics</li>
              </ul>
            </div>

            <Button className="w-full" onClick={() => {
              // Navigate to predictions
              window.location.href = '/predict';
            }}>
              Make Predictions
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </div>
        );

      case 'export_model':
        return (
          <div className="space-y-4">
            <div className="prose max-w-none">
              <h3>Export & Deploy 📦</h3>
              <p>
                Ready to use your model in production? Export it in multiple 
                formats for different use cases.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Card>
                <CardContent className="pt-6">
                  <h4 className="font-medium mb-2">🐍 Python Code</h4>
                  <p className="text-sm text-gray-600 mb-3">
                    Standalone Python class for integration
                  </p>
                  <Button variant="outline" size="sm" className="w-full">
                    Download Python
                  </Button>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="pt-6">
                  <h4 className="font-medium mb-2">🐳 Docker Container</h4>
                  <p className="text-sm text-gray-600 mb-3">
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
          <div className="prose max-w-none">
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
            <div className="text-2xl">{getStepTypeIcon(step.step_type)}</div>
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
          
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Clock className="h-4 w-4" />
            {step.estimated_duration}
          </div>
        </div>

        {step.status === 'completed' && (
          <Alert className="border-green-200 bg-green-50">
            <CheckCircle className="h-4 w-4 text-green-600" />
            <AlertDescription className="text-green-800">
              ✅ Step completed successfully!
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
                  <span className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-800 rounded-full flex items-center justify-center text-sm font-medium">
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
                  <Target className="h-4 w-4 text-blue-500 mt-0.5 flex-shrink-0" />
                  <span>{criteria}</span>
                </li>
              ))}
            </ul>
          </TabsContent>

          <TabsContent value="help" className="mt-6 space-y-4">
            {step.help_text && (
              <Alert>
                <HelpCircle className="h-4 w-4" />
                <AlertDescription>{step.help_text}</AlertDescription>
              </Alert>
            )}

            {step.code_examples && (
              <div>
                <h4 className="font-medium mb-2">Code Examples:</h4>
                {step.code_examples.map((example, index) => (
                  <div key={index} className="mb-4">
                    <h5 className="text-sm font-medium mb-1">{example.title}</h5>
                    <div className="bg-gray-50 p-3 rounded-md">
                      <pre className="text-sm font-mono">{example.code}</pre>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Button variant="outline" className="w-full">
                <BookOpen className="mr-2 h-4 w-4" />
                View Documentation
              </Button>
              <Button variant="outline" className="w-full">
                <Video className="mr-2 h-4 w-4" />
                Watch Tutorial
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
                    <CheckCircle className="mr-2 h-4 w-4" />
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
                  <Skip className="mr-2 h-4 w-4" />
                  Skip Step
                </Button>
              )}
            </>
          )}

          {step.status === 'completed' && (
            <Button variant="outline" className="flex-1" disabled>
              <CheckCircle className="mr-2 h-4 w-4 text-green-600" />
              Completed
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}