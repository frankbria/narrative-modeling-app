"use client";

import React from 'react';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Trophy, Clock, Target, Star, CheckCircle, Zap, type LucideIcon } from 'lucide-react';
import type { Achievement, OnboardingStatus } from '@/components/onboarding/types';

interface OnboardingProgressProps {
  status: OnboardingStatus | null;
  achievements: Achievement[];
}

interface StatusProps {
  status: OnboardingStatus;
}

interface AchievementsProps {
  achievements: Achievement[];
}

interface StatTileProps {
  icon: LucideIcon;
  value: number;
  label: string;
  tone: string;
}

interface Encouragement {
  /** Shown while progress is below this percentage (the first match wins). */
  below: number;
  icon: LucideIcon;
  text: string;
  tone: string;
}

const STAT_TONES = {
  blue: 'bg-blue-50 dark:bg-blue-950/40 text-blue-600 [&_strong]:text-blue-700 dark:[&_strong]:text-blue-300',
  green: 'bg-green-50 dark:bg-green-950/40 text-green-600 [&_strong]:text-green-700 dark:[&_strong]:text-green-300',
};

const NOTE_TONES = {
  blue: 'bg-blue-50 dark:bg-blue-950/40 border-blue-200 dark:border-blue-900 text-blue-800 dark:text-blue-200 [&_svg]:text-blue-600',
  purple: 'bg-purple-50 dark:bg-purple-950/40 border-purple-200 dark:border-purple-900 text-purple-800 dark:text-purple-200 [&_svg]:text-purple-600',
  green: 'bg-green-50 dark:bg-green-950/40 border-green-200 dark:border-green-900 text-green-800 dark:text-green-200 [&_svg]:text-green-600',
  orange: 'bg-orange-50 dark:bg-orange-950/40 border-orange-200 dark:border-orange-900 text-orange-800 dark:text-orange-200 [&_svg]:text-orange-600',
};

const ENCOURAGEMENTS: Encouragement[] = [
  { below: 25, icon: Zap, text: 'Great start! Keep going to unlock more features.', tone: NOTE_TONES.blue },
  { below: 50, icon: Target, text: "You're making excellent progress!", tone: NOTE_TONES.purple },
  { below: 75, icon: Star, text: "Halfway there! You're doing amazing!", tone: NOTE_TONES.green },
  { below: Infinity, icon: Trophy, text: "Almost finished! You're so close to completion!", tone: NOTE_TONES.orange },
];

const COMPLETE: Encouragement = {
  below: Infinity,
  icon: Trophy,
  text: "🎉 Tutorial Complete! You're ready to build amazing models!",
  tone: `${NOTE_TONES.green} font-medium`,
};

/** The notes that apply: one for how far along the user is, and the finished one once done. */
function encouragements(status: OnboardingStatus): Encouragement[] {
  const progress = status.progress_percentage;
  if (!status.is_onboarding_complete) return noteFor(progress);
  // Before the last quarter a finished tutorial still shows that quarter's note.
  return progress < 75 ? [...noteFor(progress), COMPLETE] : [COMPLETE];
}

/** One note, or none when the backend sent no percentage to place the user by. */
function noteFor(progress: number): Encouragement[] {
  const note = ENCOURAGEMENTS.find((candidate) => progress < candidate.below);
  return note ? [note] : [];
}

export function OnboardingProgress(props: OnboardingProgressProps) {
  const { status, achievements } = props;
  if (!status) return SKELETON;
  const earned = achievements.length > 0 ? <AchievementsSummary achievements={achievements} /> : null;
  const notes = encouragements(status).map((note) => <Note key={note.text} note={note} />);
  return (
    <div className="space-y-4">
      <OverallProgress status={status} />

      <div className="grid grid-cols-2 gap-2 text-center">
        <StatTile icon={CheckCircle} value={status.completed_steps} label="Completed" tone={STAT_TONES.blue} />
        <StatTile icon={Clock} value={status.time_spent_minutes} label="Minutes" tone={STAT_TONES.green} />
      </div>

      {earned}

      <div className="space-y-2">{notes}</div>

      <Dates status={status} />
    </div>
  );
}

const SKELETON = (
  <div className="space-y-4">
    <div className="animate-pulse space-y-2">
      <div className="h-4 bg-gray-200 rounded w-3/4"></div>
      <div className="h-8 bg-gray-200 rounded"></div>
      <div className="h-4 bg-gray-200 rounded w-1/2"></div>
    </div>
  </div>
);

function OverallProgress(props: StatusProps) {
  const { status } = props;
  const skipped = status.skipped_steps > 0 ? <span>{status.skipped_steps} skipped</span> : null;
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium">Overall Progress</span>
        <span className="text-muted-foreground">{Math.round(status.progress_percentage)}%</span>
      </div>
      <Progress value={status.progress_percentage} className="h-2" />
      <div className="flex flex-wrap items-center justify-between gap-x-2 text-xs text-muted-foreground">
        <span>
          {status.completed_steps} of {status.total_steps} completed
        </span>
        {skipped}
      </div>
    </div>
  );
}

function StatTile(props: StatTileProps) {
  const { icon: Icon, value, label, tone } = props;
  return (
    <div className={`p-2 rounded-md ${tone}`}>
      <div className="flex items-center justify-center mb-1">
        <Icon className="h-4 w-4" />
      </div>
      <strong className="block text-lg font-bold">{value}</strong>
      <div className="text-xs">{label}</div>
    </div>
  );
}

/** Points, the latest achievement, and how many of each kind. Each row wraps (#809). */
function AchievementsSummary(props: AchievementsProps) {
  const { achievements } = props;
  const latest = achievements[achievements.length - 1];
  const points = achievements.reduce((sum, achievement) => sum + achievement.points, 0);
  const badges = achievements.filter((a) => a.type === 'badge').length;
  const milestones = achievements.length - badges;
  return (
    <div className="space-y-2" data-testid="onboarding-achievements">
      <div className="flex flex-wrap items-center gap-2">
        <Trophy className="h-4 w-4 shrink-0 text-yellow-500" />
        <span className="font-medium text-sm">Achievements</span>
        <Badge variant="secondary" className="text-xs whitespace-nowrap">
          {points} points
        </Badge>
      </div>

      <div className="p-2 bg-yellow-50 dark:bg-yellow-950/40 border border-yellow-200 dark:border-yellow-900 rounded-md">
        <div className="flex items-center gap-2">
          <Star className="h-4 w-4 shrink-0 text-yellow-600" />
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium text-yellow-800 dark:text-yellow-200 break-words">{latest.title}</div>
            <div className="text-xs text-yellow-600">+{latest.points} points</div>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap justify-between gap-x-3 gap-y-1 text-xs text-muted-foreground">
        <span className="whitespace-nowrap">{badges} badges earned</span>
        <span className="whitespace-nowrap">{milestones} milestones reached</span>
      </div>
    </div>
  );
}

function Note(props: { note: Encouragement }) {
  const { icon: Icon, text, tone } = props.note;
  return (
    <div className={`p-2 border rounded-md ${tone}`}>
      <div className="flex items-center gap-2">
        <Icon className="h-4 w-4 shrink-0" />
        <div className="text-sm">{text}</div>
      </div>
    </div>
  );
}

function Dates(props: StatusProps) {
  const { status } = props;
  const completed = status.completed_at ? (
    <div>Completed {new Date(status.completed_at).toLocaleDateString()}</div>
  ) : null;
  return (
    <div className="text-xs text-muted-foreground text-center">
      Started {new Date(status.started_at).toLocaleDateString()}
      {completed}
    </div>
  );
}
