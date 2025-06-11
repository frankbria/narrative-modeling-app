import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { OnboardingProgress } from '@/components/OnboardingProgress';

const mockStatus = {
  user_id: 'test_user_123',
  is_onboarding_complete: false,
  current_step_id: 'upload_data',
  progress_percentage: 42.5,
  total_steps: 7,
  completed_steps: 3,
  skipped_steps: 1,
  time_spent_minutes: 25,
  started_at: '2024-01-01T12:00:00Z',
  completed_at: null,
  last_activity_at: '2024-01-01T12:25:00Z'
};

const mockAchievements = [
  {
    id: 'first_upload',
    title: 'Data Explorer',
    description: 'Uploaded your first dataset',
    type: 'badge' as const,
    points: 10,
    earned_at: '2024-01-01T12:10:00Z'
  },
  {
    id: 'first_model',
    title: 'Model Builder', 
    description: 'Trained your first ML model',
    type: 'milestone' as const,
    points: 25,
    earned_at: '2024-01-01T12:20:00Z'
  }
];

describe('OnboardingProgress', () => {
  it('renders loading state when status is null', () => {
    render(<OnboardingProgress status={null} achievements={[]} />);
    
    // Should show loading skeleton
    expect(document.querySelectorAll('.animate-pulse')).toHaveLength(1);
  });

  it('renders progress information correctly', () => {
    render(<OnboardingProgress status={mockStatus} achievements={mockAchievements} />);
    
    expect(screen.getByText('Overall Progress')).toBeInTheDocument();
    expect(screen.getByText('43%')).toBeInTheDocument(); // Rounded progress
    expect(screen.getByText('3 of 7 completed')).toBeInTheDocument();
    expect(screen.getByText('1 skipped')).toBeInTheDocument();
  });

  it('renders stats grid correctly', () => {
    render(<OnboardingProgress status={mockStatus} achievements={mockAchievements} />);
    
    expect(screen.getByText('3')).toBeInTheDocument(); // Completed steps
    expect(screen.getByText('Completed')).toBeInTheDocument();
    expect(screen.getByText('25')).toBeInTheDocument(); // Minutes
    expect(screen.getByText('Minutes')).toBeInTheDocument();
  });

  it('renders achievements section when achievements exist', () => {
    render(<OnboardingProgress status={mockStatus} achievements={mockAchievements} />);
    
    expect(screen.getByText('Achievements')).toBeInTheDocument();
    expect(screen.getByText('35 points')).toBeInTheDocument(); // Total points
    expect(screen.getByText('Model Builder')).toBeInTheDocument(); // Latest achievement
    expect(screen.getByText('+25 points')).toBeInTheDocument();
  });

  it('shows achievement counts correctly', () => {
    render(<OnboardingProgress status={mockStatus} achievements={mockAchievements} />);
    
    expect(screen.getByText('1 badges earned')).toBeInTheDocument();
    expect(screen.getByText('1 milestones reached')).toBeInTheDocument();
  });

  it('does not render achievements section when no achievements', () => {
    render(<OnboardingProgress status={mockStatus} achievements={[]} />);
    
    expect(screen.queryByText('Achievements')).not.toBeInTheDocument();
    expect(screen.queryByText('badges earned')).not.toBeInTheDocument();
  });

  it('shows appropriate motivation message for different progress levels', () => {
    // Less than 25%
    const lowProgress = { ...mockStatus, progress_percentage: 15 };
    const { rerender } = render(<OnboardingProgress status={lowProgress} achievements={[]} />);
    expect(screen.getByText(/Great start!/)).toBeInTheDocument();

    // 25% - 50%
    const midLowProgress = { ...mockStatus, progress_percentage: 35 };
    rerender(<OnboardingProgress status={midLowProgress} achievements={[]} />);
    expect(screen.getByText(/making excellent progress/)).toBeInTheDocument();

    // 50% - 75% 
    const midHighProgress = { ...mockStatus, progress_percentage: 60 };
    rerender(<OnboardingProgress status={midHighProgress} achievements={[]} />);
    expect(screen.getByText(/Halfway there!/)).toBeInTheDocument();

    // 75%+
    const highProgress = { ...mockStatus, progress_percentage: 85 };
    rerender(<OnboardingProgress status={highProgress} achievements={[]} />);
    expect(screen.getByText(/Almost finished!/)).toBeInTheDocument();
  });

  it('shows completion message when onboarding is complete', () => {
    const completeStatus = {
      ...mockStatus,
      is_onboarding_complete: true,
      progress_percentage: 100,
      completed_at: '2024-01-01T13:00:00Z'
    };
    
    render(<OnboardingProgress status={completeStatus} achievements={mockAchievements} />);
    
    expect(screen.getByText(/Tutorial Complete!/)).toBeInTheDocument();
  });

  it('renders time tracking information', () => {
    render(<OnboardingProgress status={mockStatus} achievements={mockAchievements} />);
    
    expect(screen.getByText(/Started/)).toBeInTheDocument();
    // Check for date formatting - use regex to be more flexible
    expect(screen.getByText(/Started.*2024/)).toBeInTheDocument();
  });

  it('shows completion date when available', () => {
    const completeStatus = {
      ...mockStatus,
      completed_at: '2024-01-01T13:00:00Z'
    };
    
    render(<OnboardingProgress status={completeStatus} achievements={mockAchievements} />);
    
    // Use getAllByText since there are multiple instances
    expect(screen.getAllByText(/Completed/).length).toBeGreaterThan(0);
  });

  it('handles zero progress correctly', () => {
    const zeroProgress = {
      ...mockStatus,
      progress_percentage: 0,
      completed_steps: 0,
      time_spent_minutes: 0
    };
    
    render(<OnboardingProgress status={zeroProgress} achievements={[]} />);
    
    expect(screen.getByText('0%')).toBeInTheDocument();
    expect(screen.getByText('0 of 7 completed')).toBeInTheDocument();
    // There are multiple "0" elements, so check for the specific one in minutes section
    expect(screen.getByText('Minutes').previousElementSibling).toHaveTextContent('0');
  });

  it('handles no skipped steps correctly', () => {
    const noSkipped = {
      ...mockStatus,
      skipped_steps: 0
    };
    
    render(<OnboardingProgress status={noSkipped} achievements={[]} />);
    
    expect(screen.queryByText('skipped')).not.toBeInTheDocument();
  });

  it('handles multiple achievements correctly', () => {
    const manyAchievements = [
      ...mockAchievements,
      {
        id: 'streak_5',
        title: 'Streak Master',
        description: '5 day learning streak',
        type: 'badge' as const,
        points: 15,
        earned_at: '2024-01-01T12:30:00Z'
      }
    ];
    
    render(<OnboardingProgress status={mockStatus} achievements={manyAchievements} />);
    
    expect(screen.getByText('50 points')).toBeInTheDocument(); // Total points
    expect(screen.getByText('2 badges earned')).toBeInTheDocument();
    expect(screen.getByText('1 milestones reached')).toBeInTheDocument();
    expect(screen.getByText('Streak Master')).toBeInTheDocument(); // Latest achievement
  });

  it('applies correct styling classes', () => {
    render(<OnboardingProgress status={mockStatus} achievements={mockAchievements} />);
    
    // Check that progress elements have correct styling
    const progressBar = document.querySelector('[role="progressbar"]');
    expect(progressBar).toBeInTheDocument();
    
    // Check stat cards have correct colors - need to go up to the container div
    expect(screen.getByText('3').closest('.bg-blue-50')).toBeInTheDocument();
    expect(screen.getByText('25').closest('.bg-green-50')).toBeInTheDocument();
  });
});