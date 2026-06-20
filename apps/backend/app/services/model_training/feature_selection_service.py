"""
Feature Selection Service for Narrative Modeling App

Implements multiple feature selection algorithms with importance scoring,
redundancy detection, and human-readable explanations.
"""

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import pearsonr
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.feature_selection import (
    RFE,
    chi2,
    f_classif,
    f_regression,
    mutual_info_classif,
    mutual_info_regression,
)
from sklearn.linear_model import LassoCV, LogisticRegressionCV
from sklearn.preprocessing import StandardScaler

from app.schemas.feature_selection import FeatureScore, RedundantPair, SelectionMethod
from app.services.data_processing.statistics_engine import StatisticsEngine
from app.services.dataset_service import DatasetService
from app.services.model_training.feature_engineer import (
    FeatureEngineer,
    FeatureEngineeringConfig,
)
from app.services.redis_cache import cache_service
from app.services.s3_service import download_file_from_s3

logger = logging.getLogger(__name__)


@dataclass
class FeatureSelectionConfig:
    """Configuration for feature selection"""
    top_k: int | None = None
    threshold: float | None = None
    correlation_threshold: float = 0.7
    problem_type: str | None = None
    sample_size: int | None = None
    algorithm_params: dict[str, Any] = None

    def __post_init__(self):
        if self.algorithm_params is None:
            self.algorithm_params = {}


