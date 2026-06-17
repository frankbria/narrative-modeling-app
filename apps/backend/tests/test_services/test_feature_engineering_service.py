"""
Tests for Feature Engineering Service

Tests AI-powered feature suggestion generation, domain detection,
importance estimation, and feedback recording.
"""

from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from app.schemas.feature_engineering import (
    FeatureFeedbackRecord,
    FeatureSuggestionResponse,
    FeatureType,
)
from app.services.domain_detector import Domain, DomainDetector
from app.services.feature_engineering_service import (
    FeatureEngineeringService,
)


class TestFeatureEngineeringService:
    """Test suite for FeatureEngineeringService"""

    @pytest.fixture
    def service(self):
        """Create feature engineering service instance"""
        return FeatureEngineeringService()

    @pytest.fixture
    def numeric_data(self):
        """Create dataset with numeric columns"""
        np.random.seed(42)
        n_samples = 100
        return pd.DataFrame({
            'age': np.random.randint(18, 70, n_samples),
            'income': np.random.randint(30000, 150000, n_samples),
            'score': np.random.randn(n_samples) * 10 + 50,
            'balance': np.random.randint(0, 10000, n_samples),
            'target': np.random.choice([0, 1], n_samples),
        })

    @pytest.fixture
    def mixed_data(self):
        """Create dataset with mixed column types"""
        np.random.seed(42)
        n_samples = 100
        return pd.DataFrame({
            'age': np.random.randint(18, 70, n_samples),
            'salary': np.random.randint(30000, 150000, n_samples),
            'department': np.random.choice(['Sales', 'Engineering', 'Marketing'], n_samples),
            'status': np.random.choice(['Active', 'Inactive'], n_samples),
            'hire_date': pd.date_range('2020-01-01', periods=n_samples, freq='D'),
            'description': ['This is a sample text description.' * np.random.randint(1, 5) for _ in range(n_samples)],
            'churn': np.random.choice([0, 1], n_samples),
        })

    @pytest.fixture
    def financial_data(self):
        """Create dataset with financial domain indicators"""
        np.random.seed(42)
        n_samples = 100
        return pd.DataFrame({
            'transaction_amount': np.random.randint(10, 1000, n_samples),
            'account_balance': np.random.randint(0, 50000, n_samples),
            'price': np.random.uniform(1, 100, n_samples),
            'revenue': np.random.uniform(1000, 10000, n_samples),
            'cost': np.random.uniform(500, 5000, n_samples),
            'profit_margin': np.random.uniform(0.05, 0.3, n_samples),
            'is_fraud': np.random.choice([0, 1], n_samples, p=[0.95, 0.05]),
        })

    @pytest.mark.asyncio
    async def test_suggest_features_returns_response(self, service, numeric_data):
        """Test that suggest_features returns proper response"""
        response = await service.suggest_features(
            df=numeric_data,
            dataset_id="test_dataset_001",
            target_column="target",
            max_suggestions=10,
            include_ai=False  # Disable AI to avoid API calls in tests
        )

        assert isinstance(response, FeatureSuggestionResponse)
        assert response.dataset_id == "test_dataset_001"
        assert len(response.suggestions) > 0
        assert response.total_suggestions == len(response.suggestions)

    @pytest.mark.asyncio
    async def test_suggest_features_detects_problem_type(self, service, numeric_data):
        """Test automatic problem type detection"""
        response = await service.suggest_features(
            df=numeric_data,
            dataset_id="test_dataset_002",
            include_ai=False
        )

        # Should detect binary classification since target has 2 values
        assert response.detected_problem_type is not None
        assert 'classification' in response.detected_problem_type.lower()

    @pytest.mark.asyncio
    async def test_suggest_features_with_target_column(self, service, numeric_data):
        """Test suggestion generation with explicit target column"""
        response = await service.suggest_features(
            df=numeric_data,
            dataset_id="test_dataset_003",
            target_column="target",
            include_ai=False
        )

        assert response.detected_target_column == "target"
        # Suggestions should not include target column transformations
        for suggestion in response.suggestions:
            assert "target" not in suggestion.name.lower()

    @pytest.mark.asyncio
    async def test_polynomial_suggestions_generated(self, service, numeric_data):
        """Test that polynomial suggestions are generated for numeric columns"""
        response = await service.suggest_features(
            df=numeric_data,
            dataset_id="test_dataset_004",
            target_column="target",
            include_ai=False
        )

        polynomial_suggestions = [
            s for s in response.suggestions
            if s.feature_type == FeatureType.POLYNOMIAL
        ]

        assert len(polynomial_suggestions) > 0
        # Should have squared, sqrt, log for numeric columns
        feature_names = [s.name for s in polynomial_suggestions]
        assert any('squared' in name for name in feature_names)

    @pytest.mark.asyncio
    async def test_interaction_suggestions_generated(self, service, numeric_data):
        """Test that interaction suggestions are generated"""
        response = await service.suggest_features(
            df=numeric_data,
            dataset_id="test_dataset_005",
            target_column="target",
            include_ai=False
        )

        interaction_suggestions = [
            s for s in response.suggestions
            if s.feature_type == FeatureType.INTERACTION
        ]

        assert len(interaction_suggestions) > 0
        # Should have multiplication and ratio features
        feature_names = [s.name for s in interaction_suggestions]
        assert any('_x_' in name for name in feature_names)

    @pytest.mark.asyncio
    async def test_time_based_suggestions_for_datetime(self, service, mixed_data):
        """Test time-based suggestions for datetime columns"""
        response = await service.suggest_features(
            df=mixed_data,
            dataset_id="test_dataset_006",
            target_column="churn",
            include_ai=False,
            max_suggestions=50  # Increase to ensure time-based features are included
        )

        time_suggestions = [
            s for s in response.suggestions
            if s.feature_type == FeatureType.TIME_BASED
        ]

        assert len(time_suggestions) > 0
        feature_names = [s.name for s in time_suggestions]
        # Should extract day_of_week, month, hour, etc.
        assert any('day_of_week' in name for name in feature_names)
        assert any('month' in name for name in feature_names)

    @pytest.mark.asyncio
    async def test_aggregation_suggestions_for_categorical(self, service, mixed_data):
        """Test aggregation suggestions for categorical columns"""
        response = await service.suggest_features(
            df=mixed_data,
            dataset_id="test_dataset_007",
            target_column="churn",
            include_ai=False
        )

        aggregation_suggestions = [
            s for s in response.suggestions
            if s.feature_type == FeatureType.AGGREGATION
        ]

        assert len(aggregation_suggestions) > 0
        # Should have mean_by_category type features
        feature_names = [s.name for s in aggregation_suggestions]
        assert any('mean_by' in name or 'count_by' in name for name in feature_names)

    @pytest.mark.asyncio
    async def test_encoding_suggestions_for_categorical(self, service, mixed_data):
        """Test encoding suggestions for categorical columns"""
        response = await service.suggest_features(
            df=mixed_data,
            dataset_id="test_dataset_008",
            target_column="churn",
            include_ai=False
        )

        encoding_suggestions = [
            s for s in response.suggestions
            if s.feature_type == FeatureType.ENCODING
        ]

        assert len(encoding_suggestions) > 0
        # Should suggest one-hot or label encoding
        for suggestion in encoding_suggestions:
            assert 'onehot' in suggestion.name or 'label' in suggestion.name

    @pytest.mark.asyncio
    async def test_scaling_suggestions_generated(self, service, numeric_data):
        """Test that scaling suggestions are generated"""
        response = await service.suggest_features(
            df=numeric_data,
            dataset_id="test_dataset_009",
            target_column="target",
            include_ai=False
        )

        scaling_suggestions = [
            s for s in response.suggestions
            if s.feature_type == FeatureType.SCALING
        ]

        assert len(scaling_suggestions) > 0
        feature_names = [s.name for s in scaling_suggestions]
        assert any('scaling' in name for name in feature_names)

    @pytest.mark.asyncio
    async def test_importance_scores_populated(self, service, numeric_data):
        """Test that importance scores are populated"""
        response = await service.suggest_features(
            df=numeric_data,
            dataset_id="test_dataset_010",
            target_column="target",
            include_ai=False
        )

        for suggestion in response.suggestions:
            assert 0 <= suggestion.expected_importance <= 1

    @pytest.mark.asyncio
    async def test_suggestions_sorted_by_importance(self, service, numeric_data):
        """Test that suggestions are sorted by importance (descending)"""
        response = await service.suggest_features(
            df=numeric_data,
            dataset_id="test_dataset_011",
            target_column="target",
            include_ai=False
        )

        if len(response.suggestions) > 1:
            importances = [s.expected_importance for s in response.suggestions]
            assert importances == sorted(importances, reverse=True)

    @pytest.mark.asyncio
    async def test_max_suggestions_limit_respected(self, service, numeric_data):
        """Test that max_suggestions limit is respected"""
        response = await service.suggest_features(
            df=numeric_data,
            dataset_id="test_dataset_012",
            target_column="target",
            max_suggestions=5,
            include_ai=False
        )

        assert len(response.suggestions) <= 5

    @pytest.mark.asyncio
    async def test_feature_type_filter(self, service, numeric_data):
        """Test filtering by feature types"""
        response = await service.suggest_features(
            df=numeric_data,
            dataset_id="test_dataset_013",
            target_column="target",
            feature_types=[FeatureType.POLYNOMIAL],
            include_ai=False
        )

        for suggestion in response.suggestions:
            assert suggestion.feature_type == FeatureType.POLYNOMIAL

    @pytest.mark.asyncio
    async def test_suggestion_has_required_fields(self, service, numeric_data):
        """Test that all suggestions have required fields"""
        response = await service.suggest_features(
            df=numeric_data,
            dataset_id="test_dataset_014",
            target_column="target",
            include_ai=False
        )

        for suggestion in response.suggestions:
            assert suggestion.id is not None
            assert suggestion.name is not None
            assert suggestion.description is not None
            assert suggestion.feature_type is not None
            assert suggestion.explanation is not None
            assert suggestion.computation_cost is not None
            assert isinstance(suggestion.input_columns, list)
            assert isinstance(suggestion.parameters, dict)

    @pytest.mark.asyncio
    async def test_deduplicate_suggestions(self, service, numeric_data):
        """Test that duplicate suggestions are removed"""
        response = await service.suggest_features(
            df=numeric_data,
            dataset_id="test_dataset_015",
            target_column="target",
            include_ai=False
        )

        names = [s.name.lower().replace("_", "") for s in response.suggestions]
        assert len(names) == len(set(names))

    @pytest.mark.asyncio
    async def test_metadata_populated(self, service, numeric_data):
        """Test that response metadata is populated"""
        response = await service.suggest_features(
            df=numeric_data,
            dataset_id="test_dataset_016",
            target_column="target",
            include_ai=False
        )

        assert 'processing_time_ms' in response.metadata
        assert response.metadata['processing_time_ms'] >= 0

    @pytest.mark.asyncio
    async def test_domain_detection_financial(self, service, financial_data):
        """Test that financial domain is detected"""
        response = await service.suggest_features(
            df=financial_data,
            dataset_id="test_dataset_017",
            target_column="is_fraud",
            include_ai=False
        )

        assert response.detected_domain == 'financial'

    @pytest.mark.asyncio
    async def test_record_feedback(self, service):
        """Test feedback recording"""
        feedback = FeatureFeedbackRecord(
            feedback_id="fb_test_001",
            suggestion_id="feat_test_001",
            user_id="user_123",
            dataset_id="dataset_123",
            feature_type=FeatureType.POLYNOMIAL,
            accepted=True,
            modified_parameters=None,
            reason=None,
            created_at=datetime.utcnow()
        )

        result = await service.record_feedback(feedback)
        assert result is True


