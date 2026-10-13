"use client";

import React from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ArrowRight, BookOpen, Trophy } from 'lucide-react';
import { AchievementsBadge } from '@/components/AchievementsBadge';
import type { Achievement, OnboardingStatus } from './types';

interface OnboardingCompleteProps {
  status: OnboardingStatus;
  achievements: Achievement[];
}

interface FigureProps {
  value: number;
  label: string;
  tone: string;
}

/** What a user sees once every required step is done. */
export function OnboardingComplete(props: OnboardingCompleteProps) {
  const { status, achievements } = props;
  const router = useRouter();
  const startBuilding = () => router.push('/explore');
  const openDocs = () => router.push('/quickstart');
  const earned = achievements.length > 0 ? <EarnedAchievements achievements={achievements} /> : null;
  return (
    <div className="container mx-auto px-4 py-8">
      <Card className="max-w-2xl mx-auto text-center">
        <CardHeader>
          <div className="flex justify-center mb-4">
            <Trophy className="h-16 w-16 text-yellow-500" />
          </div>
          <CardTitle className="text-2xl">Congratulations! 🎉</CardTitle>
          <CardDescription>You&apos;ve completed the onboarding tutorial</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid grid-cols-3 gap-4 text-center">
            <Figure value={status.completed_steps} label="Steps Completed" tone="text-blue-600" />
            <Figure value={achievements.length} label="Achievements" tone="text-green-600" />
            <Figure value={status.time_spent_minutes} label="Minutes Spent" tone="text-purple-600" />
          </div>

          {earned}

          <div className="space-y-2">
            <Button onClick={startBuilding} className="w-full" size="lg">
              Start Building Models <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
            <Button variant="outline" onClick={openDocs} className="w-full">
              <BookOpen className="mr-2 h-4 w-4" />
              View Documentation
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function Figure(props: FigureProps) {
  const { value, label, tone } = props;
  return (
    <div>
      <div className={`text-2xl font-bold ${tone}`}>{value}</div>
      <div className="text-sm text-muted-foreground">{label}</div>
    </div>
  );
}

function EarnedAchievements(props: { achievements: Achievement[] }) {
  const badges = props.achievements.map((achievement) => (
    <AchievementsBadge key={achievement.id} achievement={achievement} />
  ));
  return (
    <div>
      <h3 className="font-semibold mb-2">Your Achievements</h3>
      <div className="flex flex-wrap justify-center gap-2">{badges}</div>
    </div>
  );
}
