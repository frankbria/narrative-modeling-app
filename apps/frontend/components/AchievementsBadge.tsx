"use client";

import React from 'react';
import { Badge } from '@/components/ui/badge';
import { 
  Trophy, 
  Star, 
  Target, 
  Database, 
  Brain, 
  Rocket,
  Crown,
  Award,
  Medal,
  Zap
} from 'lucide-react';

interface Achievement {
  id: string;
  title: string;
  description: string;
  type: 'badge' | 'milestone';
  points: number;
  earned_at: string;
}

interface AchievementsBadgeProps {
  achievement: Achievement;
  size?: 'sm' | 'md' | 'lg';
  showPoints?: boolean;
}

export function AchievementsBadge({ 
  achievement, 
  size = 'md', 
  showPoints = true 
}: AchievementsBadgeProps) {
  
  const getAchievementIcon = (achievementId: string, type: string) => {
    const iconSize = size === 'sm' ? 'h-3 w-3' : size === 'lg' ? 'h-5 w-5' : 'h-4 w-4';
    
    // Specific achievement icons
    switch (achievementId) {
      case 'first_upload':
        return <Database className={`${iconSize} text-blue-500`} />;
      case 'first_model':
        return <Brain className={`${iconSize} text-purple-500`} />;
      case 'onboarding_complete':
        return <Crown className={`${iconSize} text-yellow-500`} />;
      case 'data_explorer':
        return <Target className={`${iconSize} text-green-500`} />;
      case 'prediction_master':
        return <Zap className={`${iconSize} text-orange-500`} />;
      case 'model_export':
        return <Rocket className={`${iconSize} text-red-500`} />;
      default:
        // Default icons by type
        return type === 'milestone' 
          ? <Trophy className={`${iconSize} text-yellow-500`} />
          : <Star className={`${iconSize} text-blue-500`} />;
    }
  };

  const getAchievementColor = (type: string) => {
    return type === 'milestone'
      ? 'bg-gradient-to-r from-yellow-100 to-orange-100 text-yellow-800 border-yellow-300'
      : 'bg-gradient-to-r from-blue-100 to-purple-100 text-blue-800 border-blue-300';
  };

  const getSizeClasses = () => {
    switch (size) {
      case 'sm':
        return 'text-xs px-2 py-1';
      case 'lg':
        return 'text-base px-4 py-2';
      default:
        return 'text-sm px-3 py-1.5';
    }
  };

  const formatEarnedDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffTime = Math.abs(now.getTime() - date.getTime());
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    
    if (diffDays === 1) {
      return 'Today';
    } else if (diffDays <= 7) {
      return `${diffDays} days ago`;
    } else {
      return date.toLocaleDateString();
    }
  };

  return (
    <div className="group relative">
      <Badge 
        className={`
          ${getAchievementColor(achievement.type)}
          ${getSizeClasses()}
          border-2 shadow-sm transition-all hover:shadow-md cursor-help
          flex items-center gap-1.5
        `}
      >
        {getAchievementIcon(achievement.id, achievement.type)}
        <span className="font-medium">{achievement.title}</span>
        {showPoints && (
          <span className={`
            ml-1 px-1.5 py-0.5 rounded-full text-xs font-bold
            ${achievement.type === 'milestone' 
              ? 'bg-yellow-200 text-yellow-800' 
              : 'bg-blue-200 text-blue-800'
            }
          `}>
            +{achievement.points}
          </span>
        )}
      </Badge>

      {/* Tooltip */}
      <div className="
        absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2
        bg-gray-900 text-white text-xs rounded-lg px-3 py-2 whitespace-nowrap
        opacity-0 group-hover:opacity-100 transition-opacity duration-200
        pointer-events-none z-10
        before:content-[''] before:absolute before:top-full before:left-1/2 
        before:transform before:-translate-x-1/2 before:border-4 
        before:border-transparent before:border-t-gray-900
      ">
        <div className="font-medium">{achievement.title}</div>
        <div className="text-gray-300 mt-1">{achievement.description}</div>
        <div className="text-gray-400 mt-1 text-xs">
          Earned {formatEarnedDate(achievement.earned_at)}
        </div>
        {showPoints && (
          <div className="text-yellow-300 mt-1 text-xs font-medium">
            {achievement.points} points
          </div>
        )}
      </div>
    </div>
  );
}

// Component for displaying multiple achievements in a grid
interface AchievementsGridProps {
  achievements: Achievement[];
  maxDisplay?: number;
  size?: 'sm' | 'md' | 'lg';
}

export function AchievementsGrid({ 
  achievements, 
  maxDisplay = 10,
  size = 'md' 
}: AchievementsGridProps) {
  const displayedAchievements = achievements.slice(0, maxDisplay);
  const remainingCount = achievements.length - maxDisplay;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {displayedAchievements.map((achievement) => (
          <AchievementsBadge 
            key={achievement.id} 
            achievement={achievement} 
            size={size}
          />
        ))}
        
        {remainingCount > 0 && (
          <Badge variant="outline" className="cursor-pointer hover:bg-gray-50">
            +{remainingCount} more
          </Badge>
        )}
      </div>

      {/* Achievement Stats */}
      {achievements.length > 0 && (
        <div className="flex items-center gap-4 text-sm text-gray-600">
          <div className="flex items-center gap-1">
            <Award className="h-4 w-4" />
            <span>{achievements.filter(a => a.type === 'badge').length} badges</span>
          </div>
          <div className="flex items-center gap-1">
            <Medal className="h-4 w-4" />
            <span>{achievements.filter(a => a.type === 'milestone').length} milestones</span>
          </div>
          <div className="flex items-center gap-1">
            <Star className="h-4 w-4" />
            <span>{achievements.reduce((sum, a) => sum + a.points, 0)} total points</span>
          </div>
        </div>
      )}
    </div>
  );
}

// Component for celebration animation
export function AchievementCelebration({ achievement }: { achievement: Achievement }) {
  return (
    <div className="fixed inset-0 pointer-events-none z-50 flex items-center justify-center">
      <div className="bg-white rounded-xl shadow-2xl border-4 border-yellow-300 p-6 max-w-sm mx-4 animate-bounce">
        <div className="text-center space-y-3">
          <div className="text-4xl">🎉</div>
          <div className="space-y-1">
            <div className="text-lg font-bold text-gray-900">Achievement Unlocked!</div>
            <div className="text-yellow-600 font-medium">{achievement.title}</div>
            <div className="text-sm text-gray-600">{achievement.description}</div>
            <div className="text-lg font-bold text-green-600">+{achievement.points} points!</div>
          </div>
        </div>
      </div>
    </div>
  );
}