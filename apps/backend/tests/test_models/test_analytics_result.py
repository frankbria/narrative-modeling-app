import pytest
from datetime import datetime, timezone
from beanie import PydanticObjectId, Link
from app.models.analytics_result import AnalyticsResult
from app.models.user_data import UserData
from app.models.plot import Plot


def test_analytics_result_creation():
    """Test creating an AnalyticsResult instance with all fields."""
    current_time = datetime.now(timezone.utc)
    dataset_id = PydanticObjectId()
    plot_id = PydanticObjectId()

    analytics_result = AnalyticsResult(
        userId="test_user_123",
        datasetId=Link[UserData](dataset_id),
        createdAt=current_time,
        analysisType="EDA",
        config={"param1": "value1", "param2": "value2"},
        result={"summary": "Test analysis result", "metrics": {"accuracy": 0.95}},
        plotRefs=[Link[Plot](plot_id)],
        summaryText="This is a test analysis summary",
    )

    assert analytics_result.userId == "test_user_123"
    assert analytics_result.datasetId == Link[UserData](dataset_id)
    assert analytics_result.createdAt == current_time
    assert analytics_result.analysisType == "EDA"
    assert analytics_result.config == {"param1": "value1", "param2": "value2"}
    assert analytics_result.result == {
        "summary": "Test analysis result",
        "metrics": {"accuracy": 0.95},
    }
    assert len(analytics_result.plotRefs) == 1
    assert analytics_result.plotRefs[0] == Link[Plot](plot_id)
    assert analytics_result.summaryText == "This is a test analysis summary"


def test_analytics_result_optional_fields():
    """Test creating an AnalyticsResult instance with optional fields."""
    analytics_result = AnalyticsResult(
        userId="test_user_123",
        datasetId=Link[UserData](PydanticObjectId()),
        analysisType="EDA",
    )

    assert analytics_result.userId == "test_user_123"
    assert analytics_result.config is None
    assert analytics_result.result is None
    assert analytics_result.plotRefs is None
    assert analytics_result.summaryText is None


def test_analytics_result_default_timestamp():
    """Test that AnalyticsResult automatically sets the createdAt timestamp."""
    analytics_result = AnalyticsResult(
        userId="test_user_123",
        datasetId=Link[UserData](PydanticObjectId()),
        analysisType="EDA",
    )

    assert isinstance(analytics_result.createdAt, datetime)
    assert analytics_result.createdAt.tzinfo == timezone.utc


def test_analytics_result_model_settings():
    """Test AnalyticsResult model settings."""
    assert AnalyticsResult.Settings.name == "analytics_results"


def test_analytics_result_model_config():
    """Test AnalyticsResult model configuration."""
    assert AnalyticsResult.model_config["populate_by_name"] is True
    assert AnalyticsResult.model_config["arbitrary_types_allowed"] is True


def test_analytics_result_with_different_analysis_types():
    """Test AnalyticsResult with different analysis types."""
    # Test with EDA analysis type
    eda_result = AnalyticsResult(
        userId="test_user_123",
        datasetId=Link[UserData](PydanticObjectId()),
        analysisType="EDA",
        config={"visualization_type": "histogram"},
        result={"summary": "EDA analysis complete"},
    )
    assert eda_result.analysisType == "EDA"

    # Test with regression analysis type
    regression_result = AnalyticsResult(
        userId="test_user_123",
        datasetId=Link[UserData](PydanticObjectId()),
        analysisType="regression",
        config={"target_column": "price", "features": ["size", "location"]},
        result={"r2_score": 0.85, "coefficients": {"size": 0.5, "location": 0.3}},
    )
    assert regression_result.analysisType == "regression"

    # Test with clustering analysis type
    clustering_result = AnalyticsResult(
        userId="test_user_123",
        datasetId=Link[UserData](PydanticObjectId()),
        analysisType="clustering",
        config={"n_clusters": 3, "algorithm": "kmeans"},
        result={"n_clusters": 3, "silhouette_score": 0.7},
    )
    assert clustering_result.analysisType == "clustering"


def test_analytics_result_with_multiple_plots():
    """Test AnalyticsResult with multiple plot references."""
    plot_ids = [PydanticObjectId() for _ in range(3)]
    plot_refs = [Link[Plot](plot_id) for plot_id in plot_ids]

    analytics_result = AnalyticsResult(
        userId="test_user_123",
        datasetId=Link[UserData](PydanticObjectId()),
        analysisType="EDA",
        plotRefs=plot_refs,
    )

    assert len(analytics_result.plotRefs) == 3
    assert all(isinstance(ref, Link) for ref in analytics_result.plotRefs)
    assert all(ref.model == Plot for ref in analytics_result.plotRefs)


def test_analytics_result_validation():
    """Test AnalyticsResult validation."""
    # Test with empty user_id
    with pytest.raises(ValueError):
        AnalyticsResult(
            userId="",  # Empty user_id
            datasetId=Link[UserData](PydanticObjectId()),
            analysisType="EDA",
        )

    # Test with invalid analysis type
    with pytest.raises(ValueError):
        AnalyticsResult(
            userId="test_user_123",
            datasetId=Link[UserData](PydanticObjectId()),
            analysisType="invalid_type",  # Invalid analysis type
        )

    # Test with invalid config format
    with pytest.raises(ValueError):
        AnalyticsResult(
            userId="test_user_123",
            datasetId=Link[UserData](PydanticObjectId()),
            analysisType="EDA",
            config="invalid_config",  # Config should be a dict
        )
