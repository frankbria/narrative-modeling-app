"""
Tests for dataset summarization service
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from app.services.dataset_summarization import (
    DatasetSummarizationService,
    DatasetSummaryRequest,
    EnhancedAISummary
)


@pytest.fixture
def summarization_service():
    """Create dataset summarization service instance"""
    with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
        return DatasetSummarizationService()


@pytest.fixture
def sample_request():
    """Create sample summary request"""
    return DatasetSummaryRequest(
        file_id="test-file-123",
        schema={
            "row_count": 1000,
            "column_count": 10,
            "file_type": "csv",
            "columns": [
                {
                    "name": "id",
                    "data_type": "integer",
                    "nullable": False,
                    "unique": True,
                    "cardinality": 1000,
                    "null_percentage": 0
                },
                {
                    "name": "value",
                    "data_type": "float",
                    "nullable": True,
                    "unique": False,
                    "cardinality": 500,
                    "null_percentage": 5.0
                }
            ]
        },
        statistics={
            "column_statistics": [
                {
                    "column_name": "id",
                    "mean": 500.5,
                    "outlier_count": 0,
                    "outlier_percentage": 0
                },
                {
                    "column_name": "value",
                    "mean": 100.0,
                    "outlier_count": 10,
                    "outlier_percentage": 1.0
                }
            ],
            "correlation_matrix": {
                "id": {"id": 1.0, "value": 0.85},
                "value": {"id": 0.85, "value": 1.0}
            },
            "missing_value_summary": {
                "total_missing_values": 50,
                "columns_with_missing": 1
            }
        },
        quality_report={
            "overall_quality_score": 0.92,
            "critical_issues": [],
            "warnings": [
                {
                    "dimension": "completeness",
                    "description": "5% missing values in 'value' column"
                }
            ],
            "recommendations": [
                "Consider imputing missing values in 'value' column",
                "Strong correlation between 'id' and 'value' detected"
            ],
            "dimension_scores": {
                "completeness": 0.95,
                "validity": 0.98,
                "accuracy": 0.90,
                "consistency": 0.95
            }
        },
        sample_data=[
            {"id": 1, "value": 100.5},
            {"id": 2, "value": 102.3},
            {"id": 3, "value": None}
        ]
    )


class TestDatasetSummarizationService:
    """Test dataset summarization functionality"""

    async def test_prepare_context(self, summarization_service, sample_request):
        """Test context preparation"""
        context = summarization_service._prepare_context(sample_request)
        
        assert context["file_id"] == "test-file-123"
        assert context["dataset_overview"]["row_count"] == 1000
        assert context["dataset_overview"]["column_count"] == 10
        assert len(context["column_details"]) == 2
        assert context["data_quality"]["overall_score"] == 0.92
        assert len(context["statistical_summary"]["correlations"]) > 0
        assert len(context["sample_data"]) == 3

    async def test_extract_column_details(self, summarization_service, sample_request):
        """Test column detail extraction"""
        columns = summarization_service._extract_column_details(sample_request.schema)
        
        assert len(columns) == 2
        assert columns[0]["name"] == "id"
        assert columns[0]["type"] == "integer"
        assert columns[0]["unique"] is True
        assert columns[1]["null_percentage"] == 5.0

    async def test_extract_quality_insights(self, summarization_service, sample_request):
        """Test quality insight extraction"""
        insights = summarization_service._extract_quality_insights(sample_request.quality_report)
        
        assert insights["overall_score"] == 0.92
        assert insights["critical_issues"] == 0
        assert insights["warnings"] == 1
        assert len(insights["recommendations"]) == 2
        assert "completeness" in insights["dimension_scores"]

    async def test_extract_statistical_highlights(self, summarization_service, sample_request):
        """Test statistical highlight extraction"""
        highlights = summarization_service._extract_statistical_highlights(sample_request.statistics)
        
        assert len(highlights["correlations"]) == 2  # Both directions of correlation
        assert highlights["correlations"][0]["correlation"] == 0.85
        assert len(highlights["outlier_columns"]) == 1
        assert highlights["outlier_columns"][0]["column"] == "value"

    async def test_generate_comprehensive_summary_with_openai(self, summarization_service, sample_request):
        """Test summary generation with OpenAI"""
        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="""{
                "overview": "Dataset contains 1000 rows with strong correlation patterns.",
                "issues": ["5% missing values in value column"],
                "relationships": ["Strong positive correlation between id and value"],
                "suggestions": ["Consider imputing missing values"],
                "detailed_analysis": "# Detailed Analysis\\n\\nThe dataset shows interesting patterns..."
            }"""))
        ]
        
        with patch.object(summarization_service.client.chat.completions, 'create', return_value=mock_response):
            summary = await summarization_service.generate_comprehensive_summary(sample_request)
            
            assert isinstance(summary, EnhancedAISummary)
            assert "1000 rows" in summary.overview
            assert len(summary.issues) == 1
            assert len(summary.relationships) == 1
            assert summary.confidence_score > 0.5
            assert summary.analysis_depth == "comprehensive"
            assert summary.model_used == "gpt-4-turbo"

    async def test_generate_fallback_summary(self, summarization_service, sample_request):
        """Test fallback summary generation"""
        # Disable OpenAI client
        summarization_service.client = None
        
        summary = await summarization_service.generate_comprehensive_summary(sample_request)
        
        assert isinstance(summary, EnhancedAISummary)
        assert summary.analysis_depth == "basic"
        assert summary.model_used == "fallback"
        assert summary.confidence_score == 0.6
        assert "1,000 rows and 10 columns" in summary.overview

    async def test_create_system_prompt(self, summarization_service):
        """Test system prompt creation"""
        focus_areas = ["patterns", "quality"]
        prompt = summarization_service._create_system_prompt(focus_areas)
        
        assert "patterns, quality" in prompt
        assert "JSON format" in prompt
        assert "overview" in prompt
        assert "issues" in prompt

    async def test_calculate_confidence(self, summarization_service, sample_request):
        """Test confidence score calculation"""
        context = summarization_service._prepare_context(sample_request)
        confidence = summarization_service._calculate_confidence(context)
        
        # Should get points for: sample data (0.1), >100 rows (0.1), quality >0.8 (0.2), correlations (0.1)
        assert confidence >= 0.9

    async def test_error_handling(self, summarization_service, sample_request):
        """Test error handling in summary generation"""
        # Mock OpenAI to raise an error
        with patch.object(
            summarization_service.client.chat.completions, 
            'create', 
            side_effect=Exception("API Error")
        ):
            summary = await summarization_service.generate_comprehensive_summary(sample_request)
            
            # Should fall back to basic summary
            assert summary.analysis_depth == "basic"
            assert summary.model_used == "fallback"

    async def test_no_api_key_initialization(self):
        """Test service initialization without API key"""
        with patch.dict('os.environ', {}, clear=True):
            service = DatasetSummarizationService()
            assert service.client is None
            
            # Should still work with fallback
            summary = await service.generate_comprehensive_summary(
                DatasetSummaryRequest(
                    file_id="test",
                    schema={"row_count": 10, "column_count": 2, "columns": []},
                    statistics={},
                    quality_report={"overall_quality_score": 0.8}
                )
            )
            
            assert summary.model_used == "fallback"

    async def test_processing_time_tracking(self, summarization_service, sample_request):
        """Test that processing time is tracked"""
        summary = await summarization_service.generate_comprehensive_summary(sample_request)
        
        assert summary.processing_time > 0
        assert isinstance(summary.generated_at, datetime)