class FeatureSelectionService:
    """Service for automated feature selection with multiple algorithms"""

    def __init__(self):
        self.dataset_service = DatasetService()
        self.statistics_engine = StatisticsEngine()
        self.feature_engineer = None  # Will be initialized per request
        self.cache_ttl = 3600  # 1 hour cache

    def _generate_cache_key(
        self,
        dataset_id: str,
        user_id: str,
        method: SelectionMethod,
        target_column: str,
        config: FeatureSelectionConfig,
        prefix: str = "feature_selection"
    ) -> str:
        """
        Generate cache key for feature selection results.

        SECURITY: user_id MUST be included to prevent cache poisoning attacks
        where one user could access another user's cached results.
        """
        # Create a deterministic hash of the configuration
        config_dict = {
            "method": method,
            "target": target_column,
            "top_k": config.top_k,
            "threshold": config.threshold,
            "correlation_threshold": config.correlation_threshold,
            "problem_type": config.problem_type,
            "sample_size": config.sample_size,
            "algorithm_params": config.algorithm_params or {}
        }

        config_str = json.dumps(config_dict, sort_keys=True)
        config_hash = hashlib.md5(config_str.encode()).hexdigest()[:12]

        # CRITICAL: Include user_id to prevent authorization bypass via cache poisoning
        return f"{prefix}:{dataset_id}:{user_id}:{method}:{config_hash}"

    async def select_features(
        self,
        dataset_id: str,
        user_id: str,
        target_column: str,
        method: SelectionMethod,
        config: FeatureSelectionConfig
    ) -> dict[str, Any]:
        """
        Main entry point for feature selection

        Args:
            dataset_id: Dataset identifier
            user_id: User identifier for authorization
            target_column: Target variable column name
            method: Selection algorithm to use
            config: Selection configuration

        Returns:
            Dictionary with selection results
        """
        # Check cache first (with user_id to prevent cache poisoning)
        cache_key = self._generate_cache_key(
            dataset_id, user_id, method, target_column, config
        )

        cached_result = await cache_service.get(cache_key)
        if cached_result:
            logger.info(f"Cache hit for feature selection: {cache_key}")
            return cached_result

        start_time = time.time()

        try:
            # Load dataset
            df, dataset = await self._load_dataset(dataset_id, user_id)

            # Prepare data
            X, y, problem_type = await self._prepare_data(
                df,
                target_column,
                config.problem_type,
                config.sample_size,
                dataset_id
            )

            # Select features using specified method
            selected_features, feature_scores = await self._select_by_method(
                X, y, method, problem_type, config
            )

            # Detect redundant features
            redundant_pairs = await self.detect_redundancy(
                X[selected_features],
                config.correlation_threshold
            )

            # Calculate correlation matrix
            correlation_matrix = self.statistics_engine._calculate_correlation_matrix(
                X[selected_features]
            )

            # Generate explanation
            explanation = self._explain_selection(
                method,
                selected_features,
                feature_scores,
                redundant_pairs,
                problem_type
            )

            execution_time = (time.time() - start_time) * 1000

            result = {
                "dataset_id": dataset_id,
                "method": method,
                "selected_features": selected_features,
                "feature_scores": feature_scores,
                "redundant_pairs": redundant_pairs,
                "correlation_matrix": correlation_matrix,
                "explanation": explanation,
                "metadata": {
                    "problem_type": problem_type,
                    "n_samples": len(X),
                    "n_features_original": len(df.columns) - 1,  # Exclude target
                    "n_features_selected": len(selected_features),
                    "target_column": target_column
                },
                "execution_time_ms": execution_time,
                "created_at": datetime.now(UTC)
            }

            # Cache the result
            await cache_service.set(cache_key, result, ttl=self.cache_ttl)
            logger.info(f"Cached feature selection result: {cache_key}")

            return result

        except Exception as e:
            logger.error(f"Error in feature selection: {e}")
            raise

    async def calculate_importance(
        self,
        dataset_id: str,
        user_id: str,
        target_column: str,
        method: SelectionMethod,
        problem_type: str | None = None,
        algorithm_params: dict[str, Any] | None = None
    ) -> list[FeatureScore]:
        """Calculate feature importance scores without selection"""
        df, _ = await self._load_dataset(dataset_id, user_id)
        X, y, detected_problem_type = await self._prepare_data(
            df, target_column, problem_type, dataset_id=dataset_id
        )

        config = FeatureSelectionConfig(
            problem_type=problem_type,
            algorithm_params=algorithm_params or {}
        )

        # Calculate scores
        scores = await self._calculate_importance_scores(
            X, y, method, detected_problem_type, config
        )

        # Normalize and rank
        normalized_scores = self._normalize_scores(scores)
        feature_scores = self._create_feature_scores(
            normalized_scores,
            selected=None  # All features
        )

        return feature_scores

    async def detect_redundancy(
        self,
        X: pd.DataFrame,
        threshold: float = 0.7
    ) -> list[RedundantPair]:
        """
        Detect highly correlated feature pairs

        Args:
            X: Feature DataFrame
            threshold: Correlation threshold for redundancy

        Returns:
            List of redundant pairs
        """
        redundant_pairs = []

        # Calculate correlation matrix
        corr_matrix = X.corr().abs()

        # Find pairs above threshold (excluding diagonal)
        for i in range(len(corr_matrix.columns)):
            for j in range(i + 1, len(corr_matrix.columns)):
                feature1 = corr_matrix.columns[i]
                feature2 = corr_matrix.columns[j]
                correlation = corr_matrix.iloc[i, j]

                if correlation > threshold:
                    # Determine which to keep (prefer higher variance - more information)
                    var1 = X[feature1].var()
                    var2 = X[feature2].var()

                    if var1 > var2:
                        recommendation = f"Consider removing '{feature2}' (lower variance)"
                    else:
                        recommendation = f"Consider removing '{feature1}' (lower variance)"

                    redundant_pairs.append(RedundantPair(
                        feature1=feature1,
                        feature2=feature2,
                        correlation=float(correlation),
                        recommendation=recommendation
                    ))

        return redundant_pairs

    async def compare_methods(
        self,
        dataset_id: str,
        user_id: str,
        target_column: str,
        methods: list[SelectionMethod],
        top_k: int = 10,
        problem_type: str | None = None
    ) -> dict[str, Any]:
        """Compare multiple selection methods"""
        df, _ = await self._load_dataset(dataset_id, user_id)
        X, y, detected_problem_type = await self._prepare_data(
            df, target_column, problem_type, dataset_id=dataset_id
        )

        results = []
        all_selected_features = []

        for method in methods:
            start_time = time.time()

            config = FeatureSelectionConfig(
                top_k=top_k,
                problem_type=detected_problem_type
            )

            selected, scores = await self._select_by_method(
                X, y, method, detected_problem_type, config
            )

            execution_time = (time.time() - start_time) * 1000

            results.append({
                "method": method,
                "selected_features": selected,
                "top_features": scores[:top_k],
                "execution_time_ms": execution_time
            })

            all_selected_features.append(set(selected))

        # Find consensus features (selected by all methods)
        consensus = set.intersection(*all_selected_features) if all_selected_features else set()

        # Calculate overlap matrix
        overlap_matrix = {}
        for i, method1 in enumerate(methods):
            overlap_matrix[method1] = {}
            for j, method2 in enumerate(methods):
                overlap = len(all_selected_features[i] & all_selected_features[j])
                overlap_matrix[method1][method2] = overlap

        # Generate recommendations
        recommendations = self._generate_comparison_recommendations(
            results, list(consensus), len(X.columns)
        )

        return {
            "dataset_id": dataset_id,
            "results": results,
            "consensus_features": list(consensus),
            "overlap_matrix": overlap_matrix,
            "recommendations": recommendations
        }

    # ========== Helper Methods ==========

    async def _load_dataset(
        self,
        dataset_id: str,
        user_id: str
    ) -> tuple[pd.DataFrame, Any]:
        """Load dataset from S3"""
        dataset = await self.dataset_service.get_by_id(dataset_id, user_id)

        # Download file from S3 (wrap sync call in thread to avoid blocking event loop)
        local_path = await asyncio.to_thread(download_file_from_s3, dataset.s3_url)

        # Load into DataFrame (wrap sync pandas operations in thread)
        if dataset.file_type == "csv":
            df = await asyncio.to_thread(pd.read_csv, local_path)
        elif dataset.file_type in ["xlsx", "xls"]:
            df = await asyncio.to_thread(pd.read_excel, local_path)
        else:
            raise ValueError(f"Unsupported file type: {dataset.file_type}")

        return df, dataset

    async def _prepare_data(
        self,
        df: pd.DataFrame,
        target_column: str,
        problem_type: str | None = None,
        sample_size: int | None = None,
        dataset_id: str = ""
    ) -> tuple[pd.DataFrame, pd.Series, str]:
        """Prepare features and target, detect problem type"""
        # Validate target column exists
        if target_column not in df.columns:
            raise ValueError(f"Target column '{target_column}' not found in dataset")

        # Separate features and target
        y = df[target_column]
        X = df.drop(columns=[target_column])

        # Sample if needed for large datasets (using deterministic seed for reproducibility)
        if sample_size and len(X) > sample_size:
            logger.info(f"Sampling {sample_size} rows from {len(X)} total rows")
            # Use deterministic RNG with seed derived from dataset hash for reproducibility
            seed = hash(f"{dataset_id}_{target_column}") % (2**32)
            rng = np.random.default_rng(seed)
            sample_indices = rng.choice(len(X), sample_size, replace=False)
            X = X.iloc[sample_indices]
            y = y.iloc[sample_indices]

        # Preprocess features using FeatureEngineer
        config = FeatureEngineeringConfig(
            handle_missing=True,
            scale_features=False,  # We'll scale in individual algorithms
            encode_categorical=True,
            create_interactions=False,
            select_features=False  # We're doing selection here
        )

        self.feature_engineer = FeatureEngineer(config)

        # Detect problem type if not provided
        if not problem_type:
            # Check if target is numeric with many unique values
            if pd.api.types.is_numeric_dtype(y):
                if y.nunique() > 10:
                    problem_type = "regression"
                else:
                    problem_type = "classification"
            else:
                problem_type = "classification"

        logger.info(f"Problem type: {problem_type}")

        # Fit transform without target for feature engineering
        result = await self.feature_engineer.fit_transform(
            X, None, problem_type
        )
        X_transformed = result.X_transformed

        return X_transformed, y, problem_type

    async def _select_by_method(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        method: SelectionMethod,
        problem_type: str,
        config: FeatureSelectionConfig
    ) -> tuple[list[str], list[FeatureScore]]:
        """Select features using specified method"""
        # Calculate importance scores
        scores = await self._calculate_importance_scores(
            X, y, method, problem_type, config
        )

        # Normalize scores
        normalized_scores = self._normalize_scores(scores)

        # Select features based on top_k or threshold
        selected_features = self._apply_selection_criteria(
            normalized_scores,
            config.top_k,
            config.threshold
        )

        # Create FeatureScore objects
        feature_scores = self._create_feature_scores(
            normalized_scores,
            selected_features
        )

        return selected_features, feature_scores

    async def _calculate_importance_scores(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        method: SelectionMethod,
        problem_type: str,
        config: FeatureSelectionConfig
    ) -> dict[str, float]:
        """Calculate importance scores using specified method"""
        if method == "correlation":
            return await self._select_correlation(X, y)
        elif method == "mutual_info":
            return await self._select_mutual_info(X, y, problem_type)
        elif method == "random_forest":
            return await self._select_random_forest(X, y, problem_type, config)
        elif method == "rfe":
            return await self._select_rfe(X, y, problem_type, config)
        elif method == "lasso":
            return await self._select_lasso(X, y, problem_type, config)
        elif method == "statistical":
            return await self._select_statistical(X, y, problem_type)
        else:
            raise ValueError(f"Unknown selection method: {method}")

    async def _select_correlation(
        self,
        X: pd.DataFrame,
        y: pd.Series
    ) -> dict[str, float]:
        """Correlation-based selection"""
        scores = {}

        # Convert y to numeric if needed
        if not pd.api.types.is_numeric_dtype(y):
            # Use label encoding for categorical target
            from sklearn.preprocessing import LabelEncoder
            le = LabelEncoder()
            y_numeric = le.fit_transform(y.astype(str))
        else:
            y_numeric = y.values

        for col in X.columns:
            # Only calculate correlation for numeric columns
            if pd.api.types.is_numeric_dtype(X[col]):
                try:
                    corr, _ = pearsonr(X[col].fillna(0), y_numeric)
                    scores[col] = abs(corr)  # Use absolute value
                except (ValueError, TypeError) as e:
                    # Handle cases where correlation cannot be computed (e.g., constant column, NaN values)
                    logger.debug(f"Could not compute correlation for column {col}: {e}")
                    scores[col] = 0.0
            else:
                scores[col] = 0.0

        return scores

    async def _select_mutual_info(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        problem_type: str
    ) -> dict[str, float]:
        """Mutual information-based selection"""
        # Fill NaN values for mutual info calculation
        X_filled = X.fillna(0)

        if problem_type == "classification":
            mi_scores = mutual_info_classif(X_filled, y, random_state=42)
        else:
            mi_scores = mutual_info_regression(X_filled, y, random_state=42)

        return dict(zip(X.columns, mi_scores))

    async def _select_random_forest(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        problem_type: str,
        config: FeatureSelectionConfig
    ) -> dict[str, float]:
        """Random Forest feature importance"""
        params = config.algorithm_params or {}
        n_estimators = params.get("n_estimators", 100)
        max_depth = params.get("max_depth", None)

        # Fill NaN values
        X_filled = X.fillna(0)

        if problem_type == "classification":
            model = RandomForestClassifier(
                n_estimators=n_estimators,
                max_depth=max_depth,
                random_state=42,
                n_jobs=-1
            )
        else:
            model = RandomForestRegressor(
                n_estimators=n_estimators,
                max_depth=max_depth,
                random_state=42,
                n_jobs=-1
            )

        model.fit(X_filled, y)

        return dict(zip(X.columns, model.feature_importances_))

    async def _select_rfe(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        problem_type: str,
        config: FeatureSelectionConfig
    ) -> dict[str, float]:
        """Recursive Feature Elimination"""
        # Determine n_features_to_select
        n_features = config.top_k or max(1, len(X.columns) // 2)

        # Fill NaN values and scale
        X_filled = X.fillna(0)
        scaler = StandardScaler()
        X_scaled = pd.DataFrame(
            scaler.fit_transform(X_filled),
            columns=X.columns,
            index=X.index
        )

        if problem_type == "classification":
            from sklearn.linear_model import LogisticRegression
            estimator = LogisticRegression(random_state=42, max_iter=1000)
        else:
            from sklearn.linear_model import Ridge
            estimator = Ridge(random_state=42)

        rfe = RFE(estimator=estimator, n_features_to_select=n_features)
        rfe.fit(X_scaled, y)

        # Convert rankings to scores (lower rank = higher score)
        rankings = rfe.ranking_
        max_rank = max(rankings)
        scores = {
            col: float(max_rank - rank + 1) / max_rank
            for col, rank in zip(X.columns, rankings)
        }

        return scores

    async def _select_lasso(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        problem_type: str,
        config: FeatureSelectionConfig
    ) -> dict[str, float]:
        """LASSO regularization"""
        # Fill NaN values and scale
        X_filled = X.fillna(0)
        scaler = StandardScaler()
        X_scaled = pd.DataFrame(
            scaler.fit_transform(X_filled),
            columns=X.columns,
            index=X.index
        )

        if problem_type == "classification":
            model = LogisticRegressionCV(
                cv=5,
                penalty='l1',
                solver='saga',
                random_state=42,
                max_iter=1000,
                n_jobs=-1
            )
        else:
            model = LassoCV(cv=5, random_state=42, n_jobs=-1)

        model.fit(X_scaled, y)

        # Get absolute coefficient values
        if hasattr(model, 'coef_'):
            if problem_type == "classification" and len(model.coef_.shape) > 1:
                # Multi-class: average across classes
                coeffs = np.abs(model.coef_).mean(axis=0)
            else:
                coeffs = np.abs(model.coef_)
        else:
            coeffs = np.zeros(len(X.columns))

        return dict(zip(X.columns, coeffs))

    async def _select_statistical(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        problem_type: str
    ) -> dict[str, float]:
        """Statistical tests (chi2 or f-test)"""
        # Fill NaN values
        X_filled = X.fillna(0)

        # Ensure all values are non-negative for chi2
        if problem_type == "classification":
            # Make values non-negative
            X_positive = X_filled - X_filled.min() + 1e-10
            try:
                scores, _ = chi2(X_positive, y)
            except ValueError as e:
                # Fallback to f_classif if chi2 fails (e.g., negative values)
                logger.debug(f"Chi-squared test failed, falling back to f_classif: {e}")
                scores, _ = f_classif(X_filled, y)
        else:
            scores, _ = f_regression(X_filled, y)

        # Handle NaN and inf values
        scores = np.nan_to_num(scores, nan=0.0, posinf=0.0, neginf=0.0)

        return dict(zip(X.columns, scores))

    def _normalize_scores(self, scores: dict[str, float]) -> dict[str, float]:
        """Normalize scores to 0-1 range"""
        if not scores:
            return {}

        values = np.array(list(scores.values()))

        # Handle NaN, Inf, and -Inf values that may come from correlation calculations
        values = np.nan_to_num(values, nan=0.0, posinf=1.0, neginf=0.0)

        # Handle edge case where all scores are the same
        if values.max() == values.min():
            return {k: 1.0 for k in scores.keys()}

        # Min-max normalization
        normalized = (values - values.min()) / (values.max() - values.min())

        return dict(zip(scores.keys(), normalized))

    def _apply_selection_criteria(
        self,
        scores: dict[str, float],
        top_k: int | None,
        threshold: float | None
    ) -> list[str]:
        """Apply selection criteria to choose features"""
        # Sort features by score
        sorted_features = sorted(
            scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # Apply top_k if specified
        if top_k:
            selected = [f for f, s in sorted_features[:top_k]]
        # Apply threshold if specified
        elif threshold:
            selected = [f for f, s in sorted_features if s >= threshold]
        # Default: select top 50% of features
        else:
            n_select = max(1, len(sorted_features) // 2)
            selected = [f for f, s in sorted_features[:n_select]]

        return selected

    def _create_feature_scores(
        self,
        scores: dict[str, float],
        selected_features: list[str] | None
    ) -> list[FeatureScore]:
        """Create FeatureScore objects from scores dictionary"""
        # Sort by score descending
        sorted_items = sorted(
            scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        feature_scores = []
        for rank, (feature_name, score) in enumerate(sorted_items, start=1):
            feature_scores.append(FeatureScore(
                feature_name=feature_name,
                score=float(score),
                rank=rank,
                selected=(
                    selected_features is None or
                    feature_name in selected_features
                )
            ))

        return feature_scores

    def _explain_selection(
        self,
        method: SelectionMethod,
        selected_features: list[str],
        feature_scores: list[FeatureScore],
        redundant_pairs: list[RedundantPair],
        problem_type: str
    ) -> str:
        """Generate human-readable explanation"""
        method_descriptions = {
            "correlation": "Pearson correlation with target variable",
            "mutual_info": "mutual information (captures non-linear relationships)",
            "random_forest": "Random Forest feature importance (tree-based)",
            "rfe": "Recursive Feature Elimination (optimal subset)",
            "lasso": "LASSO regularization (L1 penalty)",
            "statistical": "statistical tests (chi-squared or F-test)"
        }

        explanation_parts = []

        # Method description
        method_desc = method_descriptions.get(method, method)
        explanation_parts.append(
            f"Selected {len(selected_features)} features using {method_desc} "
            f"for {problem_type} problem."
        )

        # Top features
        top_features = [fs for fs in feature_scores if fs.selected][:5]
        if top_features:
            top_names = ", ".join([f"{fs.feature_name} ({fs.score:.3f})"
                                  for fs in top_features])
            explanation_parts.append(f"Top features: {top_names}.")

        # Redundancy warning
        if redundant_pairs:
            explanation_parts.append(
                f"Warning: Found {len(redundant_pairs)} pairs of highly correlated "
                f"features that may cause multicollinearity."
            )

        return " ".join(explanation_parts)

    def _generate_comparison_recommendations(
        self,
        results: list[dict],
        consensus_features: list[str],
        total_features: int
    ) -> str:
        """Generate recommendations from method comparison"""
        recommendations = []

        if consensus_features:
            recommendations.append(
                f"Strong recommendation: Use the {len(consensus_features)} consensus "
                f"features selected by all methods: {', '.join(consensus_features[:5])}"
                f"{'...' if len(consensus_features) > 5 else ''}."
            )
        else:
            recommendations.append(
                "No consensus features found across all methods. "
                "Consider using ensemble voting or domain expertise to select features."
            )

        # Find fastest method
        fastest = min(results, key=lambda r: r["execution_time_ms"])
        recommendations.append(
            f"For large datasets, consider '{fastest['method']}' "
            f"({fastest['execution_time_ms']:.0f}ms execution time)."
        )

        return " ".join(recommendations)
