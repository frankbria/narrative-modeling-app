"""
Pydantic schemas for onboarding API
"""
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


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
    completion_criteria: list[str]
    instructions: list[str]
    help_text: str | None = None
    code_examples: list[dict[str, str]] | None = None
    screenshot_url: str | None = None
    video_url: str | None = None
    completed_at: datetime | None = None
    completion_data: dict[str, Any] | None = None


class OnboardingStatusResponse(BaseModel):
    """Response model for overall onboarding status"""
    user_id: str
    is_onboarding_complete: bool
    current_step_id: str | None = None
    progress_percentage: float = Field(ge=0, le=100)
    total_steps: int
    completed_steps: int
    skipped_steps: int
    time_spent_minutes: int
    started_at: datetime
    completed_at: datetime | None = None
    last_activity_at: datetime


class CompleteStepRequest(BaseModel):
    """Request model for completing an onboarding step"""
    completion_data: dict[str, Any] | None = Field(
        default_factory=dict,
        description="Optional data about how the step was completed"
    )


class TutorialProgressResponse(BaseModel):
    """Response model for detailed tutorial progress"""
    user_id: str
    total_progress_percentage: float
    steps_progress: list[OnboardingStepResponse]
    achievements_unlocked: list[dict[str, Any]]
    current_streak: int
    total_time_spent_minutes: int
    features_discovered: list[str]
    help_articles_viewed: list[str]
    sample_datasets_used: list[str]


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
    tags: list[str]
    preview_data: list[dict[str, Any]] = Field(max_length=5)
    target_column: str
    feature_columns: list[str]
    learning_objectives: list[str]
    expected_accuracy: float | None = None
    download_url: str
    documentation_url: str | None = None


class OnboardingUserProgress(BaseModel):
    """Model for storing user onboarding progress in database"""
    user_id: str
    current_step_id: str | None = None
    completed_steps: list[str] = Field(default_factory=list)
    skipped_steps: list[str] = Field(default_factory=list)
    step_completion_data: dict[str, dict[str, Any]] = Field(default_factory=dict)
    achievements: list[dict[str, Any]] = Field(default_factory=list)
    started_at: datetime
    last_activity_at: datetime
    completed_at: datetime | None = None
    time_spent_minutes: int = 0
    sample_datasets_loaded: list[str] = Field(default_factory=list)
    features_discovered: list[str] = Field(default_factory=list)
    help_articles_viewed: list[str] = Field(default_factory=list)


class OnboardingMetrics(BaseModel):
    """Model for onboarding analytics and metrics"""
    total_users_started: int
    total_users_completed: int
    completion_rate: float
    average_completion_time_minutes: float
    most_skipped_steps: list[dict[str, Any]]
    most_difficult_steps: list[dict[str, Any]]
    popular_sample_datasets: list[dict[str, Any]]
    drop_off_points: list[dict[str, Any]]
    user_feedback_scores: dict[str, float]