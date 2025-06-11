"""
Feature engineering for AutoML
"""

from typing import Dict, List, Tuple, Any, Optional
import pandas as pd
import numpy as np
from sklearn.preprocessing import (
    StandardScaler, MinMaxScaler, RobustScaler,
    LabelEncoder, OneHotEncoder
)
from sklearn.impute import SimpleImputer
from sklearn.feature_selection import (
    SelectKBest, f_classif, f_regression,
    mutual_info_classif, mutual_info_regression
)
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class FeatureEngineeringConfig:
    """Configuration for feature engineering"""
    handle_missing: bool = True
    scale_features: bool = True
    encode_categorical: bool = True
    create_interactions: bool = False
    select_features: bool = True
    max_features: Optional[int] = None
    scaling_method: str = "standard"  # standard, minmax, robust
    encoding_method: str = "onehot"  # onehot, label
    missing_strategy: str = "mean"  # mean, median, most_frequent, constant


@dataclass
class FeatureEngineeringResult:
    """Result of feature engineering"""
    X_transformed: pd.DataFrame
    feature_names: List[str]
    transformers: Dict[str, Any]
    feature_importance: Optional[Dict[str, float]]
    metadata: Dict[str, Any]


class FeatureEngineer:
    """Automated feature engineering for ML models"""
    
    def __init__(self, config: Optional[FeatureEngineeringConfig] = None):
        self.config = config or FeatureEngineeringConfig()
        self.transformers = {}
        self.feature_names = []
        self.numeric_features = []
        self.categorical_features = []
    
    async def fit_transform(
        self,
        X: pd.DataFrame,
        y: Optional[pd.Series] = None,
        problem_type: Optional[str] = None
    ) -> FeatureEngineeringResult:
        """
        Fit and transform features
        
        Args:
            X: Input features
            y: Target variable (optional, for feature selection)
            problem_type: Type of ML problem
            
        Returns:
            FeatureEngineeringResult with transformed features
        """
        X_transformed = X.copy()
        
        # Identify feature types
        self._identify_feature_types(X_transformed)
        
        # Handle missing values
        if self.config.handle_missing:
            X_transformed = await self._handle_missing_values(X_transformed)
        
        # Encode categorical features
        if self.config.encode_categorical and self.categorical_features:
            X_transformed = await self._encode_categorical_features(X_transformed)
        
        # Scale numeric features
        if self.config.scale_features and self.numeric_features:
            X_transformed = await self._scale_numeric_features(X_transformed)
        
        # Create interaction features
        if self.config.create_interactions:
            X_transformed = await self._create_interaction_features(X_transformed)
        
        # Select best features
        feature_importance = None
        if self.config.select_features and y is not None:
            X_transformed, feature_importance = await self._select_features(
                X_transformed, y, problem_type
            )
        
        # Update feature names
        self.feature_names = list(X_transformed.columns)
        
        return FeatureEngineeringResult(
            X_transformed=X_transformed,
            feature_names=self.feature_names,
            transformers=self.transformers,
            feature_importance=feature_importance,
            metadata={
                "original_features": list(X.columns),
                "numeric_features": self.numeric_features,
                "categorical_features": self.categorical_features,
                "final_feature_count": len(self.feature_names)
            }
        )
    
    async def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """Transform new data using fitted transformers"""
        X_transformed = X.copy()
        
        # Apply transformations in the same order
        # Handle missing values
        if "imputer_numeric" in self.transformers:
            X_transformed[self.numeric_features] = self.transformers["imputer_numeric"].transform(
                X_transformed[self.numeric_features]
            )
        
        if "imputer_categorical" in self.transformers:
            X_transformed[self.categorical_features] = self.transformers["imputer_categorical"].transform(
                X_transformed[self.categorical_features]
            )
        
        # Encode categorical
        if "encoder" in self.transformers:
            if self.config.encoding_method == "onehot":
                encoded = self.transformers["encoder"].transform(
                    X_transformed[self.categorical_features]
                )
                encoded_df = pd.DataFrame(
                    encoded,
                    columns=self.transformers["encoded_columns"],
                    index=X_transformed.index
                )
                X_transformed = pd.concat([
                    X_transformed.drop(columns=self.categorical_features),
                    encoded_df
                ], axis=1)
            else:
                for col in self.categorical_features:
                    if col in self.transformers["label_encoders"]:
                        X_transformed[col] = self.transformers["label_encoders"][col].transform(
                            X_transformed[col]
                        )
        
        # Scale numeric
        if "scaler" in self.transformers:
            X_transformed[self.numeric_features] = self.transformers["scaler"].transform(
                X_transformed[self.numeric_features]
            )
        
        # Create interaction features if they were created during training
        if "interaction_features" in self.transformers:
            for feat in self.transformers["interaction_features"]:
                if "_x_" in feat:
                    col1, col2 = feat.split("_x_")
                    if col1 in X_transformed.columns and col2 in X_transformed.columns:
                        X_transformed[feat] = X_transformed[col1] * X_transformed[col2]
                elif "_div_" in feat:
                    col1, col2 = feat.split("_div_")
                    if col1 in X_transformed.columns and col2 in X_transformed.columns:
                        X_transformed[feat] = X_transformed[col1] / (X_transformed[col2] + 1e-8)
        
        # Select features
        if "selector" in self.transformers:
            # Only keep columns that exist in the transformed data
            available_features = [f for f in self.transformers["selected_features"] if f in X_transformed.columns]
            X_transformed = X_transformed[available_features]
        
        return X_transformed
    
    def _identify_feature_types(self, df: pd.DataFrame):
        """Identify numeric and categorical features"""
        self.numeric_features = list(df.select_dtypes(include=[np.number]).columns)
        self.categorical_features = list(df.select_dtypes(include=["object", "category"]).columns)
        
        # Check for numeric columns that might be categorical
        for col in self.numeric_features.copy():
            if df[col].nunique() < 10 and df[col].nunique() / len(df) < 0.05:
                self.numeric_features.remove(col)
                self.categorical_features.append(col)
    
    async def _handle_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """Handle missing values in features"""
        # Numeric features
        if self.numeric_features:
            numeric_imputer = SimpleImputer(strategy=self.config.missing_strategy)
            df[self.numeric_features] = numeric_imputer.fit_transform(df[self.numeric_features])
            self.transformers["imputer_numeric"] = numeric_imputer
        
        # Categorical features
        if self.categorical_features:
            categorical_imputer = SimpleImputer(strategy="most_frequent")
            try:
                # Handle case where result might be numpy array
                imputed_data = categorical_imputer.fit_transform(df[self.categorical_features])
                if isinstance(imputed_data, np.ndarray) and imputed_data.size > 0:
                    # Only create DataFrame if there's data
                    if imputed_data.shape[1] == len(self.categorical_features):
                        df[self.categorical_features] = pd.DataFrame(
                            imputed_data, 
                            columns=self.categorical_features,
                            index=df.index
                        )
                    else:
                        # Handle case where some columns were dropped
                        df = df.drop(columns=self.categorical_features)
                else:
                    df[self.categorical_features] = imputed_data
            except ValueError:
                # Handle case where all values are missing
                logger.warning(f"Could not impute categorical features: {self.categorical_features}")
                # Keep columns but leave as is
            self.transformers["imputer_categorical"] = categorical_imputer
        
        return df
    
    async def _encode_categorical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Encode categorical features"""
        if self.config.encoding_method == "onehot":
            encoder = OneHotEncoder(sparse_output=False, handle_unknown="ignore")
            encoded = encoder.fit_transform(df[self.categorical_features])
            
            # Create column names
            encoded_columns = []
            for i, col in enumerate(self.categorical_features):
                for cat in encoder.categories_[i]:
                    encoded_columns.append(f"{col}_{cat}")
            
            # Create dataframe with encoded features
            encoded_df = pd.DataFrame(
                encoded,
                columns=encoded_columns,
                index=df.index
            )
            
            # Replace original categorical columns
            df = pd.concat([
                df.drop(columns=self.categorical_features),
                encoded_df
            ], axis=1)
            
            self.transformers["encoder"] = encoder
            self.transformers["encoded_columns"] = encoded_columns
            
        else:  # label encoding
            label_encoders = {}
            for col in self.categorical_features:
                le = LabelEncoder()
                df[col] = le.fit_transform(df[col].astype(str))
                label_encoders[col] = le
            
            self.transformers["label_encoders"] = label_encoders
        
        return df
    
    async def _scale_numeric_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Scale numeric features"""
        if self.config.scaling_method == "standard":
            scaler = StandardScaler()
        elif self.config.scaling_method == "minmax":
            scaler = MinMaxScaler()
        else:  # robust
            scaler = RobustScaler()
        
        df[self.numeric_features] = scaler.fit_transform(df[self.numeric_features])
        self.transformers["scaler"] = scaler
        
        return df
    
    async def _create_interaction_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create interaction features between numeric columns"""
        if len(self.numeric_features) < 2:
            return df
        
        # Create pairwise interactions for top features
        interaction_features = []
        for i in range(min(5, len(self.numeric_features))):
            for j in range(i + 1, min(5, len(self.numeric_features))):
                col1, col2 = self.numeric_features[i], self.numeric_features[j]
                
                # Multiplication interaction
                interaction_name = f"{col1}_x_{col2}"
                df[interaction_name] = df[col1] * df[col2]
                interaction_features.append(interaction_name)
                
                # Division interaction (with small epsilon to avoid division by zero)
                if (df[col2] != 0).all():
                    interaction_name = f"{col1}_div_{col2}"
                    df[interaction_name] = df[col1] / (df[col2] + 1e-8)
                    interaction_features.append(interaction_name)
        
        self.transformers["interaction_features"] = interaction_features
        return df
    
    async def _select_features(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        problem_type: Optional[str] = None
    ) -> Tuple[pd.DataFrame, Dict[str, float]]:
        """Select best features based on importance"""
        # Determine scoring function
        if problem_type and "classification" in problem_type.lower():
            score_func = f_classif
        else:
            score_func = f_regression
        
        # Determine k
        k = min(
            self.config.max_features or X.shape[1],
            X.shape[1]
        )
        
        # Select features
        selector = SelectKBest(score_func=score_func, k=k)
        X_selected = selector.fit_transform(X, y)
        
        # Get selected feature names
        selected_mask = selector.get_support()
        selected_features = [col for col, selected in zip(X.columns, selected_mask) if selected]
        
        # Calculate feature importance
        scores = selector.scores_
        feature_importance = {
            col: float(score) for col, score, selected in 
            zip(X.columns, scores, selected_mask) if selected
        }
        
        # Sort by importance
        feature_importance = dict(
            sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)
        )
        
        # Create selected dataframe
        X_selected_df = pd.DataFrame(
            X_selected,
            columns=selected_features,
            index=X.index
        )
        
        self.transformers["selector"] = selector
        self.transformers["selected_features"] = selected_features
        
        return X_selected_df, feature_importance