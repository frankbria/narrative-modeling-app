/** The onboarding API's shapes, shared by the page and its parts. */

export interface OnboardingStatus {
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

export type StepStatus = 'not_started' | 'in_progress' | 'completed' | 'skipped';

export interface CodeExample {
  title: string;
  code: string;
}

export interface StepInfo {
  step_id: string;
  title: string;
  description: string;
  step_type: string;
  status: StepStatus;
  order: number;
  is_required: boolean;
  is_skippable: boolean;
  estimated_duration: string;
  completion_criteria: string[];
  instructions: string[];
  help_text?: string;
  code_examples?: CodeExample[];
  completed_at?: string;
}

export interface Achievement {
  id: string;
  title: string;
  description: string;
  type: 'badge' | 'milestone';
  points: number;
  earned_at: string;
}
