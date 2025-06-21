"use client";

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { 
  ArrowRight, 
  ArrowLeft, 
  CheckCircle, 
  Play, 
  Pause,
  RotateCcw,
  Lightbulb,
  Target,
  Eye,
  MousePointer,
  Keyboard
} from 'lucide-react';

interface TutorialStep {
  id: string;
  title: string;
  description: string;
  action: 'click' | 'type' | 'navigate' | 'wait' | 'observe';
  target?: string; // CSS selector for highlighting
  content: string;
  tip?: string;
  validation?: () => boolean;
  autoAdvance?: boolean;
  duration?: number; // for wait steps
}

interface InteractiveTutorialProps {
  steps: TutorialStep[];
  onComplete: () => void;
  onStepComplete?: (stepId: string) => void;
  autoStart?: boolean;
}

export function InteractiveTutorial({ 
  steps, 
  onComplete, 
  onStepComplete,
  autoStart = false 
}: InteractiveTutorialProps) {
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [isActive, setIsActive] = useState(autoStart);
  const [completedSteps, setCompletedSteps] = useState<Set<string>>(new Set());
  const [isHighlighting, setIsHighlighting] = useState(false);

  const currentStep = steps[currentStepIndex];
  const progress = (currentStepIndex / steps.length) * 100;

  useEffect(() => {
    if (isActive && currentStep?.target) {
      highlightElement(currentStep.target);
    } else {
      removeHighlight();
    }

    return () => removeHighlight();
  }, [currentStepIndex, isActive, currentStep]);

  useEffect(() => {
    if (currentStep?.autoAdvance && currentStep.duration) {
      const timer = setTimeout(() => {
        nextStep();
      }, currentStep.duration);

      return () => clearTimeout(timer);
    }
  }, [currentStepIndex, currentStep]);

  const highlightElement = (selector: string) => {
    removeHighlight();
    
    const element = document.querySelector(selector);
    if (element) {
      setIsHighlighting(true);
      
      // Create overlay
      const overlay = document.createElement('div');
      overlay.id = 'tutorial-overlay';
      overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        background: rgba(0, 0, 0, 0.5);
        z-index: 9998;
        pointer-events: none;
      `;
      
      // Create highlight box
      const rect = element.getBoundingClientRect();
      const highlight = document.createElement('div');
      highlight.id = 'tutorial-highlight';
      highlight.style.cssText = `
        position: fixed;
        top: ${rect.top - 4}px;
        left: ${rect.left - 4}px;
        width: ${rect.width + 8}px;
        height: ${rect.height + 8}px;
        border: 3px solid #3b82f6;
        border-radius: 8px;
        box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.3);
        z-index: 9999;
        pointer-events: none;
        animation: pulse 2s infinite;
      `;

      // Add pulse animation
      const style = document.createElement('style');
      style.textContent = `
        @keyframes pulse {
          0%, 100% { box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.3); }
          50% { box-shadow: 0 0 0 8px rgba(59, 130, 246, 0.1); }
        }
      `;
      document.head.appendChild(style);
      
      document.body.appendChild(overlay);
      document.body.appendChild(highlight);

      // Scroll element into view
      element.scrollIntoView({ 
        behavior: 'smooth', 
        block: 'center' 
      });
    }
  };

  const removeHighlight = () => {
    const overlay = document.getElementById('tutorial-overlay');
    const highlight = document.getElementById('tutorial-highlight');
    
    if (overlay) overlay.remove();
    if (highlight) highlight.remove();
    
    setIsHighlighting(false);
  };

  const nextStep = () => {
    if (currentStep) {
      const newCompleted = new Set(completedSteps);
      newCompleted.add(currentStep.id);
      setCompletedSteps(newCompleted);
      
      onStepComplete?.(currentStep.id);
    }

    if (currentStepIndex < steps.length - 1) {
      setCurrentStepIndex(currentStepIndex + 1);
    } else {
      // Tutorial complete
      setIsActive(false);
      removeHighlight();
      onComplete();
    }
  };

  const prevStep = () => {
    if (currentStepIndex > 0) {
      setCurrentStepIndex(currentStepIndex - 1);
    }
  };

  const startTutorial = () => {
    setIsActive(true);
    setCurrentStepIndex(0);
    setCompletedSteps(new Set());
  };

  const pauseTutorial = () => {
    setIsActive(false);
    removeHighlight();
  };

  const resetTutorial = () => {
    setIsActive(false);
    setCurrentStepIndex(0);
    setCompletedSteps(new Set());
    removeHighlight();
  };

  const getActionIcon = (action: string) => {
    switch (action) {
      case 'click': return <MousePointer className="h-4 w-4" />;
      case 'type': return <Keyboard className="h-4 w-4" />;
      case 'navigate': return <ArrowRight className="h-4 w-4" />;
      case 'wait': return <Pause className="h-4 w-4" />;
      case 'observe': return <Eye className="h-4 w-4" />;
      default: return <Target className="h-4 w-4" />;
    }
  };

  const getActionText = (action: string) => {
    switch (action) {
      case 'click': return 'Click';
      case 'type': return 'Type';
      case 'navigate': return 'Navigate';
      case 'wait': return 'Wait';
      case 'observe': return 'Observe';
      default: return 'Action';
    }
  };

  if (!isActive) {
    return (
      <Card className="fixed bottom-4 right-4 w-80 z-50 shadow-lg">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Lightbulb className="h-5 w-5 text-yellow-500" />
            Interactive Tutorial
          </CardTitle>
          <CardDescription>
            Get guided help for this page
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="text-sm text-gray-600">
            {completedSteps.size > 0 ? (
              <span>Progress: {completedSteps.size} of {steps.length} steps completed</span>
            ) : (
              <span>Learn how to use this feature step-by-step</span>
            )}
          </div>
          
          <div className="flex gap-2">
            <Button onClick={startTutorial} className="flex-1">
              <Play className="mr-2 h-4 w-4" />
              {completedSteps.size > 0 ? 'Continue' : 'Start'}
            </Button>
            
            {completedSteps.size > 0 && (
              <Button variant="outline" onClick={resetTutorial}>
                <RotateCcw className="h-4 w-4" />
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="fixed bottom-4 right-4 w-96 z-50 shadow-lg">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Badge variant="secondary" className="bg-blue-100 text-blue-800">
              Step {currentStepIndex + 1} of {steps.length}
            </Badge>
          </CardTitle>
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={pauseTutorial}
          >
            <Pause className="h-4 w-4" />
          </Button>
        </div>
        
        <Progress value={progress} className="h-2" />
      </CardHeader>

      <CardContent className="space-y-4">
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="flex items-center gap-1">
              {getActionIcon(currentStep.action)}
              {getActionText(currentStep.action)}
            </Badge>
            <h3 className="font-medium">{currentStep.title}</h3>
          </div>

          <p className="text-sm text-gray-700">
            {currentStep.content}
          </p>

          {currentStep.tip && (
            <Alert className="border-blue-200 bg-blue-50">
              <Lightbulb className="h-4 w-4 text-blue-600" />
              <AlertDescription className="text-blue-800">
                💡 <strong>Tip:</strong> {currentStep.tip}
              </AlertDescription>
            </Alert>
          )}
        </div>

        <div className="flex items-center justify-between pt-2 border-t">
          <Button 
            variant="outline" 
            size="sm"
            onClick={prevStep}
            disabled={currentStepIndex === 0}
          >
            <ArrowLeft className="mr-1 h-4 w-4" />
            Back
          </Button>

          <div className="flex gap-1">
            {steps.map((_, index) => (
              <div 
                key={index}
                className={`w-2 h-2 rounded-full ${
                  index < currentStepIndex 
                    ? 'bg-green-500' 
                    : index === currentStepIndex 
                      ? 'bg-blue-500' 
                      : 'bg-gray-200'
                }`} 
              />
            ))}
          </div>

          <Button 
            size="sm"
            onClick={nextStep}
          >
            {currentStepIndex === steps.length - 1 ? (
              <>
                <CheckCircle className="mr-1 h-4 w-4" />
                Finish
              </>
            ) : (
              <>
                Next
                <ArrowRight className="ml-1 h-4 w-4" />
              </>
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// Pre-built tutorial for common flows
export const uploadDataTutorial: TutorialStep[] = [
  {
    id: 'welcome',
    title: 'Welcome to Data Upload',
    description: 'File upload tutorial',
    action: 'observe',
    content: 'Let me show you how to upload your first dataset. This process is secure and supports CSV files up to 100MB.',
    tip: 'Make sure your CSV file has column headers in the first row.',
    autoAdvance: true,
    duration: 3000
  },
  {
    id: 'select-file',
    title: 'Select Your File',
    description: 'Click to browse files',
    action: 'click',
    target: 'input[type="file"]',
    content: 'Click this button to browse and select your CSV file from your computer.',
    tip: 'You can also drag and drop files directly onto the upload area.'
  },
  {
    id: 'upload-progress',
    title: 'Upload Progress',
    description: 'Watch the upload',
    action: 'observe',
    content: 'Once you select a file, you\'ll see the upload progress here. The system automatically scans for data quality issues.',
    tip: 'Large files may take a few minutes. The progress bar shows both upload and processing status.'
  },
  {
    id: 'review-results',
    title: 'Review Upload Results',
    description: 'Check data summary',
    action: 'observe',
    content: 'After upload, review the data summary to ensure everything looks correct. Check the column types and sample data.',
    tip: 'If something looks wrong, you can upload a different file or contact support.'
  }
];

export const exploreDataTutorial: TutorialStep[] = [
  {
    id: 'data-overview',
    title: 'Data Overview',
    description: 'Understand your dataset',
    action: 'observe',
    content: 'This overview shows key statistics about your dataset: number of rows, columns, data types, and missing values.',
    tip: 'Pay attention to missing values - they can affect model performance.'
  },
  {
    id: 'column-stats',
    title: 'Column Statistics',
    description: 'Explore individual columns',
    action: 'click',
    target: '[data-testid="column-stats"]',
    content: 'Click on any column to see detailed statistics, distribution charts, and identify potential issues.',
    tip: 'Look for outliers and unusual patterns that might need attention.'
  },
  {
    id: 'visualizations',
    title: 'Create Visualizations',
    description: 'Build charts',
    action: 'click',
    target: '[data-testid="create-chart"]',
    content: 'Create charts to understand relationships between variables. This helps you choose the right features for modeling.',
    tip: 'Start with scatter plots and histograms to understand your data distribution.'
  }
];

export const trainModelTutorial: TutorialStep[] = [
  {
    id: 'choose-target',
    title: 'Select Target Column',
    description: 'What to predict',
    action: 'click',
    target: '[data-testid="target-selector"]',
    content: 'Choose the column you want to predict. This is your target variable - what the model will learn to predict.',
    tip: 'The target should be what you want to predict for new data.'
  },
  {
    id: 'problem-type',
    title: 'Choose Problem Type',
    description: 'Classification or Regression',
    action: 'observe',
    content: 'The system automatically detects if this is a classification (categories) or regression (numbers) problem.',
    tip: 'Classification predicts categories, regression predicts continuous values.'
  },
  {
    id: 'start-training',
    title: 'Start Training',
    description: 'Begin AutoML process',
    action: 'click',
    target: '[data-testid="train-button"]',
    content: 'Click to start training. Our AutoML will try multiple algorithms and find the best one for your data.',
    tip: 'Training usually takes 2-5 minutes depending on your data size.'
  },
  {
    id: 'monitor-progress',
    title: 'Monitor Training',
    description: 'Watch the progress',
    action: 'observe',
    content: 'Watch as the system tries different algorithms and optimizes parameters. You\'ll see accuracy improvements in real-time.',
    tip: 'The final model is automatically selected based on validation performance.'
  }
];

// Tutorial provider hook
export function useTutorial(tutorialName: string) {
  const [isVisible, setIsVisible] = useState(false);
  
  const tutorials: Record<string, TutorialStep[]> = {
    'upload-data': uploadDataTutorial,
    'explore-data': exploreDataTutorial,
    'train-model': trainModelTutorial
  };

  const showTutorial = () => setIsVisible(true);
  const hideTutorial = () => setIsVisible(false);

  return {
    tutorial: tutorials[tutorialName] || [],
    isVisible,
    showTutorial,
    hideTutorial
  };
}