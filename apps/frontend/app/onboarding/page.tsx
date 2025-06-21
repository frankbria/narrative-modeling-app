"use client";

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  CheckCircle, 
  Circle, 
  Play, 
  Skip, 
  Trophy, 
  Clock, 
  BookOpen, 
  Video,
  ArrowRight,
  Star,
  Target,
  Zap
} from 'lucide-react';
import { OnboardingStep } from '@/components/OnboardingStep';
import { OnboardingProgress } from '@/components/OnboardingProgress';
import { SampleDatasetSelector } from '@/components/SampleDatasetSelector';
import { AchievementsBadge } from '@/components/AchievementsBadge';

interface OnboardingStatus {
  user_id: string;
  is_onboarding_complete: boolean;
  current_step_id: string | null;
  progress_percentage: number;
  total_steps: number;
  completed_steps: number;
  skipped_steps: number;
  time_spent_minutes: number;
  started_at: string;
  completed_at: string | null;
  last_activity_at: string;
}

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

interface Achievement {
  id: string;
  title: string;
  description: string;
  type: 'badge' | 'milestone';
  points: number;
  earned_at: string;
}

export default function OnboardingPage() {
  const router = useRouter();
  const [status, setStatus] = useState<OnboardingStatus | null>(null);
  const [steps, setSteps] = useState<StepInfo[]>([]);
  const [currentStep, setCurrentStep] = useState<StepInfo | null>(null);
  const [achievements, setAchievements] = useState<Achievement[]>([]);
  const [loading, setLoading] = useState(true);
  const [completingStep, setCompletingStep] = useState(false);
  const [showCelebration, setShowCelebration] = useState(false);

  useEffect(() => {
    loadOnboardingData();
  }, []);

  const loadOnboardingData = async () => {
    try {
      setLoading(true);
      
      // Load onboarding status
      const statusResponse = await fetch('/api/v1/onboarding/status');
      const statusData = await statusResponse.json();
      setStatus(statusData);

      // Load steps
      const stepsResponse = await fetch('/api/v1/onboarding/steps');
      const stepsData = await stepsResponse.json();
      setSteps(stepsData);

      // Set current step
      if (statusData.current_step_id) {
        const current = stepsData.find((s: StepInfo) => s.step_id === statusData.current_step_id);
        setCurrentStep(current || null);
      }

      // Load achievements
      const achievementsResponse = await fetch('/api/v1/onboarding/achievements');
      const achievementsData = await achievementsResponse.json();
      setAchievements(achievementsData.achievements || []);

    } catch (error) {
      console.error('Failed to load onboarding data:', error);
    } finally {
      setLoading(false);
    }
  };

  const completeStep = async (stepId: string, completionData?: any) => {
    try {
      setCompletingStep(true);
      
      const response = await fetch(`/api/v1/onboarding/steps/${stepId}/complete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ completion_data: completionData || {} })
      });

      const result = await response.json();
      
      if (result.success) {
        // Show celebration if achievements were earned
        if (result.achievements && result.achievements.length > 0) {
          setShowCelebration(true);
          setTimeout(() => setShowCelebration(false), 3000);
        }

        // Reload data to update progress
        await loadOnboardingData();
      }
    } catch (error) {
      console.error('Failed to complete step:', error);
    } finally {
      setCompletingStep(false);
    }
  };

  const skipStep = async (stepId: string) => {
    try {
      const response = await fetch(`/api/v1/onboarding/skip-step/${stepId}`, {
        method: 'POST'
      });

      if (response.ok) {
        await loadOnboardingData();
      }
    } catch (error) {
      console.error('Failed to skip step:', error);
    }
  };

  const getStepIcon = (step: StepInfo) => {
    switch (step.status) {
      case 'completed':
        return <CheckCircle className="h-5 w-5 text-green-500" />;
      case 'in_progress':
        return <Play className="h-5 w-5 text-blue-500" />;
      case 'skipped':
        return <Skip className="h-5 w-5 text-gray-400" />;
      default:
        return <Circle className="h-5 w-5 text-gray-300" />;
    }
  };

  const getStepStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'bg-green-100 text-green-800';
      case 'in_progress': return 'bg-blue-100 text-blue-800';
      case 'skipped': return 'bg-gray-100 text-gray-600';
      default: return 'bg-gray-50 text-gray-500';
    }
  };

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600"></div>
        </div>
      </div>
    );
  }

  // If onboarding is complete, show completion screen
  if (status?.is_onboarding_complete) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Card className="max-w-2xl mx-auto text-center">
          <CardHeader>
            <div className="flex justify-center mb-4">
              <Trophy className="h-16 w-16 text-yellow-500" />
            </div>
            <CardTitle className="text-2xl">Congratulations! 🎉</CardTitle>
            <CardDescription>You've completed the onboarding tutorial</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="grid grid-cols-3 gap-4 text-center">
              <div>
                <div className="text-2xl font-bold text-blue-600">{status.completed_steps}</div>
                <div className="text-sm text-gray-600">Steps Completed</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-green-600">{achievements.length}</div>
                <div className="text-sm text-gray-600">Achievements</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-purple-600">{status.time_spent_minutes}</div>
                <div className="text-sm text-gray-600">Minutes Spent</div>
              </div>
            </div>

            {achievements.length > 0 && (
              <div>
                <h3 className="font-semibold mb-2">Your Achievements</h3>
                <div className="flex flex-wrap justify-center gap-2">
                  {achievements.map((achievement) => (
                    <AchievementsBadge key={achievement.id} achievement={achievement} />
                  ))}
                </div>
              </div>
            )}

            <div className="space-y-2">
              <Button 
                onClick={() => router.push('/explore')} 
                className="w-full"
                size="lg"
              >
                Start Building Models <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
              <Button 
                variant="outline" 
                onClick={() => router.push('/docs')}
                className="w-full"
              >
                <BookOpen className="mr-2 h-4 w-4" />
                View Documentation
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      {showCelebration && (
        <Alert className="mb-6 border-green-200 bg-green-50">
          <Star className="h-4 w-4 text-green-600" />
          <AlertDescription className="text-green-800">
            🎉 Amazing! You've earned new achievements! Keep going!
          </AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Progress Sidebar */}
        <div className="lg:col-span-1">
          <Card className="sticky top-4">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Target className="h-5 w-5" />
                Your Progress
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <OnboardingProgress 
                status={status}
                achievements={achievements}
              />
              
              {/* Steps List */}
              <div className="space-y-2">
                <h4 className="font-medium text-sm">Tutorial Steps</h4>
                {steps.map((step) => (
                  <div 
                    key={step.step_id} 
                    className={`flex items-center gap-2 p-2 rounded-md cursor-pointer transition-colors ${
                      currentStep?.step_id === step.step_id 
                        ? 'bg-blue-50 border border-blue-200' 
                        : 'hover:bg-gray-50'
                    }`}
                    onClick={() => setCurrentStep(step)}
                  >
                    {getStepIcon(step)}
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium truncate">{step.title}</div>
                      <Badge variant="secondary" className={`text-xs ${getStepStatusColor(step.status)}`}>
                        {step.status.replace('_', ' ')}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Main Content */}
        <div className="lg:col-span-3">
          {currentStep ? (
            <OnboardingStep
              step={currentStep}
              onComplete={completeStep}
              onSkip={skipStep}
              isCompleting={completingStep}
            />
          ) : (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Zap className="h-6 w-6 text-blue-600" />
                  Welcome to Narrative Modeling!
                </CardTitle>
                <CardDescription>
                  Your AI-powered machine learning platform
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="text-center space-y-4">
                  <div className="text-lg">
                    Ready to build your first machine learning model? 
                    Our interactive tutorial will guide you through every step!
                  </div>
                  
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-center">
                    <div className="p-4 border rounded-lg">
                      <div className="text-2xl mb-2">📊</div>
                      <div className="font-medium">Upload Data</div>
                      <div className="text-sm text-gray-600">Start with your CSV file</div>
                    </div>
                    <div className="p-4 border rounded-lg">
                      <div className="text-2xl mb-2">🤖</div>
                      <div className="font-medium">Train Models</div>
                      <div className="text-sm text-gray-600">AI finds the best algorithm</div>
                    </div>
                    <div className="p-4 border rounded-lg">
                      <div className="text-2xl mb-2">🚀</div>
                      <div className="font-medium">Make Predictions</div>
                      <div className="text-sm text-gray-600">Get insights from your data</div>
                    </div>
                  </div>

                  <Button 
                    onClick={() => {
                      const firstStep = steps.find(s => s.order === 1);
                      if (firstStep) setCurrentStep(firstStep);
                    }}
                    size="lg"
                    className="bg-blue-600 hover:bg-blue-700"
                  >
                    <Play className="mr-2 h-4 w-4" />
                    Start Tutorial
                  </Button>
                </div>

                <Tabs defaultValue="overview" className="mt-6">
                  <TabsList className="grid w-full grid-cols-3">
                    <TabsTrigger value="overview">Overview</TabsTrigger>
                    <TabsTrigger value="sample-data">Sample Data</TabsTrigger>
                    <TabsTrigger value="help">Help & Resources</TabsTrigger>
                  </TabsList>
                  
                  <TabsContent value="overview" className="space-y-4">
                    <div className="prose max-w-none">
                      <h3>What you'll learn:</h3>
                      <ul>
                        <li>How to upload and validate your data</li>
                        <li>Understanding data quality and preparation</li>
                        <li>Training machine learning models with AutoML</li>
                        <li>Making predictions and interpreting results</li>
                        <li>Exporting models for production use</li>
                      </ul>
                      
                      <p className="flex items-center gap-2 text-sm text-gray-600">
                        <Clock className="h-4 w-4" />
                        Estimated time: 20-30 minutes
                      </p>
                    </div>
                  </TabsContent>
                  
                  <TabsContent value="sample-data">
                    <SampleDatasetSelector onDatasetSelected={(datasetId) => {
                      // Handle sample dataset selection
                      console.log('Selected dataset:', datasetId);
                    }} />
                  </TabsContent>
                  
                  <TabsContent value="help" className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <Card>
                        <CardHeader>
                          <CardTitle className="flex items-center gap-2">
                            <Video className="h-5 w-5" />
                            Video Tutorials
                          </CardTitle>
                        </CardHeader>
                        <CardContent>
                          <div className="space-y-2">
                            <Button variant="ghost" className="w-full justify-start">
                              Platform Overview (3 min)
                            </Button>
                            <Button variant="ghost" className="w-full justify-start">
                              Your First Model (8 min)
                            </Button>
                            <Button variant="ghost" className="w-full justify-start">
                              Advanced Features (12 min)
                            </Button>
                          </div>
                        </CardContent>
                      </Card>
                      
                      <Card>
                        <CardHeader>
                          <CardTitle className="flex items-center gap-2">
                            <BookOpen className="h-5 w-5" />
                            Documentation
                          </CardTitle>
                        </CardHeader>
                        <CardContent>
                          <div className="space-y-2">
                            <Button variant="ghost" className="w-full justify-start">
                              Understanding Data Quality
                            </Button>
                            <Button variant="ghost" className="w-full justify-start">
                              Choosing the Right Model
                            </Button>
                            <Button variant="ghost" className="w-full justify-start">
                              Interpreting Results
                            </Button>
                          </div>
                        </CardContent>
                      </Card>
                    </div>
                  </TabsContent>
                </Tabs>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}