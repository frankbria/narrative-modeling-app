"""
Enhanced dataset summarization service using AI
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from openai import OpenAI, OpenAIError

from app.services.data_processing.schema_inference import SchemaDefinition
from app.services.data_processing.statistics_engine import DatasetStatistics
from app.services.data_processing.quality_assessment import QualityReport
from app.models.user_data import AISummary
from app.utils.circuit_breaker import with_circuit_breaker

logger = logging.getLogger(__name__)


class DatasetSummaryRequest(BaseModel):
    """Request model for dataset summarization"""
    file_id: str
    schema: Union[Dict[str, Any], SchemaDefinition]
    statistics: Union[Dict[str, Any], DatasetStatistics]
    quality_report: Union[Dict[str, Any], QualityReport]
    sample_data: Optional[List[Dict[str, Any]]] = None
    focus_areas: Optional[List[str]] = Field(
        default=["patterns", "quality", "relationships", "recommendations"]
    )
    max_tokens: int = Field(default=2500, ge=500, le=4000)


class EnhancedAISummary(AISummary):
    """Enhanced AI summary with additional metadata"""
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    analysis_depth: str = Field(default="standard", pattern="^(basic|standard|comprehensive)$")
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    model_used: str = Field(default="gpt-4")
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
            self.client = OpenAI(api_key=api_key)
            
        self.model = os.getenv("OPENAI_MODEL", "gpt-4-turbo")
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
        start_time = datetime.now(timezone.utc)
        
        try:
            # Prepare the dataset context
            context = self._prepare_context(request)
            
            # Generate AI summary
            if self.client:
                summary = await self._generate_openai_summary(context, request)
            else:
                summary = self._generate_fallback_summary(context)
            
            # Calculate processing time
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            summary.processing_time = processing_time
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generating dataset summary: {e}")
            return self._create_error_summary(str(e))
    
    def _prepare_context(self, request: DatasetSummaryRequest) -> Dict[str, Any]:
        """Prepare context for AI summarization"""
        # Convert models to dicts if needed
        schema = request.schema
        if hasattr(schema, 'model_dump'):
            schema = schema.model_dump()
        elif hasattr(schema, 'dict'):
            schema = schema.dict()
            
        statistics = request.statistics
        if hasattr(statistics, 'model_dump'):
            statistics = statistics.model_dump()
        elif hasattr(statistics, 'dict'):
            statistics = statistics.dict()
            
        quality_report = request.quality_report
        if hasattr(quality_report, 'model_dump'):
            quality_report = quality_report.model_dump()
        elif hasattr(quality_report, 'dict'):
            quality_report = quality_report.dict()
        
        context = {
            "file_id": request.file_id,
            "dataset_overview": {
                "row_count": schema.get("row_count", 0),
                "column_count": schema.get("column_count", 0),
                "file_type": schema.get("file_type", "unknown")
            },
            "column_details": self._extract_column_details(schema),
            "data_quality": self._extract_quality_insights(quality_report),
            "statistical_summary": self._extract_statistical_highlights(statistics),
            "sample_data": request.sample_data[:5] if request.sample_data else None
        }
        
        return context
    
    def _extract_column_details(self, schema: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract important column details from schema"""
        columns = []
        
        for col in schema.get("columns", []):
            columns.append({
                "name": col.get("name"),
                "type": col.get("data_type"),
                "nullable": col.get("nullable"),
                "unique": col.get("unique"),
                "cardinality": col.get("cardinality"),
                "null_percentage": col.get("null_percentage", 0)
            })
        
        return columns
    
    def _extract_quality_insights(self, quality_report: Dict[str, Any]) -> Dict[str, Any]:
        """Extract key quality insights"""
        return {
            "overall_score": quality_report.get("overall_quality_score", 0),
            "critical_issues": len(quality_report.get("critical_issues", [])),
            "warnings": len(quality_report.get("warnings", [])),
            "recommendations": quality_report.get("recommendations", [])[:3],
            "dimension_scores": quality_report.get("dimension_scores", {})
        }
    
    def _extract_statistical_highlights(self, statistics: Dict[str, Any]) -> Dict[str, Any]:
        """Extract statistical highlights"""
        highlights = {
            "missing_data_summary": statistics.get("missing_value_summary", {}),
            "correlations": [],
            "outlier_columns": []
        }
        
        # Extract high correlations
        correlation_matrix = statistics.get("correlation_matrix", {})
        for col1, correlations in correlation_matrix.items():
            for col2, corr_value in correlations.items():
                if col1 != col2 and abs(corr_value) > 0.7:
                    highlights["correlations"].append({
                        "columns": [col1, col2],
                        "correlation": corr_value
                    })
        
        # Extract columns with outliers
        for col_stats in statistics.get("column_statistics", []):
            if col_stats.get("outlier_count", 0) > 0:
                highlights["outlier_columns"].append({
                    "column": col_stats.get("column_name"),
                    "outlier_count": col_stats.get("outlier_count"),
                    "outlier_percentage": col_stats.get("outlier_percentage")
                })
        
        return highlights

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
        context: Dict[str, Any],
        request: DatasetSummaryRequest
    ) -> EnhancedAISummary:
        """Generate summary using OpenAI"""
        # Create prompts
        system_prompt = self._create_system_prompt(request.focus_areas)
        user_prompt = self._create_user_prompt(context)
        
        try:
            response = self.client.chat.completions.create(
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
    
    def _create_system_prompt(self, focus_areas: List[str]) -> str:
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
    
    def _create_user_prompt(self, context: Dict[str, Any]) -> str:
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
    
    def _generate_fallback_summary(self, context: Dict[str, Any]) -> EnhancedAISummary:
        """Generate basic summary without AI"""
        overview = f"Dataset contains {context['dataset_overview']['row_count']:,} rows and {context['dataset_overview']['column_count']} columns."
        
        issues = []
        if context['data_quality']['critical_issues'] > 0:
            issues.append(f"Found {context['data_quality']['critical_issues']} critical data quality issues")
        if context['data_quality']['overall_score'] < 0.8:
            issues.append(f"Data quality score is {context['data_quality']['overall_score']:.2f}, below recommended threshold")
        
        relationships = []
        for corr in context['statistical_summary']['correlations'][:3]:
            relationships.append(
                f"Strong correlation ({corr['correlation']:.2f}) between {corr['columns'][0]} and {corr['columns'][1]}"
            )
        
        suggestions = context['data_quality']['recommendations']
        
        return EnhancedAISummary(
            overview=overview,
            issues=issues,
            relationships=relationships,
            suggestions=suggestions,
            rawMarkdown=self._create_fallback_markdown(context),
            confidence_score=0.6,
            analysis_depth="basic",
            model_used="fallback"
        )
    
    def _create_fallback_markdown(self, context: Dict[str, Any]) -> str:
        """Create basic markdown analysis"""
        return f"""# Dataset Analysis

## Overview
- **Rows**: {context['dataset_overview']['row_count']:,}
- **Columns**: {context['dataset_overview']['column_count']}
- **File Type**: {context['dataset_overview']['file_type']}

## Data Quality
- **Overall Score**: {context['data_quality']['overall_score']:.2f}
- **Critical Issues**: {context['data_quality']['critical_issues']}
- **Warnings**: {context['data_quality']['warnings']}

## Key Findings
This is a basic analysis generated without AI assistance. For more detailed insights, ensure OpenAI API access is configured.
"""
    
    def _calculate_confidence(self, context: Dict[str, Any]) -> float:
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
    
    def _create_error_summary(self, error_message: str) -> EnhancedAISummary:
        """Create error summary"""
        return EnhancedAISummary(
            overview="Failed to generate dataset summary",
            issues=[f"Error: {error_message}"],
            relationships=[],
            suggestions=["Check logs for error details", "Ensure all required data is available"],
            rawMarkdown=f"# Error\n\nFailed to generate summary: {error_message}",
            confidence_score=0.0,
            analysis_depth="basic",
            model_used="error"
        )


# Singleton instance
dataset_summarization_service = DatasetSummarizationService()