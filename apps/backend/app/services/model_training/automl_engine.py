"""
Core AutoML engine for automated model selection and training
"""

from typing import Awaitable, Callable, Dict, List, Any, Optional, Tuple
import pandas as pd
import numpy as np
from dataclasses import dataclass
from datetime import datetime, timezone
import logging

from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, r2_score
from sklearn.linear_model import LogisticRegression, LinearRegression, Ridge
from sklearn.ensemble import (
    RandomForestClassifier, RandomForestRegressor,
    GradientBoostingClassifier, GradientBoostingRegressor
)
from sklearn.svm import SVC, SVR
from sklearn.neighbors import KNeighborsClassifier
import xgboost as xgb
import lightgbm as lgb

from .problem_detector import ProblemDetector, ProblemType
from .feature_engineer import FeatureEngineer, FeatureEngineeringConfig

logger = logging.getLogger(__name__)


@dataclass
class ModelCandidate:
    """A candidate model for training"""
    name: str
    estimator: Any
    hyperparameters: Dict[str, Any]
    training_time: Optional[float] = None
    cv_score: Optional[float] = None
    test_score: Optional[float] = None


@dataclass
class AutoMLResult:
    """Result of AutoML process"""
    best_model: ModelCandidate
    all_models: List[ModelCandidate]
    problem_type: ProblemType
    feature_names: List[str]
    feature_importance: Optional[Dict[str, float]]
    training_time: float
    metadata: Dict[str, Any]


