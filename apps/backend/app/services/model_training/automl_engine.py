"""
Core AutoML engine for automated model selection and training
"""

from typing import Dict, List, Any, Optional, Tuple
import pandas as pd
import numpy as np
from dataclasses import dataclass
from datetime import datetime, timezone
import logging

from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, f1_score, mean_squared_error, r2_score
from sklearn.linear_model import LogisticRegression, LinearRegression, Ridge, Lasso
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from sklearn.ensemble import (
    RandomForestClassifier, RandomForestRegressor,
    GradientBoostingClassifier, GradientBoostingRegressor
)
from sklearn.svm import SVC, SVR
from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
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
        feature_config: Optional[FeatureEngineeringConfig] = None
    ) -> AutoMLResult:
        """
        Run the AutoML pipeline
        
        Args:
            df: Input dataframe
            target_column: Name of target column
            feature_config: Feature engineering configuration
            
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
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=self.test_size, random_state=self.random_state,
            stratify=y if problem_type in [
                ProblemType.BINARY_CLASSIFICATION,
                ProblemType.MULTICLASS_CLASSIFICATION
            ] else None
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
        candidates = self._get_candidate_models(problem_type, X_train_transformed.shape)
        
        # Train and evaluate models
        trained_models = []
        for candidate in candidates[:self.max_models]:
            logger.info(f"Training {candidate.name}...")
            
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
        
        # Select best model
        if not trained_models:
            raise ValueError("No models were successfully trained")
        best_model = max(trained_models, key=lambda m: m.cv_score)
        
        # Get feature importance if available
        feature_importance = self._get_feature_importance(
            best_model.estimator,
            feature_result.feature_names
        )
        
        total_time = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        return AutoMLResult(
            best_model=best_model,
            all_models=sorted(trained_models, key=lambda m: m.cv_score, reverse=True),
            problem_type=problem_type,
            feature_names=feature_result.feature_names,
            feature_importance=feature_importance,
            training_time=total_time,
            metadata={
                "n_samples": len(df),
                "n_features_original": len(X.columns),
                "n_features_engineered": len(feature_result.feature_names),
                "feature_engineering": feature_result.metadata,
                "detection_result": {
                    "confidence": detection_result.confidence,
                    "reasoning": detection_result.reasoning
                }
            }
        )
    
    def _get_candidate_models(
        self,
        problem_type: ProblemType,
        data_shape: Tuple[int, int]
    ) -> List[ModelCandidate]:
        """Get candidate models based on problem type and data characteristics"""
        n_samples, n_features = data_shape
        candidates = []
        
        if problem_type in [ProblemType.BINARY_CLASSIFICATION, ProblemType.MULTICLASS_CLASSIFICATION]:
            # Logistic Regression
            candidates.append(ModelCandidate(
                name="Logistic Regression",
                estimator=LogisticRegression(random_state=self.random_state, max_iter=1000),
                hyperparameters={"C": 1.0, "penalty": "l2"}
            ))
            
            # Random Forest
            candidates.append(ModelCandidate(
                name="Random Forest",
                estimator=RandomForestClassifier(
                    n_estimators=100,
                    random_state=self.random_state,
                    n_jobs=-1
                ),
                hyperparameters={"n_estimators": 100, "max_depth": None}
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
                    verbosity=-1
                ),
                hyperparameters={"n_estimators": 100, "learning_rate": 0.1}
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
                        probability=True
                    ),
                    hyperparameters={"C": 1.0, "kernel": "rbf"}
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