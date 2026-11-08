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
        return <Database className={`${iconSize} text-primary`} />;
      case 'first_model':
        return <Brain className={`${iconSize} text-primary`} />;
      case 'onboarding_complete':
        return <Crown className={`${iconSize} text-warning`} />;
      case 'data_explorer':
        return <Target className={`${iconSize} text-success`} />;
      case 'prediction_master':
        return <Zap className={`${iconSize} text-warning`} />;
      case 'model_export':
        return <Rocket className={`${iconSize} text-primary`} />;
      default:
        // Default icons by type
        return type === 'milestone' 
          ? <Trophy className={`${iconSize} text-warning`} />
          : <Star className={`${iconSize} text-primary`} />;
    }
  };

  const getAchievementColor = (type: string) => {
    return type === 'milestone'
      ? 'bg-gradient-to-r from-primary/20 to-primary/10 text-primary border-primary'
      : 'bg-gradient-to-r from-primary/10 to-primary/5 text-primary border-primary/30';
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
              ? 'bg-primary text-primary-foreground' 
              : 'bg-primary/20 text-primary'
            }
          `}>
            +{achievement.points}
          </span>
        )}
      </Badge>

      {/* Tooltip */}
      <div className="
        absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2
        bg-foreground text-background text-xs rounded-lg px-3 py-2 whitespace-nowrap
        opacity-0 group-hover:opacity-100 transition-opacity duration-200
        pointer-events-none z-10
        before:content-[''] before:absolute before:top-full before:left-1/2 
        before:transform before:-translate-x-1/2 before:border-4 
        before:border-transparent before:border-t-gray-900
      ">
        <div className="font-medium">{achievement.title}</div>
        <div className="text-background/80 mt-1">{achievement.description}</div>
        <div className="text-background/70 mt-1 text-xs">
          Earned {formatEarnedDate(achievement.earned_at)}
        </div>
        {showPoints && (
          <div className="text-background mt-1 text-xs font-medium">
            {achievement.points} points
          </div>
        )}
      </div>
    </div>
  );
}
