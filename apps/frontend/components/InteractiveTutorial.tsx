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
  // Derived, not stored: highlighting is on exactly when the tutorial is active
  // and the current step names a target. Storing it duplicated that condition and
  // required an effect to keep the copy in sync.

  const currentStep = steps[currentStepIndex];
  const progress = (currentStepIndex / steps.length) * 100;

  const removeHighlight = () => {
    const overlay = document.getElementById('tutorial-overlay');
    const highlight = document.getElementById('tutorial-highlight');
    
    if (overlay) overlay.remove();
    if (highlight) highlight.remove();
  };

  const highlightElement = (selector: string) => {
    removeHighlight();

    const element = document.querySelector(selector);
    if (element) {
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

  useEffect(() => {
    if (isActive && currentStep?.target) {
      highlightElement(currentStep.target);
    } else {
      removeHighlight();
    }

    return () => removeHighlight();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentStepIndex, isActive, currentStep]);

  const isHighlighting = isActive && !!currentStep?.target;

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

  useEffect(() => {
    if (currentStep?.autoAdvance && currentStep.duration) {
      const timer = setTimeout(() => {
        nextStep();
      }, currentStep.duration);

      return () => clearTimeout(timer);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentStepIndex, currentStep]);

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
          <div className="text-sm text-muted-foreground">
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
            <Badge variant="secondary" className="bg-blue-100 dark:bg-blue-900/40 text-blue-800 dark:text-blue-200">
              Step {currentStepIndex + 1} of {steps.length}
            </Badge>
            {isHighlighting && (
              <Badge variant="outline" className="flex items-center gap-1 text-blue-600">
                <Target className="h-3 w-3" />
                Highlighting
              </Badge>
            )}
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

          <p className="text-sm text-foreground">
            {currentStep.content}
          </p>

          {currentStep.tip && (
            <Alert className="border-blue-200 dark:border-blue-900 bg-blue-50 dark:bg-blue-950/40">
              <Lightbulb className="h-4 w-4 text-blue-600" />
              <AlertDescription className="text-blue-800 dark:text-blue-200">
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
