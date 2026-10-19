"""
Enhanced dataset summarization service using AI
"""

import asyncio
import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

from openai import OpenAIError
from pydantic import BaseModel, Field

from app.middleware.error_handlers import internal_error_message
from app.models.user_data import AISummary
from app.utils.circuit_breaker import CircuitBreakerOpen, with_circuit_breaker
from app.utils.datetime import utcnow
from app.utils.field_shadows import expect_field_shadow
from app.utils.openai_client import build_openai_client, openai_model

logger = logging.getLogger(__name__)


expect_field_shadow("schema", "DatasetSummaryRequest")


class DatasetSummaryRequest(BaseModel):
    """Request model for dataset summarization"""
    file_id: str
    # `schema` shadows Pydantic's deprecated `BaseModel.schema()`; it is part of
    # the public request contract and cannot be renamed.
    # Each part is what processing stored on the dataset, or nothing: a processed
    # dataset can hold null for a part processing could not produce (#981).
    schema: dict[str, Any] | None = None  # type: ignore[assignment]
    statistics: dict[str, Any] | None = None
    quality_report: dict[str, Any] | None = None
    sample_data: list[dict[str, Any]] | None = None
    focus_areas: list[str] | None = Field(
        default=["patterns", "quality", "relationships", "recommendations"]
    )
    max_tokens: int = Field(default=2500, ge=500, le=4000)


class EnhancedAISummary(AISummary):
    """Enhanced AI summary with additional metadata"""
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    analysis_depth: str = Field(default="standard", pattern="^(basic|standard|comprehensive)$")
    generated_at: datetime = Field(default_factory=utcnow)
    model_used: str = Field(default_factory=openai_model)
    processing_time: float = Field(default=0.0)


