"""
A/B Test model for experiment tracking
"""
from datetime import datetime
from enum import Enum
from typing import Annotated

from beanie import Document, Indexed
from pydantic import BaseModel, Field

from app.utils.datetime import utcnow


class VariantStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class ExperimentStatus(str, Enum):
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class Variant(BaseModel):
    """Model variant in an A/B test"""
    variant_id: str = Field(description="Unique variant identifier")
    model_id: str = Field(description="Model ID for this variant")
    name: str = Field(description="Variant name (e.g., 'Control', 'Treatment A')")
    description: str | None = Field(None, description="Variant description")
    traffic_percentage: float = Field(description="Traffic allocation percentage")
    
    # Performance metrics
    total_predictions: int = Field(default=0)
    total_latency_ms: float = Field(default=0)
    error_count: int = Field(default=0)
    
    # Business metrics (customizable)
    custom_metrics: dict[str, float] = Field(default_factory=dict)
    
    # Status
    status: VariantStatus = Field(default=VariantStatus.ACTIVE)
    created_at: datetime = Field(default_factory=utcnow)


class ABTest(Document):
    """A/B Test experiment document"""
    
    # Identification
    experiment_id: Annotated[str, Indexed()] = Field(description="Unique experiment ID")
    name: str = Field(description="Experiment name")
    description: str | None = Field(None, description="Experiment description")
    
    # Ownership
    user_id: str = Field(description="User who created the experiment")
    workspace_id: str | None = Field(None, description="Workspace ID for team experiments")
    
    # Configuration
    variants: list[Variant] = Field(description="List of variants in the test")
    primary_metric: str = Field(description="Primary metric for comparison")
    secondary_metrics: list[str] = Field(default_factory=list)
    
    # Test settings
    min_sample_size: int = Field(default=1000, description="Minimum samples per variant")
    confidence_level: float = Field(default=0.95, description="Statistical confidence level")
    test_duration_hours: int | None = Field(None, description="Max test duration")
    
    # Status and timing
    status: ExperimentStatus = Field(default=ExperimentStatus.DRAFT)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    
    # Results
    winner_variant_id: str | None = None
    statistical_significance: float | None = None
    lift_percentage: float | None = None
    
    # Metadata
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    tags: list[str] = Field(default_factory=list)
    
    class Settings:
        name = "ab_tests"
        indexes = [
            "experiment_id",
            "user_id",
            "status",
            "created_at"
        ]
    
    def get_variant_by_id(self, variant_id: str) -> Variant | None:
        """Get a specific variant by ID"""
        for variant in self.variants:
            if variant.variant_id == variant_id:
                return variant
        return None
    
    def get_active_variants(self) -> list[Variant]:
        """Get all active variants"""
        return [v for v in self.variants if v.status == VariantStatus.ACTIVE]
    
    def calculate_total_traffic(self) -> float:
        """Calculate total traffic percentage across all variants"""
        return sum(v.traffic_percentage for v in self.variants)
    
    def is_valid_configuration(self) -> bool:
        """Check if the experiment configuration is valid"""
        total_traffic = self.calculate_total_traffic()
        return abs(total_traffic - 100.0) < 0.01  # Allow small floating point errors