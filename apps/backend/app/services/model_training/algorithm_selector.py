"""
Algorithm recommendation system for AutoML
"""

import logging
from dataclasses import dataclass
from typing import Any

from .problem_detector import ProblemType

logger = logging.getLogger(__name__)


@dataclass
class DataProfile:
    """Profile of dataset characteristics"""
    n_samples: int
    n_features: int
    n_numeric_features: int
    n_categorical_features: int
    class_balance_ratio: float | None  # None for regression
    missing_value_percentage: float
    high_cardinality_features: int
    dataset_size_category: str  # "small", "medium", "large"


@dataclass
class AlgorithmRecommendation:
    """Recommendation for a specific algorithm"""
    algorithm_name: str
    priority: int  # 1-10, higher is better
    expected_performance: str
    training_time_estimate: str
    interpretability_score: int  # 1-10, higher is more interpretable
    explanation: str
    pros: list[str]
    cons: list[str]


class AlgorithmSelector:
    """
    Select and recommend algorithms based on data characteristics
    """

    def __init__(self):
        # Thresholds for dataset size categories
        self.small_dataset_threshold = 5000
        self.large_dataset_threshold = 50000

        # Thresholds for feature characteristics
        self.high_imbalance_threshold = 3.0
        self.high_cardinality_threshold = 100

    async def select_algorithms(
        self,
        problem_type: ProblemType,
        data_profile: DataProfile,
        config: dict[str, Any]
    ) -> list[AlgorithmRecommendation]:
        """
        Select and rank algorithms based on problem type and data characteristics

        Args:
            problem_type: Type of ML problem
            data_profile: Dataset profile
            config: Configuration including optimize_for preference

        Returns:
            List of algorithm recommendations sorted by priority
        """
        recommendations = []

        # Get base recommendations based on problem type
        if problem_type in [
            ProblemType.BINARY_CLASSIFICATION,
            ProblemType.MULTICLASS_CLASSIFICATION
        ]:
            recommendations = self._get_classification_algorithms(
                data_profile, problem_type
            )
        elif problem_type == ProblemType.REGRESSION:
            recommendations = self._get_regression_algorithms(data_profile)
        else:
            # For other problem types, return empty for now
            logger.warning(f"Unsupported problem type: {problem_type}")
            return []

        # Adjust priorities based on optimization preference
        optimize_for = config.get("optimize_for", "accuracy")
        recommendations = self._adjust_priorities(
            recommendations, data_profile, optimize_for
        )

        # Sort by priority (descending)
        recommendations.sort(key=lambda x: x.priority, reverse=True)

        return recommendations

    def _get_classification_algorithms(
        self,
        data_profile: DataProfile,
        problem_type: ProblemType
    ) -> list[AlgorithmRecommendation]:
        """Get classification algorithm recommendations"""
        recommendations = []

        # Logistic Regression
        recommendations.append(self._create_logistic_regression_rec(data_profile))

        # Random Forest
        recommendations.append(self._create_random_forest_rec(data_profile))

        # XGBoost
        recommendations.append(self._create_xgboost_rec(data_profile))

        # LightGBM
        recommendations.append(self._create_lightgbm_rec(data_profile))

        # Gradient Boosting (for smaller datasets)
        if data_profile.n_samples < 10000:
            recommendations.append(
                self._create_gradient_boosting_rec(data_profile)
            )

        # SVM (for smaller datasets only)
        if data_profile.n_samples < self.small_dataset_threshold:
            recommendations.append(self._create_svm_rec(data_profile))

        # KNN (for smaller datasets)
        if data_profile.n_samples < 10000:
            recommendations.append(self._create_knn_rec(data_profile))

        return recommendations

    def _get_regression_algorithms(
        self,
        data_profile: DataProfile
    ) -> list[AlgorithmRecommendation]:
        """Get regression algorithm recommendations"""
        recommendations = []

        # Linear Regression
        recommendations.append(
            AlgorithmRecommendation(
                algorithm_name="Linear Regression",
                priority=7,
                expected_performance="Good for linear relationships",
                training_time_estimate="< 1 minute",
                interpretability_score=10,
                explanation="Simple linear model, best for linear relationships",
                pros=[
                    "Very interpretable",
                    "Fast training and prediction",
                    "Works well with linear relationships",
                    "Low memory footprint"
                ],
                cons=[
                    "Limited to linear relationships",
                    "Sensitive to outliers",
                    "Assumes feature independence"
                ]
            )
        )

        # Ridge Regression
        recommendations.append(
            AlgorithmRecommendation(
                algorithm_name="Ridge Regression",
                priority=7,
                expected_performance="Good with regularization",
                training_time_estimate="< 1 minute",
                interpretability_score=9,
                explanation="Linear regression with L2 regularization",
                pros=[
                    "Handles multicollinearity",
                    "Reduces overfitting",
                    "Interpretable coefficients"
                ],
                cons=[
                    "Still limited to linear relationships",
                    "Requires feature scaling",
                    "Doesn't perform feature selection"
                ]
            )
        )

        # Random Forest Regressor
        recommendations.append(
            AlgorithmRecommendation(
                algorithm_name="Random Forest Regressor",
                priority=8,
                expected_performance="70-85% R²",
                training_time_estimate="2-5 minutes",
                interpretability_score=6,
                explanation="Ensemble of decision trees for robust predictions",
                pros=[
                    "Handles non-linear relationships",
                    "Resistant to overfitting",
                    "Provides feature importance",
                    "No feature scaling needed"
                ],
                cons=[
                    "Less interpretable than linear models",
                    "Slower prediction",
                    "Memory intensive"
                ]
            )
        )

        # XGBoost Regressor
        recommendations.append(
            AlgorithmRecommendation(
                algorithm_name="XGBoost Regressor",
                priority=9,
                expected_performance="75-90% R²",
                training_time_estimate="2-8 minutes",
                interpretability_score=5,
                explanation="Gradient boosting optimized for performance",
                pros=[
                    "Often best performance",
                    "Handles missing values",
                    "Built-in regularization",
                    "Feature importance"
                ],
                cons=[
                    "Complex hyperparameters",
                    "Risk of overfitting",
                    "Less interpretable"
                ]
            )
        )

        # LightGBM Regressor
        recommendations.append(
            AlgorithmRecommendation(
                algorithm_name="LightGBM Regressor",
                priority=9,
                expected_performance="75-90% R²",
                training_time_estimate="1-5 minutes",
                interpretability_score=5,
                explanation="Fast gradient boosting for large datasets",
                pros=[
                    "Very fast training",
                    "Memory efficient",
                    "Handles large datasets well",
                    "Good with categorical features"
                ],
                cons=[
                    "Can overfit small datasets",
                    "Complex tuning",
                    "Less interpretable"
                ]
            )
        )

        return recommendations

    def _create_logistic_regression_rec(
        self, data_profile: DataProfile
    ) -> AlgorithmRecommendation:
        """Create Logistic Regression recommendation"""
        priority = 7

        # Increase priority for balanced datasets
        if data_profile.class_balance_ratio and data_profile.class_balance_ratio < 2.0:
            priority += 1

        explanation = "Simple, interpretable model for classification"
        if data_profile.class_balance_ratio and data_profile.class_balance_ratio > self.high_imbalance_threshold:
            explanation += ". Note: May need class balancing for imbalanced data"

        return AlgorithmRecommendation(
            algorithm_name="Logistic Regression",
            priority=priority,
            expected_performance="75-85% accuracy",
            training_time_estimate="< 1 minute",
            interpretability_score=10,
            explanation=explanation,
            pros=[
                "Highly interpretable",
                "Fast training and prediction",
                "Probability estimates",
                "Works well with linearly separable data"
            ],
            cons=[
                "Limited to linear decision boundaries",
                "May underperform on complex patterns",
                "Sensitive to feature scaling"
            ]
        )

    def _create_random_forest_rec(
        self, data_profile: DataProfile
    ) -> AlgorithmRecommendation:
        """Create Random Forest recommendation"""
        priority = 8

        # Increase priority for imbalanced data
        if data_profile.class_balance_ratio and data_profile.class_balance_ratio > self.high_imbalance_threshold:
            priority += 1

        explanation = "Robust ensemble model, good for most datasets"
        if data_profile.class_balance_ratio and data_profile.class_balance_ratio > self.high_imbalance_threshold:
            explanation += ". Handles class imbalance better than linear models"

        return AlgorithmRecommendation(
            algorithm_name="Random Forest",
            priority=priority,
            expected_performance="80-90% accuracy",
            training_time_estimate="2-5 minutes",
            interpretability_score=6,
            explanation=explanation,
            pros=[
                "Handles non-linear relationships",
                "Resistant to overfitting",
                "Provides feature importance",
                "No feature scaling needed"
            ],
            cons=[
                "Less interpretable than linear models",
                "Slower prediction than linear models",
                "Memory intensive for large forests"
            ]
        )

    def _create_xgboost_rec(
        self, data_profile: DataProfile
    ) -> AlgorithmRecommendation:
        """Create XGBoost recommendation"""
        priority = 9

        # Increase priority for large datasets
        if data_profile.dataset_size_category == "large":
            priority += 1

        # Increase priority for high cardinality
        if data_profile.high_cardinality_features > 0:
            priority += 1

        # Cap at 10
        priority = min(priority, 10)

        explanation = "State-of-the-art gradient boosting, often best performance"
        if data_profile.dataset_size_category == "large":
            explanation += ". Scales well to large datasets"

        return AlgorithmRecommendation(
            algorithm_name="XGBoost",
            priority=priority,
            expected_performance="85-95% accuracy",
            training_time_estimate="3-10 minutes",
            interpretability_score=5,
            explanation=explanation,
            pros=[
                "Often achieves best accuracy",
                "Handles missing values natively",
                "Built-in regularization",
                "Parallel processing"
            ],
            cons=[
                "Complex hyperparameters",
                "Risk of overfitting",
                "Less interpretable",
                "Longer training time"
            ]
        )

    def _create_lightgbm_rec(
        self, data_profile: DataProfile
    ) -> AlgorithmRecommendation:
        """Create LightGBM recommendation"""
        priority = 9

        # Highly prioritize for large datasets
        if data_profile.dataset_size_category == "large":
            priority = 10

        explanation = "Very fast gradient boosting, excellent for large datasets"
        if data_profile.dataset_size_category == "large":
            explanation += ". Optimized for your large dataset"

        return AlgorithmRecommendation(
            algorithm_name="LightGBM",
            priority=priority,
            expected_performance="85-95% accuracy",
            training_time_estimate="1-5 minutes",
            interpretability_score=5,
            explanation=explanation,
            pros=[
                "Very fast training",
                "Memory efficient",
                "Handles large datasets well",
                "Good with categorical features"
            ],
            cons=[
                "Can overfit on small datasets",
                "Complex hyperparameter tuning",
                "Less interpretable"
            ]
        )

    def _create_gradient_boosting_rec(
        self, data_profile: DataProfile
    ) -> AlgorithmRecommendation:
        """Create Gradient Boosting recommendation"""
        return AlgorithmRecommendation(
            algorithm_name="Gradient Boosting",
            priority=7,
            expected_performance="80-90% accuracy",
            training_time_estimate="5-15 minutes",
            interpretability_score=5,
            explanation="Classic gradient boosting, slower but robust",
            pros=[
                "Good accuracy",
                "Handles non-linear patterns",
                "Feature importance available"
            ],
            cons=[
                "Slower than LightGBM/XGBoost",
                "Risk of overfitting",
                "Less interpretable"
            ]
        )

    def _create_svm_rec(
        self, data_profile: DataProfile
    ) -> AlgorithmRecommendation:
        """Create SVM recommendation"""
        return AlgorithmRecommendation(
            algorithm_name="SVM",
            priority=6,
            expected_performance="75-88% accuracy",
            training_time_estimate="2-10 minutes",
            interpretability_score=4,
            explanation="Effective for smaller datasets with clear margins",
            pros=[
                "Works well in high dimensions",
                "Effective with clear margins",
                "Memory efficient (uses support vectors)"
            ],
            cons=[
                "Slow on large datasets",
                "Sensitive to feature scaling",
                "Difficult to interpret",
                "Requires kernel selection"
            ]
        )

    def _create_knn_rec(
        self, data_profile: DataProfile
    ) -> AlgorithmRecommendation:
        """Create KNN recommendation"""
        return AlgorithmRecommendation(
            algorithm_name="K-Nearest Neighbors",
            priority=5,
            expected_performance="70-85% accuracy",
            training_time_estimate="< 1 minute (training), slow prediction",
            interpretability_score=7,
            explanation="Simple distance-based classifier",
            pros=[
                "Simple and intuitive",
                "No training time",
                "Naturally handles multiclass"
            ],
            cons=[
                "Slow predictions on large datasets",
                "Sensitive to feature scaling",
                "Memory intensive for storage",
                "Curse of dimensionality"
            ]
        )

    def _adjust_priorities(
        self,
        recommendations: list[AlgorithmRecommendation],
        data_profile: DataProfile,
        optimize_for: str
    ) -> list[AlgorithmRecommendation]:
        """
        Adjust algorithm priorities based on optimization preference

        Args:
            recommendations: Base recommendations
            data_profile: Dataset profile
            optimize_for: "accuracy", "speed", or "interpretability"

        Returns:
            Recommendations with adjusted priorities
        """
        if optimize_for == "interpretability":
            # Boost interpretable models
            for rec in recommendations:
                if rec.interpretability_score >= 8:
                    rec.priority = min(rec.priority + 2, 10)
                elif rec.interpretability_score <= 5:
                    rec.priority = max(rec.priority - 1, 1)

        elif optimize_for == "speed":
            # Boost fast models
            fast_models = [
                "LightGBM",
                "Logistic Regression",
                "Linear Regression",
                "Ridge Regression"
            ]
            for rec in recommendations:
                if any(name in rec.algorithm_name for name in fast_models):
                    rec.priority = min(rec.priority + 2, 10)

        # For "accuracy", keep default priorities

        return recommendations