class AutoMLEngine:
    """Main AutoML engine for automated machine learning"""
    
    def __init__(self, 
                 max_models: int = 10,
                 time_limit: Optional[int] = None,
                 cv_folds: int = 5,
                 test_size: float = 0.2,
                 random_state: int = 42):
        self.max_models = max_models
        self.time_limit = time_limit
        self.cv_folds = cv_folds
        self.test_size = test_size
        self.random_state = random_state
        
        self.problem_detector = ProblemDetector()
        self.feature_engineer = FeatureEngineer()
    
    async def run(
        self,
        df: pd.DataFrame,
        target_column: str,
        feature_config: Optional[FeatureEngineeringConfig] = None,
        progress_callback: Optional[
            Callable[[int, int, str], Awaitable[None]]
        ] = None,
    ) -> AutoMLResult:
        """
        Run the AutoML pipeline

        Args:
            df: Input dataframe
            target_column: Name of target column
            feature_config: Feature engineering configuration
            progress_callback: Optional async callback invoked as
                ``await progress_callback(completed, total, current_algorithm)``
                before each candidate is trained and once more when all
                candidates finish. Callback errors are swallowed so progress
                reporting never breaks training.

        Returns:
            AutoMLResult with best model and metadata
        """
        start_time = datetime.now(timezone.utc)
        
        # Detect problem type
        detection_result = await self.problem_detector.detect_problem_type(
            df, target_column
        )
        problem_type = detection_result.problem_type
        
        logger.info(f"Detected problem type: {problem_type.value}")
        
        # Prepare data
        X = df.drop(columns=[target_column])
        y = df[target_column]
        
        is_classification = problem_type in [
            ProblemType.BINARY_CLASSIFICATION,
            ProblemType.MULTICLASS_CLASSIFICATION,
        ]

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=self.test_size, random_state=self.random_state,
            stratify=y if is_classification else None
        )

        # Detect class imbalance and enable basic handling (class weighting).
        # This is the lightweight "basic class-imbalance handling" of the beta
        # scope: no resampling (SMOTE etc.), just class_weight="balanced" on the
        # estimators that support it.
        class_balance_ratio, class_weight = self._assess_class_balance(
            y_train, is_classification
        )

        # Feature engineering
        if feature_config:
            self.feature_engineer.config = feature_config

        feature_result = await self.feature_engineer.fit_transform(
            X_train, y_train, problem_type.value
        )
        X_train_transformed = feature_result.X_transformed

        # Transform test data
        X_test_transformed = await self.feature_engineer.transform(X_test)

        # Get candidate models
        candidates = self._get_candidate_models(
            problem_type, X_train_transformed.shape, class_weight=class_weight
        )
        
        # Train and evaluate models
        selected_candidates = candidates[:self.max_models]
        total_candidates = len(selected_candidates)
        trained_models = []
        for index, candidate in enumerate(selected_candidates):
            logger.info(f"Training {candidate.name}...")
            await self._report_progress(
                progress_callback, index, total_candidates, candidate.name
            )

            try:
                # Train model
                model_start = datetime.now(timezone.utc)
                candidate.estimator.fit(X_train_transformed, y_train)
                candidate.training_time = (datetime.now(timezone.utc) - model_start).total_seconds()
                
                # Cross-validation score
                cv_scores = cross_val_score(
                    candidate.estimator,
                    X_train_transformed,
                    y_train,
                    cv=self.cv_folds,
                    scoring=self._get_scoring_metric(problem_type)
                )
                candidate.cv_score = np.mean(cv_scores)
                
                # Test score
                y_pred = candidate.estimator.predict(X_test_transformed)
                candidate.test_score = self._calculate_test_score(
                    y_test, y_pred, problem_type
                )
                
                trained_models.append(candidate)
                logger.info(f"{candidate.name} - CV Score: {candidate.cv_score:.4f}, Test Score: {candidate.test_score:.4f}")
                
            except Exception as e:
                logger.error(f"Error training {candidate.name}: {str(e)}")
                continue
        
        # Final progress tick: all candidates processed.
        await self._report_progress(
            progress_callback, total_candidates, total_candidates, None
        )

        # Select best model
        if not trained_models:
            raise ValueError("No models were successfully trained")
        best_model = max(trained_models, key=lambda m: m.cv_score)
        ranked_models = sorted(trained_models, key=lambda m: m.cv_score, reverse=True)

        # Get feature importance if available
        feature_importance = self._get_feature_importance(
            best_model.estimator,
            feature_result.feature_names
        )

        total_time = (datetime.now(timezone.utc) - start_time).total_seconds()

        # Side-by-side comparison of every trained candidate, ranked by CV score.
        model_comparison = [
            {
                "algorithm": m.name,
                "cv_score": m.cv_score,
                "test_score": m.test_score,
                "training_time": m.training_time,
            }
            for m in ranked_models
        ]

        return AutoMLResult(
            best_model=best_model,
            all_models=ranked_models,
            problem_type=problem_type,
            feature_names=feature_result.feature_names,
            feature_importance=feature_importance,
            training_time=total_time,
            metadata={
                "n_samples": len(df),
                "n_features_original": len(X.columns),
                "n_features_engineered": len(feature_result.feature_names),
                "feature_engineering": feature_result.metadata,
                "model_comparison": model_comparison,
                "class_balance": {
                    "ratio": class_balance_ratio,
                    "balancing_applied": class_weight is not None,
                },
                "detection_result": {
                    "confidence": detection_result.confidence,
                    "reasoning": detection_result.reasoning
                }
            }
        )

    @staticmethod
    async def _report_progress(
        progress_callback: Optional[Callable[[int, int, str], Awaitable[None]]],
        completed: int,
        total: int,
        current_algorithm: Optional[str],
    ) -> None:
        """Invoke the progress callback, swallowing any error it raises."""
        if progress_callback is None:
            return
        try:
            await progress_callback(completed, total, current_algorithm)
        except Exception as exc:  # progress reporting must never break training
            logger.warning(f"Progress callback failed: {exc}")

    @staticmethod
    def _assess_class_balance(
        y_train: pd.Series, is_classification: bool
    ) -> Tuple[Optional[float], Optional[str]]:
        """Return (majority/minority ratio, class_weight) for the training labels.

        ``class_weight`` is ``"balanced"`` when the ratio exceeds 2:1, otherwise
        ``None``. For regression both values are ``None``.
        """
        if not is_classification:
            return None, None
        counts = y_train.value_counts()
        if len(counts) < 2 or counts.min() == 0:
            return None, None
        ratio = float(counts.max() / counts.min())
        class_weight = "balanced" if ratio > 2.0 else None
        return ratio, class_weight
    
    def _get_candidate_models(
        self,
        problem_type: ProblemType,
        data_shape: Tuple[int, int],
        class_weight: Optional[str] = None
    ) -> List[ModelCandidate]:
        """Get candidate models based on problem type and data characteristics.

        ``class_weight`` (e.g. ``"balanced"``) is applied to the classifiers that
        support it — Logistic Regression, Random Forest, SVM and LightGBM — to
        provide basic class-imbalance handling. XGBoost, Gradient Boosting and KNN
        do not take a ``class_weight`` and are left unchanged.
        """
        n_samples, n_features = data_shape
        candidates = []

        if problem_type in [ProblemType.BINARY_CLASSIFICATION, ProblemType.MULTICLASS_CLASSIFICATION]:
            # Logistic Regression
            candidates.append(ModelCandidate(
                name="Logistic Regression",
                estimator=LogisticRegression(
                    random_state=self.random_state,
                    max_iter=1000,
                    class_weight=class_weight
                ),
                hyperparameters={"C": 1.0, "penalty": "l2", "class_weight": class_weight}
            ))

            # Random Forest
            candidates.append(ModelCandidate(
                name="Random Forest",
                estimator=RandomForestClassifier(
                    n_estimators=100,
                    random_state=self.random_state,
                    n_jobs=-1,
                    class_weight=class_weight
                ),
                hyperparameters={"n_estimators": 100, "max_depth": None, "class_weight": class_weight}
            ))
            
            # XGBoost
            candidates.append(ModelCandidate(
                name="XGBoost",
                estimator=xgb.XGBClassifier(
                    n_estimators=100,
                    random_state=self.random_state,
                    n_jobs=-1,
                    eval_metric='logloss' if problem_type == ProblemType.BINARY_CLASSIFICATION else 'mlogloss'
                ),
                hyperparameters={"n_estimators": 100, "learning_rate": 0.1}
            ))
            
            # LightGBM
            candidates.append(ModelCandidate(
                name="LightGBM",
                estimator=lgb.LGBMClassifier(
                    n_estimators=100,
                    random_state=self.random_state,
                    n_jobs=-1,
                    verbosity=-1,
                    class_weight=class_weight
                ),
                hyperparameters={"n_estimators": 100, "learning_rate": 0.1, "class_weight": class_weight}
            ))

            # Gradient Boosting
            if n_samples < 10000:  # Slower for large datasets
                candidates.append(ModelCandidate(
                    name="Gradient Boosting",
                    estimator=GradientBoostingClassifier(
                        n_estimators=100,
                        random_state=self.random_state
                    ),
                    hyperparameters={"n_estimators": 100, "learning_rate": 0.1}
                ))
            
            # SVM (for smaller datasets)
            if n_samples < 5000:
                candidates.append(ModelCandidate(
                    name="SVM",
                    estimator=SVC(
                        kernel='rbf',
                        random_state=self.random_state,
                        probability=True,
                        class_weight=class_weight
                    ),
                    hyperparameters={"C": 1.0, "kernel": "rbf", "class_weight": class_weight}
                ))
            
            # KNN (for smaller datasets)
            if n_samples < 10000:
                candidates.append(ModelCandidate(
                    name="K-Nearest Neighbors",
                    estimator=KNeighborsClassifier(n_neighbors=5, n_jobs=-1),
                    hyperparameters={"n_neighbors": 5}
                ))
            
        elif problem_type == ProblemType.REGRESSION:
            # Linear Regression
            candidates.append(ModelCandidate(
                name="Linear Regression",
                estimator=LinearRegression(n_jobs=-1),
                hyperparameters={}
            ))
            
            # Ridge Regression
            candidates.append(ModelCandidate(
                name="Ridge Regression",
                estimator=Ridge(random_state=self.random_state),
                hyperparameters={"alpha": 1.0}
            ))
            
            # Random Forest
            candidates.append(ModelCandidate(
                name="Random Forest Regressor",
                estimator=RandomForestRegressor(
                    n_estimators=100,
                    random_state=self.random_state,
                    n_jobs=-1
                ),
                hyperparameters={"n_estimators": 100}
            ))
            
            # XGBoost
            candidates.append(ModelCandidate(
                name="XGBoost Regressor",
                estimator=xgb.XGBRegressor(
                    n_estimators=100,
                    random_state=self.random_state,
                    n_jobs=-1
                ),
                hyperparameters={"n_estimators": 100, "learning_rate": 0.1}
            ))
            
            # LightGBM
            candidates.append(ModelCandidate(
                name="LightGBM Regressor",
                estimator=lgb.LGBMRegressor(
                    n_estimators=100,
                    random_state=self.random_state,
                    n_jobs=-1,
                    verbosity=-1
                ),
                hyperparameters={"n_estimators": 100, "learning_rate": 0.1}
            ))
            
            # Gradient Boosting
            if n_samples < 10000:
                candidates.append(ModelCandidate(
                    name="Gradient Boosting Regressor",
                    estimator=GradientBoostingRegressor(
                        n_estimators=100,
                        random_state=self.random_state
                    ),
                    hyperparameters={"n_estimators": 100, "learning_rate": 0.1}
                ))
            
            # SVR (for smaller datasets)
            if n_samples < 5000:
                candidates.append(ModelCandidate(
                    name="Support Vector Regressor",
                    estimator=SVR(kernel='rbf'),
                    hyperparameters={"C": 1.0, "kernel": "rbf"}
                ))
        
        return candidates
    
    def _get_scoring_metric(self, problem_type: ProblemType) -> str:
        """Get appropriate scoring metric for problem type"""
        if problem_type == ProblemType.BINARY_CLASSIFICATION:
            return "roc_auc"
        elif problem_type == ProblemType.MULTICLASS_CLASSIFICATION:
            return "f1_weighted"
        elif problem_type == ProblemType.REGRESSION:
            return "neg_mean_squared_error"
        else:
            return "accuracy"
    
    def _calculate_test_score(
        self,
        y_true: pd.Series,
        y_pred: np.ndarray,
        problem_type: ProblemType
    ) -> float:
        """Calculate test score based on problem type"""
        if problem_type in [ProblemType.BINARY_CLASSIFICATION, ProblemType.MULTICLASS_CLASSIFICATION]:
            return accuracy_score(y_true, y_pred)
        elif problem_type == ProblemType.REGRESSION:
            return r2_score(y_true, y_pred)
        else:
            return 0.0
    
    def _get_feature_importance(
        self,
        model: Any,
        feature_names: List[str]
    ) -> Optional[Dict[str, float]]:
        """Extract feature importance from model if available"""
        importance = None
        
        # Tree-based models
        if hasattr(model, 'feature_importances_'):
            importance = model.feature_importances_
        # Linear models
        elif hasattr(model, 'coef_'):
            importance = np.abs(model.coef_).flatten()
        else:
            return None
        
        # Create importance dictionary
        if importance is not None:
            feature_importance = {
                name: float(imp) for name, imp in zip(feature_names, importance)
            }
            # Sort by importance
            feature_importance = dict(
                sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)
            )
            return feature_importance
        
        return None