class TestDomainDetector:
    """Test suite for DomainDetector"""

    @pytest.fixture
    def detector(self):
        """Create domain detector instance"""
        return DomainDetector()

    @pytest.fixture
    def financial_df(self):
        """Create financial domain dataframe"""
        return pd.DataFrame({
            'transaction_id': range(100),
            'amount': np.random.uniform(10, 1000, 100),
            'balance': np.random.uniform(0, 50000, 100),
            'interest_rate': np.random.uniform(0.01, 0.1, 100),
            'credit_score': np.random.randint(300, 850, 100),
        })

    @pytest.fixture
    def healthcare_df(self):
        """Create healthcare domain dataframe"""
        return pd.DataFrame({
            'patient_id': range(100),
            'diagnosis_code': ['A00', 'B01', 'C02'] * 33 + ['D03'],
            'blood_pressure': np.random.randint(80, 180, 100),
            'treatment': np.random.choice(['Treatment A', 'Treatment B'], 100),
            'medication': np.random.choice(['Drug X', 'Drug Y', 'Drug Z'], 100),
        })

    @pytest.fixture
    def retail_df(self):
        """Create retail domain dataframe"""
        return pd.DataFrame({
            'order_id': range(100),
            'product_name': ['Product ' + str(i % 10) for i in range(100)],
            'quantity': np.random.randint(1, 10, 100),
            'customer_id': np.random.randint(1, 50, 100),
            'discount': np.random.uniform(0, 0.3, 100),
        })

    @pytest.fixture
    def general_df(self):
        """Create general purpose dataframe with no domain indicators"""
        return pd.DataFrame({
            'col_a': np.random.randn(100),
            'col_b': np.random.randn(100),
            'col_c': np.random.choice(['X', 'Y', 'Z'], 100),
        })

    def test_detect_financial_domain(self, detector, financial_df):
        """Test detection of financial domain"""
        result = detector.detect_domain(financial_df)

        assert result.domain == Domain.FINANCIAL
        assert result.confidence >= 0.3
        assert len(result.evidence) > 0

    def test_detect_healthcare_domain(self, detector, healthcare_df):
        """Test detection of healthcare domain"""
        result = detector.detect_domain(healthcare_df)

        assert result.domain == Domain.HEALTHCARE
        assert result.confidence >= 0.3

    def test_detect_retail_domain(self, detector, retail_df):
        """Test detection of retail domain"""
        result = detector.detect_domain(retail_df)

        assert result.domain == Domain.RETAIL
        assert result.confidence >= 0.3

    def test_detect_general_domain_fallback(self, detector, general_df):
        """Test fallback to general domain when no indicators"""
        result = detector.detect_domain(general_df)

        assert result.domain == Domain.GENERAL
        # Low confidence since no specific domain detected
        assert result.confidence <= 0.6

    def test_domain_suggested_features(self, detector, financial_df):
        """Test that domain-specific features are suggested"""
        result = detector.detect_domain(financial_df)

        # Financial domain should suggest domain-specific features
        assert isinstance(result.suggested_features, list)

    def test_domain_metadata(self, detector, financial_df):
        """Test that metadata is populated"""
        result = detector.detect_domain(financial_df)

        assert 'all_scores' in result.metadata
        assert 'column_count' in result.metadata
        assert result.metadata['column_count'] == len(financial_df.columns)

    def test_domain_description(self, detector):
        """Test domain description retrieval"""
        description = detector.get_domain_description(Domain.FINANCIAL)
        assert 'financial' in description.lower() or 'transaction' in description.lower()

        description = detector.get_domain_description(Domain.GENERAL)
        assert len(description) > 0


