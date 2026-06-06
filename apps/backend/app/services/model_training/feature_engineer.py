"""
Feature engineering for AutoML
"""

import json
from typing import Dict, List, Tuple, Any, Optional, TYPE_CHECKING
import pandas as pd
import numpy as np
from pydantic import ValidationError as PydanticValidationError
from sklearn.preprocessing import (
    StandardScaler, MinMaxScaler, RobustScaler,
    LabelEncoder, OneHotEncoder
)
from sklearn.impute import SimpleImputer
from sklearn.feature_selection import (
    SelectKBest, f_classif, f_regression
)
from dataclasses import dataclass
import logging

from app.models.feature import ExpressionNode
from app.services.exceptions import (
    UnsafeFeatureDefinitionError,
    ValidationError,
)
from app.services.expression_evaluator import (
    ExpressionError,
    ExpressionEvaluator,
)

if TYPE_CHECKING:
    from app.models.feature_store import StoredFeature

logger = logging.getLogger(__name__)


def parse_feature_definition(definition_code: str) -> ExpressionNode:
    """
    Parse a Feature Store definition into a safe expression tree.

    SECURITY (GH-132): ``definition_code`` must be a JSON-serialized
    ExpressionNode tree. It is parsed and validated — NEVER executed.
    Raw Python code (the legacy format) is rejected here, which makes
    arbitrary file system, network, import, and system-command access
    impossible by construction.

    Args:
        definition_code: JSON-serialized ExpressionNode tree

    Returns:
        Validated ExpressionNode root

    Raises:
        UnsafeFeatureDefinitionError: If the definition is not a valid
            serialized expression tree (including legacy raw Python code)
    """
    try:
        data = json.loads(definition_code)
    except (json.JSONDecodeError, TypeError):
        raise UnsafeFeatureDefinitionError(
            message=(
                "Feature definition must be a JSON-serialized expression tree. "
                "Raw code is not supported — recreate the feature with the "
                "Visual Feature Builder."
            )
        )

    if not isinstance(data, dict):
        raise UnsafeFeatureDefinitionError(
            message="Feature definition must be a JSON object describing an expression tree"
        )

    try:
        return ExpressionNode.model_validate(data)
    except PydanticValidationError as e:
        raise UnsafeFeatureDefinitionError(
            message="Feature definition is not a valid expression tree",
            details={"errors": [err["msg"] for err in e.errors()]},
        )


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

    async def apply_suggestion(
        self,
        df: pd.DataFrame,
        suggestion: Any
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Apply a single feature suggestion to a dataframe.

        Args:
            df: Input dataframe
            suggestion: FeatureSuggestion object with feature details

        Returns:
            Tuple of (transformed dataframe, metadata dict)
        """
        df = df.copy()
        metadata: Dict[str, Any] = {
            "feature_name": suggestion.name,
            "success": False,
            "error": None
        }

        try:
            feature_type = suggestion.feature_type
            params = suggestion.parameters
            input_cols = suggestion.input_columns

            # Validate input columns
            missing_cols = [c for c in input_cols if c not in df.columns]
            if missing_cols:
                metadata["error"] = f"Missing columns: {missing_cols}"
                return df, metadata

            # Apply based on feature type
            if feature_type.value == "polynomial":
                df = self._apply_polynomial(df, suggestion.name, input_cols, params)
            elif feature_type.value == "interaction":
                df = self._apply_interaction(df, suggestion.name, input_cols, params)
            elif feature_type.value == "aggregation":
                df = self._apply_aggregation(df, suggestion.name, input_cols, params)
            elif feature_type.value == "time_based":
                df = self._apply_time_based(df, suggestion.name, input_cols, params)
            elif feature_type.value == "text":
                df = self._apply_text(df, suggestion.name, input_cols, params)
            elif feature_type.value == "binning":
                df = self._apply_binning(df, suggestion.name, input_cols, params)
            elif feature_type.value == "encoding":
                df = await self._apply_encoding(df, suggestion.name, input_cols, params)
            elif feature_type.value == "scaling":
                df = self._apply_scaling(df, suggestion.name, input_cols, params)
            else:
                # Try generic application for mathematical/domain-specific
                df = self._apply_generic(df, suggestion.name, input_cols, params)

            metadata["success"] = True
            metadata["new_columns"] = [suggestion.name]

        except Exception as e:
            logger.error(f"Error applying suggestion {suggestion.name}: {e}")
            metadata["error"] = str(e)

        return df, metadata

    async def apply_multiple_suggestions(
        self,
        df: pd.DataFrame,
        suggestions: List[Any]
    ) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
        """
        Apply multiple feature suggestions to a dataframe.

        Args:
            df: Input dataframe
            suggestions: List of FeatureSuggestion objects

        Returns:
            Tuple of (transformed dataframe, list of metadata dicts)
        """
        all_metadata: List[Dict[str, Any]] = []

        for suggestion in suggestions:
            df, metadata = await self.apply_suggestion(df, suggestion)
            all_metadata.append(metadata)

        return df, all_metadata

    def _apply_polynomial(
        self,
        df: pd.DataFrame,
        name: str,
        input_cols: List[str],
        params: Dict[str, Any]
    ) -> pd.DataFrame:
        """Apply polynomial transformation"""
        col = input_cols[0]
        func = params.get("function", "")
        power = params.get("power", 2)

        if func == "sqrt":
            df[name] = np.sqrt(df[col].clip(lower=0))
        elif func == "log":
            df[name] = np.log1p(df[col].clip(lower=0))
        elif func == "exp":
            df[name] = np.exp(df[col].clip(upper=100))  # Prevent overflow
        else:
            df[name] = df[col] ** power

        return df

    def _apply_interaction(
        self,
        df: pd.DataFrame,
        name: str,
        input_cols: List[str],
        params: Dict[str, Any]
    ) -> pd.DataFrame:
        """Apply interaction transformation"""
        col1, col2 = input_cols[0], input_cols[1]
        operation = params.get("operation", "multiply")

        if operation == "multiply":
            df[name] = df[col1] * df[col2]
        elif operation == "divide":
            df[name] = df[col1] / (df[col2] + 1e-8)
        elif operation == "add":
            df[name] = df[col1] + df[col2]
        elif operation == "subtract":
            df[name] = df[col1] - df[col2]

        return df

    def _apply_aggregation(
        self,
        df: pd.DataFrame,
        name: str,
        input_cols: List[str],
        params: Dict[str, Any]
    ) -> pd.DataFrame:
        """Apply aggregation transformation"""
        aggregation = params.get("aggregation", "mean")
        group_by = params.get("group_by")

        if not group_by or group_by not in df.columns:
            raise ValueError(f"Group by column '{group_by}' not found")

        if aggregation == "mean" and len(input_cols) > 0:
            num_col = input_cols[0]
            df[name] = df.groupby(group_by)[num_col].transform("mean")
        elif aggregation == "sum" and len(input_cols) > 0:
            num_col = input_cols[0]
            df[name] = df.groupby(group_by)[num_col].transform("sum")
        elif aggregation == "count":
            df[name] = df.groupby(group_by)[group_by].transform("count")
        elif aggregation == "std" and len(input_cols) > 0:
            num_col = input_cols[0]
            df[name] = df.groupby(group_by)[num_col].transform("std")
        elif aggregation == "median" and len(input_cols) > 0:
            num_col = input_cols[0]
            df[name] = df.groupby(group_by)[num_col].transform("median")

        return df

    def _apply_time_based(
        self,
        df: pd.DataFrame,
        name: str,
        input_cols: List[str],
        params: Dict[str, Any]
    ) -> pd.DataFrame:
        """Apply time-based transformation"""
        col = input_cols[0]
        extract = params.get("extract", "")

        # Convert to datetime if needed
        dt_col = pd.to_datetime(df[col], errors='coerce')

        if extract == "dayofweek":
            df[name] = dt_col.dt.dayofweek
        elif extract == "month":
            df[name] = dt_col.dt.month
        elif extract == "day":
            df[name] = dt_col.dt.day
        elif extract == "hour":
            df[name] = dt_col.dt.hour
        elif extract == "minute":
            df[name] = dt_col.dt.minute
        elif extract == "quarter":
            df[name] = dt_col.dt.quarter
        elif extract == "year":
            df[name] = dt_col.dt.year
        elif extract == "is_weekend":
            df[name] = dt_col.dt.dayofweek.isin([5, 6]).astype(int)
        elif extract == "is_month_start":
            df[name] = dt_col.dt.is_month_start.astype(int)
        elif extract == "is_month_end":
            df[name] = dt_col.dt.is_month_end.astype(int)

        return df

    def _apply_text(
        self,
        df: pd.DataFrame,
        name: str,
        input_cols: List[str],
        params: Dict[str, Any]
    ) -> pd.DataFrame:
        """Apply text transformation"""
        col = input_cols[0]
        operation = params.get("operation", "")

        str_col = df[col].astype(str)

        if operation == "char_count":
            df[name] = str_col.str.len()
        elif operation == "word_count":
            df[name] = str_col.str.split().str.len()
        elif operation == "has_special":
            df[name] = str_col.str.contains(r'[!@#$%^&*]', regex=True).astype(int)
        elif operation == "is_upper":
            df[name] = str_col.str.isupper().astype(int)
        elif operation == "is_lower":
            df[name] = str_col.str.islower().astype(int)
        elif operation == "digit_count":
            df[name] = str_col.str.count(r'\d')

        return df

    def _apply_binning(
        self,
        df: pd.DataFrame,
        name: str,
        input_cols: List[str],
        params: Dict[str, Any]
    ) -> pd.DataFrame:
        """Apply binning transformation"""
        col = input_cols[0]
        method = params.get("method", "equal_width")
        bins = params.get("bins", 5)

        if method == "quantile":
            df[name] = pd.qcut(df[col], q=bins, labels=False, duplicates='drop')
        else:  # equal_width
            df[name] = pd.cut(df[col], bins=bins, labels=False)

        return df

    async def _apply_encoding(
        self,
        df: pd.DataFrame,
        name: str,
        input_cols: List[str],
        params: Dict[str, Any]
    ) -> pd.DataFrame:
        """Apply encoding transformation"""
        col = input_cols[0]
        method = params.get("method", "label")

        if method == "one_hot":
            # Create one-hot encoded columns
            dummies = pd.get_dummies(df[col], prefix=col)
            df = pd.concat([df, dummies], axis=1)
        else:  # label encoding
            le = LabelEncoder()
            df[name] = le.fit_transform(df[col].astype(str))

        return df

    def _apply_scaling(
        self,
        df: pd.DataFrame,
        name: str,
        input_cols: List[str],
        params: Dict[str, Any]
    ) -> pd.DataFrame:
        """Apply scaling transformation"""
        method = params.get("method", "standard")

        if method == "standard":
            scaler = StandardScaler()
        elif method == "minmax":
            scaler = MinMaxScaler()
        else:
            scaler = RobustScaler()

        # Scale all input columns
        for col in input_cols:
            if col in df.columns:
                scaled_name = f"{col}_scaled" if name == "standard_scaling" or name == "minmax_scaling" else name
                df[scaled_name] = scaler.fit_transform(df[[col]])

        return df

    def _apply_generic(
        self,
        df: pd.DataFrame,
        name: str,
        input_cols: List[str],
        params: Dict[str, Any]
    ) -> pd.DataFrame:
        """Apply generic transformation based on formula (limited support)"""
        # This is a simplified implementation
        # In production, you might use a safe expression evaluator
        if len(input_cols) == 1:
            col = input_cols[0]
            # Simple copy with optional modification
            df[name] = df[col].copy()
        elif len(input_cols) == 2:
            col1, col2 = input_cols[0], input_cols[1]
            # Default to multiplication for two columns
            df[name] = df[col1] * df[col2]

        return df

    async def apply_stored_feature(
        self,
        df: pd.DataFrame,
        feature: 'StoredFeature'
    ) -> pd.DataFrame:
        """
        Apply a stored feature definition to a dataframe.

        SECURITY (GH-132): The definition is parsed as a serialized
        expression tree and evaluated by the whitelist-based
        ExpressionEvaluator. No eval() or exec() — user-provided
        definitions cannot access the file system, network, modules,
        or system commands.

        Args:
            df: Input dataframe
            feature: StoredFeature instance from feature store

        Returns:
            New DataFrame with the feature column added (input is not mutated)

        Raises:
            UnsafeFeatureDefinitionError: If the definition is not a valid
                serialized expression tree
            ValidationError: If the expression cannot be evaluated on the
                dataframe (e.g., missing columns)
        """
        expression_tree = parse_feature_definition(feature.definition_code)

        evaluator = ExpressionEvaluator()
        try:
            series, warnings = evaluator.evaluate(
                expression_tree, df, feature.output_column_name
            )
        except ExpressionError as e:
            logger.error(
                f"Error applying stored feature {feature.feature_id}: {e.message}"
            )
            raise ValidationError(
                message=f"Failed to apply feature: {e.message}",
                details={"feature_id": feature.feature_id, "node_id": e.node_id},
            )

        for warning in warnings:
            logger.warning(
                f"Stored feature {feature.feature_id} warning: {warning}"
            )

        result_df = df.copy()
        result_df[feature.output_column_name] = series

        logger.info(
            f"Applied stored feature {feature.feature_id} - "
            f"created column: {feature.output_column_name}"
        )

        return result_df