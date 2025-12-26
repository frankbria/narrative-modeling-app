"""
Feature Engineering Service for AI-powered feature suggestions.

Combines rule-based heuristics with GPT-4 intelligence to generate
comprehensive feature suggestions for machine learning tasks.
"""

import os
import json
import uuid
import logging
import hashlib
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import pandas as pd
import numpy as np
from dataclasses import dataclass

from sklearn.feature_selection import mutual_info_classif, mutual_info_regression
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from openai import OpenAI, OpenAIError

from app.schemas.feature_engineering import (
    FeatureSuggestion,
    FeatureType,
    ComputationCost,
    FeatureSuggestionResponse,
    FeatureFeedbackRecord
)
from app.services.domain_detector import domain_detector, Domain
from app.services.model_training.problem_detector import ProblemDetector, ProblemType
from app.services.redis_cache import cache_service
from app.utils.circuit_breaker import with_circuit_breaker

logger = logging.getLogger(__name__)

# OpenAI client initialization
_openai_client: Optional[OpenAI] = None


def get_openai_client() -> Optional[OpenAI]:
    """Get or initialize OpenAI client"""
    global _openai_client
    if _openai_client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            _openai_client = OpenAI(api_key=api_key)
    return _openai_client


# Feature suggestion model
FEATURE_SUGGESTION_MODEL = os.getenv("OPENAI_FEATURE_SUGGESTION_MODEL", "gpt-4")

# Configuration
FEATURE_SUGGESTION_CACHE_TTL = int(os.getenv("FEATURE_SUGGESTION_CACHE_TTL", "3600"))
FEATURE_IMPORTANCE_SAMPLE_SIZE = int(os.getenv("FEATURE_IMPORTANCE_SAMPLE_SIZE", "1000"))


@dataclass
class DatasetAnalysis:
    """Analysis results for a dataset"""
    df: pd.DataFrame
    numeric_columns: List[str]
    categorical_columns: List[str]
    datetime_columns: List[str]
    text_columns: List[str]
    target_column: Optional[str]
    problem_type: Optional[ProblemType]
    domain: Domain
    statistics: Dict[str, Any]
    correlations: Optional[pd.DataFrame]