class TestDatasetAnalysis:
    """Test dataset analysis functionality"""

    @pytest.fixture
    def service(self):
        return FeatureEngineeringService()

    @pytest.fixture
    def complex_df(self):
        """Create complex dataframe with various column types"""
        np.random.seed(42)
        n = 100
        return pd.DataFrame({
            'numeric_int': np.random.randint(0, 100, n),
            'numeric_float': np.random.randn(n),
            'categorical': np.random.choice(['A', 'B', 'C'], n),
            'datetime': pd.date_range('2024-01-01', periods=n, freq='H'),
            'text': ['Sample text ' * np.random.randint(5, 20) for _ in range(n)],
            'target': np.random.choice([0, 1], n),
        })

    @pytest.mark.asyncio
    async def test_analyze_identifies_column_types(self, service, complex_df):
        """Test that analysis correctly identifies column types"""
        analysis = await service._analyze_dataset(complex_df, 'target', None)

        assert 'numeric_int' in analysis.numeric_columns
        assert 'numeric_float' in analysis.numeric_columns
        assert 'categorical' in analysis.categorical_columns
        assert 'datetime' in analysis.datetime_columns
        assert 'text' in analysis.text_columns

    @pytest.mark.asyncio
    async def test_analyze_calculates_statistics(self, service, complex_df):
        """Test that analysis calculates statistics"""
        analysis = await service._analyze_dataset(complex_df, 'target', None)

        assert 'row_count' in analysis.statistics
        assert analysis.statistics['row_count'] == len(complex_df)
        assert 'numeric_stats' in analysis.statistics

    @pytest.mark.asyncio
    async def test_analyze_calculates_correlations(self, service, complex_df):
        """Test that analysis calculates correlations"""
        analysis = await service._analyze_dataset(complex_df, 'target', None)

        if analysis.correlations is not None:
            assert isinstance(analysis.correlations, pd.DataFrame)
