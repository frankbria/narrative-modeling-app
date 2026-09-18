# app/models/user_data.py

from datetime import UTC, datetime
from typing import Any

from beanie import (
    Document,
    Indexed,
    Insert,
    PydanticObjectId,
    Save,
    after_event,
    before_event,
)
from pydantic import BaseModel, Field, PrivateAttr

from app.utils.filenames import SafeFilename


def get_current_time() -> datetime:
    return datetime.now(UTC)


class SchemaField(BaseModel):
    field_name: str
    field_type: str  # 'numeric', 'text', 'boolean', 'datetime', 'categorical'
    data_type: str | None = None  # 'nominal', 'ordinal', 'interval', 'ratio'
    inferred_dtype: str
    unique_values: int
    missing_values: int
    example_values: list[Any]
    is_constant: bool
    is_high_cardinality: bool


class AISummary(BaseModel):
    """Model for storing AI-generated summaries of datasets"""

    overview: str
    issues: list[str]
    relationships: list[str]
    suggestions: list[str]
    rawMarkdown: str
    createdAt: datetime = Field(default_factory=get_current_time)


class UserData(Document):
    """Model for storing user uploaded data metadata"""

    user_id: str = Indexed(str)
    filename: SafeFilename
    original_filename: SafeFilename  # client filename, normalised at ingestion (#585)

    s3_url: str
    num_rows: int
    num_columns: int
    data_schema: list[SchemaField]
    created_at: datetime = Field(default_factory=get_current_time)
    updated_at: datetime = Field(default_factory=get_current_time)
    aiSummary: AISummary | None = None
    
    # PII-related fields
    contains_pii: bool = False
    pii_report: dict[str, Any] | None = None
    pii_risk_level: str | None = None  # "low", "medium", "high"
    pii_masked: bool = False
    
    # Data processing fields
    is_processed: bool = False
    processed_at: datetime | None = None
    schema: dict[str, Any] | None = None  # Inferred schema from data processing
    statistics: dict[str, Any] | None = None  # Calculated statistics
    quality_report: dict[str, Any] | None = None  # Data quality assessment
    row_count: int | None = None  # Actual row count after processing
    columns: list[str] | None = None  # Column names after processing
    data_preview: list[dict[str, Any]] | None = None  # Preview rows
    file_type: str | None = None  # csv, excel, json, etc.
    #: Bytes of the stored object, counted against the FREE storage ceiling (#768).
    #: None on rows written before it existed — those count as 0.
    file_size: int | None = None
    
    # Onboarding progress
    onboarding_progress: dict[str, Any] | None = None  # User's onboarding tutorial progress
    
    # Transformation tracking
    file_path: str | None = None  # Current file path (S3 key)
    # Every previous s3_url this dataset moved through as transformations rewrote its
    # current file — tracked so erasure can delete these now-unreferenced objects (#525).
    superseded_s3_urls: list[str] = Field(default_factory=list)
    transformation_history: list[dict[str, Any]] = Field(default_factory=list)  # History of transformations applied

    _is_new: bool = PrivateAttr(default=False)

    # Save too: `save()` on a new document is an upsert, not an insert, and fires no
    # Insert event — that is how /datasets/upload creates its row. Only a creation
    # records, so the many later saves (AI summary, processing) cost nothing.
    @before_event(Insert, Save)
    def _note_creation(self) -> None:
        # Relies on no writer pre-assigning an id before the first write.
        self._is_new = self.id is None

    @after_event(Insert, Save)
    async def _record_first_upload(self) -> None:
        # Here rather than in each route, so every dataset writer is covered (#769).
        if not self._is_new:
            return
        self._is_new = False
        from app.services import product_events

        await product_events.record(
            self.user_id, product_events.FIRST_UPLOAD, once=product_events.FIRST_UPLOAD
        )

    class Settings:
        name = "user_data"
        # Re-run the field validators on save()/replace() (#585): a route that
        # setattr()s a client value onto a loaded document would otherwise skip
        # them — Pydantic validates on construction, not on assignment.
        validate_on_save = True
        indexes = [
            "user_id",
            "created_at",
            # the dual-write join to DatasetMetadata (#467): looked up on every file move
            [("user_id", 1), ("s3_url", 1)],
        ]

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {
            PydanticObjectId: str
        }
    }