class FeatureEngineeringService:
    """
    Service for generating AI-powered feature suggestions.

    Combines rule-based heuristics with GPT-4 intelligence to provide
    comprehensive feature engineering recommendations.
    """

    def __init__(self):
        self.problem_detector = ProblemDetector()
        self._suggestion_counter = 0

    async def suggest_features(
        self,
        df: pd.DataFrame,
        dataset_id: str,
        target_column: Optional[str] = None,
        problem_type: Optional[str] = None,
        max_suggestions: int = 20,
        include_ai: bool = True,
        feature_types: Optional[List[FeatureType]] = None
    ) -> FeatureSuggestionResponse:
        """
        Generate feature suggestions for a dataset.

        Args:
            df: Input dataframe
            dataset_id: Dataset identifier
            target_column: Target column (auto-detected if not provided)
            problem_type: ML problem type (auto-detected if not provided)
            max_suggestions: Maximum suggestions to return
            include_ai: Whether to include AI-generated suggestions
            feature_types: Filter by feature types

        Returns:
            FeatureSuggestionResponse with suggestions
        """
        start_time = datetime.utcnow()

        # Check cache first
        cache_key = self._get_cache_key(dataset_id, target_column, problem_type)
        cached = await self._get_cached_suggestions(cache_key)
        if cached:
            logger.info(f"Returning cached suggestions for dataset {dataset_id}")
            return cached

        # Analyze dataset
        analysis = await self._analyze_dataset(df, target_column, problem_type)

        # Generate rule-based suggestions
        rule_based = await self._generate_rule_based_suggestions(analysis)
        logger.info(f"Generated {len(rule_based)} rule-based suggestions")

        # Generate AI suggestions if enabled
        ai_suggestions: List[FeatureSuggestion] = []
        if include_ai:
            try:
                ai_suggestions = await self._generate_ai_suggestions(
                    analysis,
                    existing_suggestions=rule_based
                )
                logger.info(f"Generated {len(ai_suggestions)} AI suggestions")
            except Exception as e:
                logger.warning(f"AI suggestion generation failed: {e}")

        # Combine and deduplicate
        all_suggestions = rule_based + ai_suggestions
        all_suggestions = self._deduplicate_suggestions(all_suggestions)

        # Estimate importance scores
        all_suggestions = await self._estimate_importance_batch(
            all_suggestions, analysis
        )

        # Sort by importance
        all_suggestions.sort(key=lambda s: s.expected_importance, reverse=True)

        # Filter by feature types if specified
        if feature_types:
            all_suggestions = [
                s for s in all_suggestions
                if s.feature_type in feature_types
            ]

        # Limit to max suggestions
        all_suggestions = all_suggestions[:max_suggestions]

        # Build response
        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        response = FeatureSuggestionResponse(
            dataset_id=dataset_id,
            suggestions=all_suggestions,
            detected_problem_type=analysis.problem_type.value if analysis.problem_type else None,
            detected_target_column=analysis.target_column,
            detected_domain=analysis.domain.value,
            total_suggestions=len(all_suggestions),
            rule_based_count=len([s for s in all_suggestions if s.source == "rule_based"]),
            ai_count=len([s for s in all_suggestions if s.source == "ai"]),
            metadata={
                "processing_time_ms": processing_time,
                "numeric_columns": len(analysis.numeric_columns),
                "categorical_columns": len(analysis.categorical_columns),
                "datetime_columns": len(analysis.datetime_columns)
            },
            generated_at=datetime.utcnow()
        )

        # Cache response
        await self._cache_suggestions(cache_key, response)

        return response

    async def _analyze_dataset(
        self,
        df: pd.DataFrame,
        target_column: Optional[str],
        problem_type: Optional[str]
    ) -> DatasetAnalysis:
        """Analyze dataset to inform suggestion generation"""

        # Identify column types
        numeric_columns = df.select_dtypes(include=[np.number]).columns.tolist()
        categorical_columns = df.select_dtypes(include=['object', 'category']).columns.tolist()
        datetime_columns = df.select_dtypes(include=['datetime64', 'datetime64[ns]', 'datetime']).columns.tolist()

        # Detect datetime columns from object columns
        for col in categorical_columns.copy():
            if self._is_datetime_column(df[col]):
                datetime_columns.append(col)
                categorical_columns.remove(col)

        # Detect text columns (long strings)
        text_columns = []
        for col in categorical_columns.copy():
            avg_len = df[col].dropna().astype(str).str.len().mean()
            if avg_len > 50:  # Likely text if average length > 50
                text_columns.append(col)
                categorical_columns.remove(col)

        # Detect problem type
        detected_problem_type = None
        if problem_type:
            try:
                detected_problem_type = ProblemType(problem_type)
            except ValueError:
                pass

        if detected_problem_type is None and target_column:
            result = await self.problem_detector.detect_problem_type(
                df, target_column=target_column
            )
            detected_problem_type = result.problem_type
        elif detected_problem_type is None:
            result = await self.problem_detector.detect_problem_type(df)
            detected_problem_type = result.problem_type
            if result.target_column:
                target_column = result.target_column

        # Detect domain
        domain_result = domain_detector.detect_domain(df)

        # Calculate statistics
        statistics = self._calculate_statistics(df, numeric_columns, categorical_columns)

        # Calculate correlations for numeric columns
        correlations = None
        if len(numeric_columns) > 1:
            try:
                correlations = df[numeric_columns].corr()
            except Exception:
                pass

        return DatasetAnalysis(
            df=df,
            numeric_columns=numeric_columns,
            categorical_columns=categorical_columns,
            datetime_columns=datetime_columns,
            text_columns=text_columns,
            target_column=target_column,
            problem_type=detected_problem_type,
            domain=domain_result.domain,
            statistics=statistics,
            correlations=correlations
        )

    def _is_datetime_column(self, series: pd.Series) -> bool:
        """Check if a column contains datetime values"""
        sample = series.dropna().head(100)
        if len(sample) == 0:
            return False

        try:
            pd.to_datetime(sample, errors='raise')
            return True
        except (ValueError, TypeError):
            return False

    def _calculate_statistics(
        self,
        df: pd.DataFrame,
        numeric_columns: List[str],
        categorical_columns: List[str]
    ) -> Dict[str, Any]:
        """Calculate basic statistics for the dataset"""
        stats: Dict[str, Any] = {
            "row_count": len(df),
            "column_count": len(df.columns),
            "numeric_stats": {},
            "categorical_stats": {}
        }

        for col in numeric_columns[:20]:  # Limit to first 20
            try:
                stats["numeric_stats"][col] = {
                    "mean": float(df[col].mean()),
                    "std": float(df[col].std()),
                    "min": float(df[col].min()),
                    "max": float(df[col].max()),
                    "missing": int(df[col].isna().sum()),
                    "unique": int(df[col].nunique())
                }
            except Exception:
                pass

        for col in categorical_columns[:10]:  # Limit to first 10
            try:
                stats["categorical_stats"][col] = {
                    "unique": int(df[col].nunique()),
                    "missing": int(df[col].isna().sum()),
                    "top_values": df[col].value_counts().head(5).to_dict()
                }
            except Exception:
                pass

        return stats

    async def _generate_rule_based_suggestions(
        self,
        analysis: DatasetAnalysis
    ) -> List[FeatureSuggestion]:
        """Generate rule-based feature suggestions"""
        suggestions: List[FeatureSuggestion] = []

        # Polynomial features for numeric columns
        suggestions.extend(self._suggest_polynomial_features(analysis))

        # Interaction features
        suggestions.extend(self._suggest_interaction_features(analysis))

        # Aggregation features
        suggestions.extend(self._suggest_aggregation_features(analysis))

        # Time-based features
        suggestions.extend(self._suggest_time_features(analysis))

        # Text features
        suggestions.extend(self._suggest_text_features(analysis))

        # Binning features
        suggestions.extend(self._suggest_binning_features(analysis))

        # Encoding suggestions
        suggestions.extend(self._suggest_encoding_features(analysis))

        # Scaling suggestions
        suggestions.extend(self._suggest_scaling_features(analysis))

        # Domain-specific features
        suggestions.extend(self._suggest_domain_features(analysis))

        return suggestions

    def _suggest_polynomial_features(self, analysis: DatasetAnalysis) -> List[FeatureSuggestion]:
        """Suggest polynomial transformations"""
        suggestions = []
        target = analysis.target_column

        for col in analysis.numeric_columns[:10]:  # Limit
            if col == target:
                continue

            # Skip if column has negative values (for sqrt/log)
            col_min = analysis.df[col].min()
            has_negatives = col_min < 0 if pd.notna(col_min) else False

            # Square
            suggestions.append(FeatureSuggestion(
                id=self._generate_id("poly"),
                name=f"{col}_squared",
                description=f"Square of {col} to capture non-linear relationships",
                feature_type=FeatureType.POLYNOMIAL,
                formula=f"{col} ** 2",
                expected_importance=0.5,
                explanation="Polynomial features can capture diminishing returns or accelerating effects.",
                computation_cost=ComputationCost.LOW,
                input_columns=[col],
                parameters={"power": 2},
                source="rule_based"
            ))

            # Square root (only if non-negative)
            if not has_negatives:
                suggestions.append(FeatureSuggestion(
                    id=self._generate_id("poly"),
                    name=f"{col}_sqrt",
                    description=f"Square root of {col} to reduce right skewness",
                    feature_type=FeatureType.POLYNOMIAL,
                    formula=f"sqrt({col})",
                    expected_importance=0.4,
                    explanation="Square root transformation can normalize right-skewed distributions.",
                    computation_cost=ComputationCost.LOW,
                    input_columns=[col],
                    parameters={"function": "sqrt"},
                    source="rule_based"
                ))

            # Log transform (only if positive)
            if not has_negatives and col_min > 0:
                suggestions.append(FeatureSuggestion(
                    id=self._generate_id("poly"),
                    name=f"{col}_log",
                    description=f"Log transform of {col} to reduce skewness and handle multiplicative relationships",
                    feature_type=FeatureType.POLYNOMIAL,
                    formula=f"log({col})",
                    expected_importance=0.45,
                    explanation="Log transformation is effective for variables with exponential growth patterns.",
                    computation_cost=ComputationCost.LOW,
                    input_columns=[col],
                    parameters={"function": "log"},
                    source="rule_based"
                ))

        return suggestions

    def _suggest_interaction_features(self, analysis: DatasetAnalysis) -> List[FeatureSuggestion]:
        """Suggest interaction features between numeric columns"""
        suggestions = []
        target = analysis.target_column
        numeric_cols = [c for c in analysis.numeric_columns if c != target]

        # Limit to top columns based on variance
        if len(numeric_cols) > 8:
            variances = analysis.df[numeric_cols].var().sort_values(ascending=False)
            numeric_cols = variances.head(8).index.tolist()

        for i, col1 in enumerate(numeric_cols):
            for col2 in numeric_cols[i+1:]:
                # Multiplication
                suggestions.append(FeatureSuggestion(
                    id=self._generate_id("int"),
                    name=f"{col1}_x_{col2}",
                    description=f"Interaction between {col1} and {col2}",
                    feature_type=FeatureType.INTERACTION,
                    formula=f"{col1} * {col2}",
                    expected_importance=0.4,
                    explanation="Multiplication captures combined effects when both features matter together.",
                    computation_cost=ComputationCost.LOW,
                    input_columns=[col1, col2],
                    parameters={"operation": "multiply"},
                    source="rule_based"
                ))

                # Ratio (if col2 has no zeros)
                if (analysis.df[col2] != 0).all():
                    suggestions.append(FeatureSuggestion(
                        id=self._generate_id("int"),
                        name=f"{col1}_per_{col2}",
                        description=f"Ratio of {col1} to {col2}",
                        feature_type=FeatureType.INTERACTION,
                        formula=f"{col1} / {col2}",
                        expected_importance=0.45,
                        explanation="Ratios can reveal proportional relationships between features.",
                        computation_cost=ComputationCost.LOW,
                        input_columns=[col1, col2],
                        parameters={"operation": "divide"},
                        source="rule_based"
                    ))

        return suggestions[:20]  # Limit interaction features

    def _suggest_aggregation_features(self, analysis: DatasetAnalysis) -> List[FeatureSuggestion]:
        """Suggest aggregation features based on categorical groupings"""
        suggestions = []
        target = analysis.target_column

        if not analysis.categorical_columns:
            return suggestions

        numeric_cols = [c for c in analysis.numeric_columns if c != target][:5]

        for cat_col in analysis.categorical_columns[:3]:
            # Skip if too many unique values
            if analysis.df[cat_col].nunique() > 100:
                continue

            for num_col in numeric_cols:
                # Mean by category
                suggestions.append(FeatureSuggestion(
                    id=self._generate_id("agg"),
                    name=f"{num_col}_mean_by_{cat_col}",
                    description=f"Mean of {num_col} grouped by {cat_col}",
                    feature_type=FeatureType.AGGREGATION,
                    formula=f"mean({num_col}) GROUP BY {cat_col}",
                    expected_importance=0.55,
                    explanation="Category-level aggregations capture group-specific patterns.",
                    computation_cost=ComputationCost.MEDIUM,
                    input_columns=[num_col, cat_col],
                    parameters={"aggregation": "mean", "group_by": cat_col},
                    source="rule_based"
                ))

                # Count by category
                suggestions.append(FeatureSuggestion(
                    id=self._generate_id("agg"),
                    name=f"count_by_{cat_col}",
                    description=f"Count of records by {cat_col}",
                    feature_type=FeatureType.AGGREGATION,
                    formula=f"count(*) GROUP BY {cat_col}",
                    expected_importance=0.5,
                    explanation="Category frequency can indicate popularity or prevalence effects.",
                    computation_cost=ComputationCost.LOW,
                    input_columns=[cat_col],
                    parameters={"aggregation": "count", "group_by": cat_col},
                    source="rule_based"
                ))

        return suggestions[:15]

    def _suggest_time_features(self, analysis: DatasetAnalysis) -> List[FeatureSuggestion]:
        """Suggest time-based features from datetime columns"""
        suggestions = []

        for col in analysis.datetime_columns[:3]:
            # Day of week
            suggestions.append(FeatureSuggestion(
                id=self._generate_id("time"),
                name=f"{col}_day_of_week",
                description=f"Day of week extracted from {col} (0=Monday, 6=Sunday)",
                feature_type=FeatureType.TIME_BASED,
                formula=f"dayofweek({col})",
                expected_importance=0.5,
                explanation="Day of week captures weekly patterns in time-series data.",
                computation_cost=ComputationCost.LOW,
                input_columns=[col],
                parameters={"extract": "dayofweek"},
                source="rule_based"
            ))

            # Month
            suggestions.append(FeatureSuggestion(
                id=self._generate_id("time"),
                name=f"{col}_month",
                description=f"Month extracted from {col}",
                feature_type=FeatureType.TIME_BASED,
                formula=f"month({col})",
                expected_importance=0.45,
                explanation="Month captures seasonal patterns.",
                computation_cost=ComputationCost.LOW,
                input_columns=[col],
                parameters={"extract": "month"},
                source="rule_based"
            ))

            # Is weekend
            suggestions.append(FeatureSuggestion(
                id=self._generate_id("time"),
                name=f"{col}_is_weekend",
                description=f"Whether {col} falls on a weekend",
                feature_type=FeatureType.TIME_BASED,
                formula=f"dayofweek({col}) in [5, 6]",
                expected_importance=0.4,
                explanation="Weekend indicator can capture different behavior patterns.",
                computation_cost=ComputationCost.LOW,
                input_columns=[col],
                parameters={"extract": "is_weekend"},
                source="rule_based"
            ))

            # Hour (if datetime has time component)
            suggestions.append(FeatureSuggestion(
                id=self._generate_id("time"),
                name=f"{col}_hour",
                description=f"Hour of day extracted from {col}",
                feature_type=FeatureType.TIME_BASED,
                formula=f"hour({col})",
                expected_importance=0.45,
                explanation="Hour captures daily patterns in behavior.",
                computation_cost=ComputationCost.LOW,
                input_columns=[col],
                parameters={"extract": "hour"},
                source="rule_based"
            ))

            # Quarter
            suggestions.append(FeatureSuggestion(
                id=self._generate_id("time"),
                name=f"{col}_quarter",
                description=f"Quarter of year from {col}",
                feature_type=FeatureType.TIME_BASED,
                formula=f"quarter({col})",
                expected_importance=0.4,
                explanation="Quarter captures quarterly business patterns.",
                computation_cost=ComputationCost.LOW,
                input_columns=[col],
                parameters={"extract": "quarter"},
                source="rule_based"
            ))

        return suggestions

    def _suggest_text_features(self, analysis: DatasetAnalysis) -> List[FeatureSuggestion]:
        """Suggest text-based features"""
        suggestions = []

        for col in analysis.text_columns[:3]:
            # Character count
            suggestions.append(FeatureSuggestion(
                id=self._generate_id("text"),
                name=f"{col}_char_count",
                description=f"Character count in {col}",
                feature_type=FeatureType.TEXT,
                formula=f"len({col})",
                expected_importance=0.35,
                explanation="Text length can indicate completeness or engagement.",
                computation_cost=ComputationCost.LOW,
                input_columns=[col],
                parameters={"operation": "char_count"},
                source="rule_based"
            ))

            # Word count
            suggestions.append(FeatureSuggestion(
                id=self._generate_id("text"),
                name=f"{col}_word_count",
                description=f"Word count in {col}",
                feature_type=FeatureType.TEXT,
                formula=f"word_count({col})",
                expected_importance=0.35,
                explanation="Word count can indicate complexity or detail level.",
                computation_cost=ComputationCost.LOW,
                input_columns=[col],
                parameters={"operation": "word_count"},
                source="rule_based"
            ))

            # Has special characters
            suggestions.append(FeatureSuggestion(
                id=self._generate_id("text"),
                name=f"{col}_has_special",
                description=f"Whether {col} contains special characters",
                feature_type=FeatureType.TEXT,
                formula=f"contains_pattern({col}, '[!@#$%^&*]')",
                expected_importance=0.25,
                explanation="Special characters may indicate formatting or emphasis.",
                computation_cost=ComputationCost.LOW,
                input_columns=[col],
                parameters={"operation": "has_special"},
                source="rule_based"
            ))

        return suggestions

    def _suggest_binning_features(self, analysis: DatasetAnalysis) -> List[FeatureSuggestion]:
        """Suggest binning features for numeric columns"""
        suggestions = []
        target = analysis.target_column

        for col in analysis.numeric_columns[:5]:
            if col == target:
                continue

            # Skip if already few unique values
            if analysis.df[col].nunique() < 10:
                continue

            # Equal-width binning
            suggestions.append(FeatureSuggestion(
                id=self._generate_id("bin"),
                name=f"{col}_binned_5",
                description=f"{col} binned into 5 equal-width groups",
                feature_type=FeatureType.BINNING,
                formula=f"cut({col}, bins=5)",
                expected_importance=0.35,
                explanation="Binning can capture non-linear relationships and reduce noise.",
                computation_cost=ComputationCost.LOW,
                input_columns=[col],
                parameters={"method": "equal_width", "bins": 5},
                source="rule_based"
            ))

            # Quantile binning
            suggestions.append(FeatureSuggestion(
                id=self._generate_id("bin"),
                name=f"{col}_quantile_4",
                description=f"{col} binned into quartiles",
                feature_type=FeatureType.BINNING,
                formula=f"qcut({col}, q=4)",
                expected_importance=0.4,
                explanation="Quantile binning ensures equal samples per bin.",
                computation_cost=ComputationCost.LOW,
                input_columns=[col],
                parameters={"method": "quantile", "bins": 4},
                source="rule_based"
            ))

        return suggestions

    def _suggest_encoding_features(self, analysis: DatasetAnalysis) -> List[FeatureSuggestion]:
        """Suggest encoding options for categorical columns"""
        suggestions = []

        for col in analysis.categorical_columns[:5]:
            unique_count = analysis.df[col].nunique()

            if unique_count <= 10:
                # One-hot encoding for low cardinality
                suggestions.append(FeatureSuggestion(
                    id=self._generate_id("enc"),
                    name=f"{col}_onehot",
                    description=f"One-hot encoding of {col} ({unique_count} categories)",
                    feature_type=FeatureType.ENCODING,
                    formula=f"one_hot({col})",
                    expected_importance=0.5,
                    explanation="One-hot encoding creates binary features for each category.",
                    computation_cost=ComputationCost.LOW,
                    input_columns=[col],
                    parameters={"method": "one_hot"},
                    source="rule_based"
                ))
            else:
                # Label encoding for high cardinality
                suggestions.append(FeatureSuggestion(
                    id=self._generate_id("enc"),
                    name=f"{col}_label",
                    description=f"Label encoding of {col} ({unique_count} categories)",
                    feature_type=FeatureType.ENCODING,
                    formula=f"label_encode({col})",
                    expected_importance=0.4,
                    explanation="Label encoding converts categories to integers (use with tree models).",
                    computation_cost=ComputationCost.LOW,
                    input_columns=[col],
                    parameters={"method": "label"},
                    source="rule_based"
                ))

        return suggestions

    def _suggest_scaling_features(self, analysis: DatasetAnalysis) -> List[FeatureSuggestion]:
        """Suggest scaling options for numeric columns"""
        suggestions = []
        target = analysis.target_column

        # Suggest one scaling type for all numeric columns together
        numeric_cols = [c for c in analysis.numeric_columns if c != target]
        if numeric_cols:
            suggestions.append(FeatureSuggestion(
                id=self._generate_id("scale"),
                name="standard_scaling",
                description="Standard scaling (z-score normalization) for numeric features",
                feature_type=FeatureType.SCALING,
                formula="(x - mean) / std",
                expected_importance=0.3,
                explanation="Standard scaling centers data at 0 with unit variance, ideal for many ML algorithms.",
                computation_cost=ComputationCost.LOW,
                input_columns=numeric_cols[:10],
                parameters={"method": "standard"},
                source="rule_based"
            ))

            suggestions.append(FeatureSuggestion(
                id=self._generate_id("scale"),
                name="minmax_scaling",
                description="Min-max scaling to [0, 1] range",
                feature_type=FeatureType.SCALING,
                formula="(x - min) / (max - min)",
                expected_importance=0.3,
                explanation="Min-max scaling bounds values to a fixed range, useful for neural networks.",
                computation_cost=ComputationCost.LOW,
                input_columns=numeric_cols[:10],
                parameters={"method": "minmax"},
                source="rule_based"
            ))

        return suggestions

    def _suggest_domain_features(self, analysis: DatasetAnalysis) -> List[FeatureSuggestion]:
        """Suggest domain-specific features based on detected domain"""
        suggestions = []
        domain_result = domain_detector.detect_domain(analysis.df)

        for template in domain_result.suggested_features:
            if template.get("can_apply"):
                matching = template.get("matching_columns", {})
                suggestions.append(FeatureSuggestion(
                    id=self._generate_id("domain"),
                    name=template["name"],
                    description=template["description"],
                    feature_type=FeatureType.DOMAIN_SPECIFIC,
                    formula=template.get("formula", ""),
                    expected_importance=0.6,
                    explanation=f"Domain-specific feature for {analysis.domain.value} data.",
                    computation_cost=ComputationCost.MEDIUM,
                    input_columns=list(matching.values()),
                    parameters={"domain": analysis.domain.value, "template": template["name"]},
                    source="rule_based"
                ))

        return suggestions

    @with_circuit_breaker(
        "openai",
        max_attempts=2,
        failure_threshold=3,
        recovery_timeout=60.0,
        exceptions=(OpenAIError, Exception),
        fallback_value=[]
    )
    async def _generate_ai_suggestions(
        self,
        analysis: DatasetAnalysis,
        existing_suggestions: List[FeatureSuggestion]
    ) -> List[FeatureSuggestion]:
        """Generate AI-powered feature suggestions using GPT-4"""
        client = get_openai_client()
        if not client:
            logger.warning("OpenAI client not available")
            return []

        # Prepare context for AI
        context = self._prepare_ai_context(analysis, existing_suggestions)

        system_prompt = """You are an expert data scientist specializing in feature engineering.
Your task is to suggest creative, domain-specific features that could improve machine learning model performance.

Focus on:
1. Domain-specific insights that rule-based systems might miss
2. Complex interactions between features
3. Business-relevant derived metrics
4. Features that capture temporal patterns or trends
5. Cross-feature relationships

Return suggestions in JSON format as an array of objects with these fields:
- name: Feature name (snake_case)
- description: Clear description
- formula: Mathematical formula or logic
- feature_type: One of [polynomial, interaction, aggregation, time_based, text, binning, encoding, mathematical, domain_specific]
- explanation: Why this feature could be useful for the ML task
- input_columns: List of source columns needed
- computation_cost: One of [low, medium, high]

Respond with valid JSON only, no additional text."""

        user_prompt = f"""Dataset Analysis:
{json.dumps(context, indent=2)}

Existing suggestions to avoid duplicating:
{[s.name for s in existing_suggestions[:10]]}

Please suggest 5-8 creative features that:
1. Are different from the existing suggestions
2. Leverage the specific characteristics of this data
3. Could meaningfully improve model performance for {analysis.problem_type.value if analysis.problem_type else 'prediction'}

Target column: {analysis.target_column or 'not specified'}
Domain: {analysis.domain.value}"""

        try:
            response = client.chat.completions.create(
                model=FEATURE_SUGGESTION_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content
            suggestions_data = json.loads(content)

            # Handle different JSON structures
            if isinstance(suggestions_data, dict):
                suggestions_data = suggestions_data.get("suggestions", suggestions_data.get("features", []))

            suggestions = []
            for item in suggestions_data:
                try:
                    feature_type_str = item.get("feature_type", "mathematical")
                    try:
                        feature_type = FeatureType(feature_type_str)
                    except ValueError:
                        feature_type = FeatureType.MATHEMATICAL

                    cost_str = item.get("computation_cost", "medium")
                    try:
                        cost = ComputationCost(cost_str)
                    except ValueError:
                        cost = ComputationCost.MEDIUM

                    suggestions.append(FeatureSuggestion(
                        id=self._generate_id("ai"),
                        name=item.get("name", "unnamed_feature"),
                        description=item.get("description", ""),
                        feature_type=feature_type,
                        formula=item.get("formula", ""),
                        expected_importance=0.5,  # Will be updated by importance estimation
                        explanation=item.get("explanation", "AI-generated suggestion"),
                        computation_cost=cost,
                        input_columns=item.get("input_columns", []),
                        parameters=item.get("parameters", {}),
                        source="ai"
                    ))
                except Exception as e:
                    logger.warning(f"Failed to parse AI suggestion: {e}")
                    continue

            return suggestions

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse AI response: {e}")
            return []
        except Exception as e:
            logger.error(f"AI suggestion generation error: {e}")
            return []

    def _prepare_ai_context(
        self,
        analysis: DatasetAnalysis,
        existing_suggestions: List[FeatureSuggestion]
    ) -> Dict[str, Any]:
        """Prepare context dictionary for AI prompt"""
        return {
            "columns": {
                "numeric": analysis.numeric_columns,
                "categorical": analysis.categorical_columns,
                "datetime": analysis.datetime_columns,
                "text": analysis.text_columns
            },
            "target": analysis.target_column,
            "problem_type": analysis.problem_type.value if analysis.problem_type else None,
            "domain": analysis.domain.value,
            "row_count": len(analysis.df),
            "statistics_sample": {k: v for k, v in list(analysis.statistics.get("numeric_stats", {}).items())[:5]},
            "correlations_sample": analysis.correlations.iloc[:5, :5].to_dict() if analysis.correlations is not None and len(analysis.correlations) >= 5 else None
        }

    async def _estimate_importance_batch(
        self,
        suggestions: List[FeatureSuggestion],
        analysis: DatasetAnalysis
    ) -> List[FeatureSuggestion]:
        """Estimate importance scores for all suggestions"""
        if not analysis.target_column:
            return suggestions

        target = analysis.target_column
        if target not in analysis.df.columns:
            return suggestions

        y = analysis.df[target].dropna()
        if len(y) < 10:
            return suggestions

        # Sample data for performance
        sample_size = min(FEATURE_IMPORTANCE_SAMPLE_SIZE, len(analysis.df))
        df_sample = analysis.df.sample(n=sample_size, random_state=42) if len(analysis.df) > sample_size else analysis.df

        for suggestion in suggestions:
            try:
                importance = await self._estimate_single_importance(
                    suggestion, df_sample, analysis
                )
                suggestion.expected_importance = importance
            except Exception as e:
                logger.debug(f"Failed to estimate importance for {suggestion.name}: {e}")

        return suggestions

    async def _estimate_single_importance(
        self,
        suggestion: FeatureSuggestion,
        df: pd.DataFrame,
        analysis: DatasetAnalysis
    ) -> float:
        """Estimate importance for a single suggestion"""
        # For simple column-based features, use correlation or mutual information
        if len(suggestion.input_columns) == 1:
            col = suggestion.input_columns[0]
            if col in df.columns and analysis.target_column in df.columns:
                X = df[[col]].dropna()
                y = df.loc[X.index, analysis.target_column]

                if len(X) < 10:
                    return 0.5

                if analysis.problem_type and "classification" in analysis.problem_type.value:
                    try:
                        mi = mutual_info_classif(X, y, random_state=42)
                        return float(min(mi[0] * 2, 1.0))  # Scale to 0-1
                    except Exception:
                        pass
                else:
                    try:
                        corr = abs(X[col].corr(y))
                        return float(min(corr, 1.0)) if pd.notna(corr) else 0.5
                    except Exception:
                        pass

        # For complex features, use a quick RF-based estimate
        if len(suggestion.input_columns) >= 2:
            cols = [c for c in suggestion.input_columns if c in df.columns]
            if len(cols) >= 2 and analysis.target_column in df.columns:
                try:
                    X = df[cols].dropna()
                    y = df.loc[X.index, analysis.target_column]

                    if len(X) < 20:
                        return 0.5

                    if analysis.problem_type and "classification" in analysis.problem_type.value:
                        model = RandomForestClassifier(n_estimators=10, max_depth=3, random_state=42)
                    else:
                        model = RandomForestRegressor(n_estimators=10, max_depth=3, random_state=42)

                    model.fit(X, y)
                    return float(min(max(model.feature_importances_), 1.0))
                except Exception:
                    pass

        return 0.5  # Default

    def _deduplicate_suggestions(
        self,
        suggestions: List[FeatureSuggestion]
    ) -> List[FeatureSuggestion]:
        """Remove duplicate suggestions based on name similarity"""
        seen_names = set()
        unique = []

        for s in suggestions:
            name_key = s.name.lower().replace("_", "")
            if name_key not in seen_names:
                seen_names.add(name_key)
                unique.append(s)

        return unique

    def _generate_id(self, prefix: str) -> str:
        """Generate unique suggestion ID"""
        self._suggestion_counter += 1
        return f"feat_{prefix}_{self._suggestion_counter:04d}_{uuid.uuid4().hex[:6]}"

    def _get_cache_key(
        self,
        dataset_id: str,
        target_column: Optional[str],
        problem_type: Optional[str]
    ) -> str:
        """Generate cache key for suggestions"""
        key_parts = [dataset_id, target_column or "auto", problem_type or "auto"]
        return f"feature_suggestions:{hashlib.md5(':'.join(key_parts).encode()).hexdigest()}"

    async def _get_cached_suggestions(
        self,
        cache_key: str
    ) -> Optional[FeatureSuggestionResponse]:
        """Get cached suggestions if available"""
        try:
            if cache_service:
                cached = await cache_service.get(cache_key)
                if cached:
                    return FeatureSuggestionResponse(**cached)
        except Exception as e:
            logger.debug(f"Cache retrieval failed: {e}")
        return None

    async def _cache_suggestions(
        self,
        cache_key: str,
        response: FeatureSuggestionResponse
    ) -> None:
        """Cache suggestions for future requests"""
        try:
            if cache_service:
                await cache_service.set(
                    cache_key,
                    response.model_dump(),
                    ttl=FEATURE_SUGGESTION_CACHE_TTL
                )
        except Exception as e:
            logger.debug(f"Cache storage failed: {e}")

    async def record_feedback(
        self,
        feedback: FeatureFeedbackRecord
    ) -> bool:
        """Record user feedback on a suggestion"""
        # In production, this would store to MongoDB
        # For now, just log it
        logger.info(f"Feedback recorded: suggestion={feedback.suggestion_id}, accepted={feedback.accepted}")
        return True

    async def explain_feature(
        self,
        suggestion: FeatureSuggestion,
        analysis: DatasetAnalysis
    ) -> Dict[str, Any]:
        """Generate detailed explanation for a feature suggestion"""
        return {
            "suggestion_id": suggestion.id,
            "name": suggestion.name,
            "detailed_explanation": f"""
## {suggestion.name}

### Description
{suggestion.description}

### Formula
```
{suggestion.formula}
```

### Why This Feature?
{suggestion.explanation}

### Input Columns
{', '.join(suggestion.input_columns)}

### Computation Cost
{suggestion.computation_cost.value.upper()} - {'This feature is fast to compute' if suggestion.computation_cost == ComputationCost.LOW else 'This feature requires moderate computation' if suggestion.computation_cost == ComputationCost.MEDIUM else 'This feature is computationally expensive'}

### Expected Impact
Based on our analysis, this feature has an estimated importance score of {suggestion.expected_importance:.2f} out of 1.0.
            """.strip(),
            "example_calculations": [],
            "similar_features": [],
            "use_cases": [
                f"Useful for {analysis.problem_type.value if analysis.problem_type else 'prediction'} tasks",
                f"Applicable to {analysis.domain.value} domain data"
            ],
            "considerations": [
                "Check for missing values in input columns before applying",
                "Consider the computational cost for large datasets"
            ]
        }


# Singleton instance
feature_engineering_service = FeatureEngineeringService()
