"""
Pydantic schemas for onboarding API
"""
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum


class OnboardingStepType(str, Enum):
    """Types of onboarding steps"""
    WELCOME = "welcome"
    UPLOAD_DATA = "upload_data"
    EXPLORE_DATA = "explore_data"
    TRAIN_MODEL = "train_model"
    MAKE_PREDICTIONS = "make_predictions"
    EXPORT_MODEL = "export_model"
    COMPLETION = "completion"


class OnboardingStepStatus(str, Enum):
    """Status of onboarding steps"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class OnboardingStepResponse(BaseModel):
    """Response model for onboarding step"""
    step_id: str
    title: str
    description: str
    step_type: OnboardingStepType
    status: OnboardingStepStatus
    order: int
    is_required: bool = True
    is_skippable: bool = False
    estimated_duration: str
    completion_criteria: List[str]
    instructions: List[str]
    help_text: Optional[str] = None
    code_examples: Optional[List[Dict[str, str]]] = None
    screenshot_url: Optional[str] = None
    video_url: Optional[str] = None
    completed_at: Optional[datetime] = None
    completion_data: Optional[Dict[str, Any]] = None


class OnboardingStatusResponse(BaseModel):
    """Response model for overall onboarding status"""
    user_id: str
    is_onboarding_complete: bool
    current_step_id: Optional[str] = None
    progress_percentage: float = Field(ge=0, le=100)
    total_steps: int
    completed_steps: int
    skipped_steps: int
    time_spent_minutes: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    last_activity_at: datetime


class CompleteStepRequest(BaseModel):
    """Request model for completing an onboarding step"""
    completion_data: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Optional data about how the step was completed"
    )


class TutorialProgressResponse(BaseModel):
    """Response model for detailed tutorial progress"""
    user_id: str
    total_progress_percentage: float
    steps_progress: List[OnboardingStepResponse]
    achievements_unlocked: List[Dict[str, Any]]
    current_streak: int
    total_time_spent_minutes: int
    features_discovered: List[str]
    help_articles_viewed: List[str]
    sample_datasets_used: List[str]


class SampleDatasetResponse(BaseModel):
    """Response model for sample datasets"""
    dataset_id: str
    name: str
    description: str
    size_mb: float
    rows: int
    columns: int
    problem_type: str
    difficulty_level: str = Field(description="beginner, intermediate, advanced")
    tags: List[str]
    preview_data: List[Dict[str, Any]] = Field(max_items=5)
    target_column: str
    feature_columns: List[str]
    learning_objectives: List[str]
    expected_accuracy: Optional[float] = None
    download_url: str
    documentation_url: Optional[str] = None


class OnboardingUserProgress(BaseModel):
    """Model for storing user onboarding progress in database"""
    user_id: str
    current_step_id: Optional[str] = None
    completed_steps: List[str] = Field(default_factory=list)
    skipped_steps: List[str] = Field(default_factory=list)
    step_completion_data: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    achievements: List[Dict[str, Any]] = Field(default_factory=list)
    started_at: datetime
    last_activity_at: datetime
    completed_at: Optional[datetime] = None
    time_spent_minutes: int = 0
    sample_datasets_loaded: List[str] = Field(default_factory=list)
    features_discovered: List[str] = Field(default_factory=list)
    help_articles_viewed: List[str] = Field(default_factory=list)


class OnboardingMetrics(BaseModel):
    """Model for onboarding analytics and metrics"""
    total_users_started: int
    total_users_completed: int
    completion_rate: float
    average_completion_time_minutes: float
    most_skipped_steps: List[Dict[str, Any]]
    most_difficult_steps: List[Dict[str, Any]]
    popular_sample_datasets: List[Dict[str, Any]]
    drop_off_points: List[Dict[str, Any]]
    user_feedback_scores: Dict[str, float]