class DatasetSummarizationService:
    """Service for generating AI-powered dataset summaries"""
    
    def __init__(self):
        """Initialize the summarization service"""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not set - AI summaries will be limited")
            self.client = None
        else:
            self.client = build_openai_client(api_key)
            
        self.model = openai_model()
        logger.info(f"Using OpenAI model: {self.model}")
    
    async def generate_comprehensive_summary(
        self,
        request: DatasetSummaryRequest
    ) -> EnhancedAISummary:
        """
        Generate a comprehensive AI summary of the dataset
        
        Args:
            request: Dataset summary request with schema, stats, and quality info
            
        Returns:
            Enhanced AI summary with insights and recommendations
        """
        start_time = datetime.now(UTC)
        
        try:
            # Prepare the dataset context
            context = self._prepare_context(request)
            
            # Generate AI summary
            summary = None
            if self.client:
                try:
                    summary = await self._generate_openai_summary(context, request)
                except CircuitBreakerOpen as exc:
                    # Includes the global daily AI ceiling (#768): serve the
                    # rule-based summary rather than an error summary.
                    logger.warning(f"OpenAI summary unavailable, using fallback: {exc}")
            if summary is None:
                summary = self._generate_fallback_summary(context)
            
            # Calculate processing time
            processing_time = (datetime.now(UTC) - start_time).total_seconds()
            summary.processing_time = processing_time
            
            return summary
            
        except Exception:
            logger.exception("Dataset summary failed for %s", request.file_id)
            return self._create_error_summary()
    
    @staticmethod
    def _stored(source: dict[str, Any] | None, key: str, default: Any) -> Any:
        """What processing stored under ``key``, or ``default`` when it stored nothing.

        Processing writes an explicit null for what it could not compute (no
        correlation matrix under two numeric columns, no outlier count for text), and
        ``.get(key, default)`` returns that null, not the default. One such read used
        to turn the whole summary into the error card (#409, #981).
        """
        value = (source or {}).get(key)
        return default if value is None else value

    def _prepare_context(self, request: DatasetSummaryRequest) -> dict[str, Any]:
        """Prepare context for AI summarization"""
        schema = request.schema
        context = {
            "file_id": request.file_id,
            "dataset_overview": {
                "row_count": self._stored(schema, "row_count", 0),
                "column_count": self._stored(schema, "column_count", 0),
                "file_type": self._stored(schema, "file_type", "unknown")
            },
            "column_details": self._extract_column_details(schema),
            "data_quality": self._extract_quality_insights(request.quality_report),
            "statistical_summary": self._extract_statistical_highlights(request.statistics),
            "sample_data": request.sample_data[:5] if request.sample_data else None
        }

        return context

    def _extract_column_details(self, schema: dict[str, Any] | None) -> list[dict[str, Any]]:
        """Extract important column details from schema"""
        columns = []

        for col in self._stored(schema, "columns", []):
            columns.append({
                "name": col.get("name"),
                "type": col.get("data_type"),
                "nullable": col.get("nullable"),
                "unique": col.get("unique"),
                "cardinality": col.get("cardinality"),
                "null_percentage": self._stored(col, "null_percentage", 0)
            })

        return columns

    def _extract_quality_insights(self, quality_report: dict[str, Any] | None) -> dict[str, Any]:
        """Extract key quality insights"""
        return {
            "overall_score": self._stored(quality_report, "overall_quality_score", 0),
            "critical_issues": len(self._stored(quality_report, "critical_issues", [])),
            "warnings": len(self._stored(quality_report, "warnings", [])),
            "recommendations": self._stored(quality_report, "recommendations", [])[:3],
            "dimension_scores": self._stored(quality_report, "dimension_scores", {})
        }

    def _extract_statistical_highlights(self, statistics: dict[str, Any] | None) -> dict[str, Any]:
        """Extract statistical highlights"""
        return {
            "missing_data_summary": self._stored(statistics, "missing_value_summary", {}),
            "correlations": self._strong_correlations(self._stored(statistics, "correlation_matrix", {})),
            "outlier_columns": self._outlier_columns(self._stored(statistics, "column_statistics", [])),
        }

    @staticmethod
    def _is_strong(first: str, second: str, value: float | None) -> bool:
        """A correlation worth reporting. A pair with a non-numeric column is stored as null."""
        return first != second and value is not None and abs(value) > 0.7

    def _strong_correlations(self, matrix: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {"columns": [first, second], "correlation": value}
            for first, row in matrix.items()
            for second, value in row.items()
            if self._is_strong(first, second, value)
        ]

    def _outlier_columns(self, column_statistics: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Columns with outliers. A text column stores ``outlier_count: null`` (#409)."""
        return [
            {
                "column": stats.get("column_name"),
                "outlier_count": stats.get("outlier_count"),
                "outlier_percentage": stats.get("outlier_percentage"),
            }
            for stats in column_statistics
            if self._stored(stats, "outlier_count", 0) > 0
        ]

    @with_circuit_breaker(
        "openai",
        max_attempts=3,
        failure_threshold=5,
        recovery_timeout=60.0,
        exceptions=(OpenAIError, Exception),
        fallback_value=None
    )
    async def _generate_openai_summary(
        self,
        context: dict[str, Any],
        request: DatasetSummaryRequest
    ) -> EnhancedAISummary:
        """Generate summary using OpenAI"""
        # Create prompts
        system_prompt = self._create_system_prompt(
            request.focus_areas
            or ["patterns", "quality", "relationships", "recommendations"]
        )
        user_prompt = self._create_user_prompt(context)
        
        try:
            # Off the event loop: the OpenAI client is synchronous and this is an
            # async method, so an inline call would block the worker (#501).
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=request.max_tokens,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            summary_data = json.loads(content)
            
            return EnhancedAISummary(
                overview=summary_data.get("overview", ""),
                issues=summary_data.get("issues", []),
                relationships=summary_data.get("relationships", []),
                suggestions=summary_data.get("suggestions", []),
                rawMarkdown=summary_data.get("detailed_analysis", ""),
                confidence_score=self._calculate_confidence(context),
                analysis_depth="comprehensive",
                model_used=self.model
            )
            
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return self._generate_fallback_summary(context)
    
    def _create_system_prompt(self, focus_areas: list[str]) -> str:
        """Create system prompt for OpenAI"""
        focus_string = ", ".join(focus_areas)
        
        return f"""You are an expert data analyst specializing in exploratory data analysis and data quality assessment.
        
Your task is to analyze dataset information and provide comprehensive insights focusing on: {focus_string}.

Respond in JSON format with the following structure:
{{
    "overview": "A concise 2-3 sentence overview of the dataset and its main characteristics",
    "issues": ["Array of identified data quality issues or concerns, max 5 items"],
    "relationships": ["Array of discovered relationships or patterns between variables, max 5 items"],
    "suggestions": ["Array of actionable recommendations for analysis or data improvement, max 5 items"],
    "detailed_analysis": "A comprehensive markdown analysis covering all aspects of the data"
}}

Be specific, quantitative where possible, and focus on actionable insights. The detailed_analysis should be thorough but well-structured."""
    
    def _create_user_prompt(self, context: dict[str, Any]) -> str:
        """Create user prompt with dataset context"""
        context_json = json.dumps(context, indent=2)
        
        return f"""Please analyze this dataset and provide comprehensive insights:

{context_json}

Focus on:
1. Data quality issues and their potential impact
2. Statistical patterns and relationships
3. Recommendations for data cleaning or transformation
4. Potential use cases or analysis approaches
5. Any unusual patterns or outliers that need attention"""
    
    def _fallback_figures(self, context: dict[str, Any]) -> dict[str, Any]:
        """What the rule-based summary prints, each read as stored-or-default (#1076)."""
        overview = self._stored(context, "dataset_overview", {})
        quality = self._stored(context, "data_quality", {})
        return {
            "rows": self._stored(overview, "row_count", 0),
            "columns": self._stored(overview, "column_count", 0),
            "file_type": self._stored(overview, "file_type", "unknown"),
            "score": self._stored(quality, "overall_score", 0),
            "critical": self._stored(quality, "critical_issues", 0),
            "warnings": self._stored(quality, "warnings", 0),
            "recommendations": self._stored(quality, "recommendations", []),
            "correlations": self._stored(self._stored(context, "statistical_summary", {}), "correlations", []),
        }

    def _generate_fallback_summary(self, context: dict[str, Any]) -> EnhancedAISummary:
        """Generate basic summary without AI"""
        f = self._fallback_figures(context)
        overview = f"Dataset contains {f['rows']:,} rows and {f['columns']} columns."

        issues = []
        if f["critical"] > 0:
            issues.append(f"Found {f['critical']} critical data quality issues")
        if f["score"] < 0.8:
            issues.append(f"Data quality score is {f['score']:.2f}, below recommended threshold")

        relationships = [
            f"Strong correlation ({corr['correlation']:.2f}) between {corr['columns'][0]} and {corr['columns'][1]}"
            for corr in f["correlations"][:3]
        ]

        return EnhancedAISummary(
            overview=overview,
            issues=issues,
            relationships=relationships,
            suggestions=f["recommendations"],
            rawMarkdown=self._create_fallback_markdown(context),
            confidence_score=0.6,
            analysis_depth="basic",
            model_used="fallback"
        )

    def _create_fallback_markdown(self, context: dict[str, Any]) -> str:
        """Create basic markdown analysis"""
        f = self._fallback_figures(context)
        return f"""# Dataset Analysis

## Overview
- **Rows**: {f['rows']:,}
- **Columns**: {f['columns']}
- **File Type**: {f['file_type']}

## Data Quality
- **Overall Score**: {f['score']:.2f}
- **Critical Issues**: {f['critical']}
- **Warnings**: {f['warnings']}

## Key Findings
This is a basic analysis generated without AI assistance. For more detailed insights, ensure OpenAI API access is configured.
"""
    
    def _calculate_confidence(self, context: dict[str, Any]) -> float:
        """Calculate confidence score based on data completeness"""
        score = 0.5  # Base score
        
        # Add points for data availability
        if context.get('sample_data'):
            score += 0.1
        if context['dataset_overview']['row_count'] > 100:
            score += 0.1
        if context['data_quality']['overall_score'] > 0.8:
            score += 0.2
        if len(context['statistical_summary']['correlations']) > 0:
            score += 0.1
            
        return min(score, 1.0)
    
    def _create_error_summary(self) -> EnhancedAISummary:
        """What the caller gets when the summary could not be made. This is a 200
        body, which the 5xx sanitiser never sees, so it carries a fixed sentence and
        the request's reference; the exception is in the log (#637, #981)."""
        reason = internal_error_message("The summary")
        return EnhancedAISummary(
            overview="The summary could not be generated for this dataset.",
            issues=[reason],
            relationships=[],
            suggestions=["Try again. If it keeps failing, contact support and quote the reference above."],
            rawMarkdown=f"# Summary unavailable\n\n{reason}",
            confidence_score=0.0,
            analysis_depth="basic",
            model_used="error"
        )


# Singleton instance
dataset_summarization_service = DatasetSummarizationService()