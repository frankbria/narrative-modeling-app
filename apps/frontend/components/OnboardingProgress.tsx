"use client";

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { 
  Trophy, 
  Clock, 
  Target, 
  Star,
  CheckCircle,
  Zap
} from 'lucide-react';

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

interface Achievement {
  id: string;
  title: string;
  description: string;
  type: 'badge' | 'milestone';
  points: number;
  earned_at: string;
}

interface OnboardingProgressProps {
  status: OnboardingStatus | null;
  achievements: Achievement[];
}

export function OnboardingProgress({ status, achievements }: OnboardingProgressProps) {
  if (!status) {
    return (
      <div className="space-y-4">
        <div className="animate-pulse space-y-2">
          <div className="h-4 bg-gray-200 rounded w-3/4"></div>
          <div className="h-8 bg-gray-200 rounded"></div>
          <div className="h-4 bg-gray-200 rounded w-1/2"></div>
        </div>
      </div>
    );
  }

  const totalPoints = achievements.reduce((sum, achievement) => sum + achievement.points, 0);
  const badges = achievements.filter(a => a.type === 'badge');
  const milestones = achievements.filter(a => a.type === 'milestone');

  return (
    <div className="space-y-4">
      {/* Overall Progress */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-sm">
          <span className="font-medium">Overall Progress</span>
          <span className="text-gray-600">{Math.round(status.progress_percentage)}%</span>
        </div>
        <Progress value={status.progress_percentage} className="h-2" />
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>{status.completed_steps} of {status.total_steps} completed</span>
          {status.skipped_steps > 0 && (
            <span>{status.skipped_steps} skipped</span>
          )}
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 gap-2 text-center">
        <div className="p-2 bg-blue-50 rounded-md">
          <div className="flex items-center justify-center mb-1">
            <CheckCircle className="h-4 w-4 text-blue-600" />
          </div>
          <div className="text-lg font-bold text-blue-700">{status.completed_steps}</div>
          <div className="text-xs text-blue-600">Completed</div>
        </div>
        
        <div className="p-2 bg-green-50 rounded-md">
          <div className="flex items-center justify-center mb-1">
            <Clock className="h-4 w-4 text-green-600" />
          </div>
          <div className="text-lg font-bold text-green-700">{status.time_spent_minutes}</div>
          <div className="text-xs text-green-600">Minutes</div>
        </div>
      </div>

      {/* Achievements Section */}
      {achievements.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Trophy className="h-4 w-4 text-yellow-500" />
            <span className="font-medium text-sm">Achievements</span>
            <Badge variant="secondary" className="text-xs">
              {totalPoints} points
            </Badge>
          </div>
          
          {/* Recent Achievement */}
          {achievements.length > 0 && (
            <div className="p-2 bg-yellow-50 border border-yellow-200 rounded-md">
              <div className="flex items-center gap-2">
                <Star className="h-4 w-4 text-yellow-600" />
                <div className="flex-1">
                  <div className="text-sm font-medium text-yellow-800">
                    {achievements[achievements.length - 1].title}
                  </div>
                  <div className="text-xs text-yellow-600">
                    +{achievements[achievements.length - 1].points} points
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Achievement Counts */}
          <div className="flex justify-between text-xs text-gray-600">
            <span>{badges.length} badges earned</span>
            <span>{milestones.length} milestones reached</span>
          </div>
        </div>
      )}

      {/* Motivation Message */}
      <div className="space-y-2">
        {status.progress_percentage < 25 && (
          <div className="p-2 bg-blue-50 border border-blue-200 rounded-md">
            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4 text-blue-600" />
              <div className="text-sm text-blue-800">
                Great start! Keep going to unlock more features.
              </div>
            </div>
          </div>
        )}

        {status.progress_percentage >= 25 && status.progress_percentage < 50 && (
          <div className="p-2 bg-purple-50 border border-purple-200 rounded-md">
            <div className="flex items-center gap-2">
              <Target className="h-4 w-4 text-purple-600" />
              <div className="text-sm text-purple-800">
                You're making excellent progress! 
              </div>
            </div>
          </div>
        )}

        {status.progress_percentage >= 50 && status.progress_percentage < 75 && (
          <div className="p-2 bg-green-50 border border-green-200 rounded-md">
            <div className="flex items-center gap-2">
              <Star className="h-4 w-4 text-green-600" />
              <div className="text-sm text-green-800">
                Halfway there! You're doing amazing!
              </div>
            </div>
          </div>
        )}

        {status.progress_percentage >= 75 && !status.is_onboarding_complete && (
          <div className="p-2 bg-orange-50 border border-orange-200 rounded-md">
            <div className="flex items-center gap-2">
              <Trophy className="h-4 w-4 text-orange-600" />
              <div className="text-sm text-orange-800">
                Almost finished! You're so close to completion!
              </div>
            </div>
          </div>
        )}

        {status.is_onboarding_complete && (
          <div className="p-2 bg-green-50 border border-green-200 rounded-md">
            <div className="flex items-center gap-2">
              <Trophy className="h-4 w-4 text-green-600" />
              <div className="text-sm text-green-800 font-medium">
                🎉 Tutorial Complete! You're ready to build amazing models!
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Time Tracking */}
      <div className="text-xs text-gray-500 text-center">
        Started {new Date(status.started_at).toLocaleDateString()}
        {status.completed_at && (
          <div>
            Completed {new Date(status.completed_at).toLocaleDateString()}
          </div>
        )}
      </div>
    </div>
  );
}