"""
A/B Test model for experiment tracking
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from beanie import Document, Indexed, PydanticObjectId
from pydantic import Field, BaseModel
from enum import Enum


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
    description: Optional[str] = Field(None, description="Variant description")
    traffic_percentage: float = Field(description="Traffic allocation percentage")
    
    # Performance metrics
    total_predictions: int = Field(default=0)
    total_latency_ms: float = Field(default=0)
    error_count: int = Field(default=0)
    
    # Business metrics (customizable)
    custom_metrics: Dict[str, float] = Field(default_factory=dict)
    
    # Status
    status: VariantStatus = Field(default=VariantStatus.ACTIVE)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ABTest(Document):
    """A/B Test experiment document"""
    
    # Identification
    experiment_id: Indexed(str) = Field(description="Unique experiment ID")
    name: str = Field(description="Experiment name")
    description: Optional[str] = Field(None, description="Experiment description")
    
    # Ownership
    user_id: str = Field(description="User who created the experiment")
    workspace_id: Optional[str] = Field(None, description="Workspace ID for team experiments")
    
    # Configuration
    variants: List[Variant] = Field(description="List of variants in the test")
    primary_metric: str = Field(description="Primary metric for comparison")
    secondary_metrics: List[str] = Field(default_factory=list)
    
    # Test settings
    min_sample_size: int = Field(default=1000, description="Minimum samples per variant")
    confidence_level: float = Field(default=0.95, description="Statistical confidence level")
    test_duration_hours: Optional[int] = Field(None, description="Max test duration")
    
    # Status and timing
    status: ExperimentStatus = Field(default=ExperimentStatus.DRAFT)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    
    # Results
    winner_variant_id: Optional[str] = None
    statistical_significance: Optional[float] = None
    lift_percentage: Optional[float] = None
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    tags: List[str] = Field(default_factory=list)
    
    class Settings:
        name = "ab_tests"
        indexes = [
            "experiment_id",
            "user_id",
            "status",
            "created_at"
        ]
    
    def get_variant_by_id(self, variant_id: str) -> Optional[Variant]:
        """Get a specific variant by ID"""
        for variant in self.variants:
            if variant.variant_id == variant_id:
                return variant
        return None
    
    def get_active_variants(self) -> List[Variant]:
        """Get all active variants"""
        return [v for v in self.variants if v.status == VariantStatus.ACTIVE]
    
    def calculate_total_traffic(self) -> float:
        """Calculate total traffic percentage across all variants"""
        return sum(v.traffic_percentage for v in self.variants)
    
    def is_valid_configuration(self) -> bool:
        """Check if the experiment configuration is valid"""
        total_traffic = self.calculate_total_traffic()
        return abs(total_traffic - 100.0) < 0.01  # Allow small floating point errors