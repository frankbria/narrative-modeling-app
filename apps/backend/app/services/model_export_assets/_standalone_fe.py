"""Standalone preprocessing for exported models (issue #632).

This file ships **verbatim** inside the model-export ZIP as ``feature_engineer.py``
and runs in the delivered container, which does NOT have the platform's ``app``
package on ``sys.path``. So it must import nothing from ``app`` — only pandas and
the stock scikit-learn objects that were pickled into the state dict.

The platform's real ``FeatureEngineer`` (``app.services.model_training.feature_engineer``)
pickles its own class, whose module imports ``app.models.feature`` etc.; unpickling
that in the container raised ``ModuleNotFoundError`` and the API never started. The
export ships a plain **state dict** instead — only fitted stock sklearn transformers
plus lists/strings — and this class reconstructs the transform from it.

``transform`` here mirrors ``FeatureEngineer.transform`` step-for-step (same order,
same transformer keys, same encoder gates) so the container's predictions match
the platform's, and it is **synchronous** (the platform's is async only because its
sibling steps are).
"""

import pickle

import pandas as pd


class StandaloneFeatureEngineer:
    """Applies a fitted FeatureEngineer's transformers without the platform code."""

    def __init__(self, state: dict):
        self.transformers = state.get("transformers", {})
        self.numeric_features = state.get("numeric_features", [])
        self.categorical_features = state.get("categorical_features", [])
        self.feature_names = state.get("feature_names", [])

    @staticmethod
    def _coerce_booleans(df: pd.DataFrame) -> pd.DataFrame:
        for col in list(df.select_dtypes(include=["bool"]).columns):
            df[col] = df[col].astype(str)
        return df

    @staticmethod
    def _label_keys(s: pd.Series) -> pd.Series:
        # Same keying as the platform's fit: integral floats drop their ".0".
        return s.map(lambda v: str(int(v)) if isinstance(v, float) and v.is_integer() else str(v))

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        X_transformed = self._coerce_booleans(X.copy())
        X_transformed = self._apply_imputers(X_transformed)
        X_transformed = self._apply_encoders(X_transformed)
        if "scaler" in self.transformers:
            X_transformed[self.numeric_features] = self.transformers["scaler"].transform(
                X_transformed[self.numeric_features]
            )
        X_transformed = self._apply_interactions(X_transformed)
        if "selector" in self.transformers:
            available = [f for f in self.transformers["selected_features"] if f in X_transformed.columns]
            X_transformed = X_transformed[available]
        return X_transformed

    def _apply_imputers(self, X: pd.DataFrame) -> pd.DataFrame:
        t = self.transformers
        if "imputer_numeric" in t:
            X[self.numeric_features] = t["imputer_numeric"].transform(X[self.numeric_features])
        if "imputer_categorical" in t:
            X[self.categorical_features] = t["imputer_categorical"].transform(X[self.categorical_features])
        return X

    def _apply_encoders(self, X: pd.DataFrame) -> pd.DataFrame:
        # Same gate as the platform: one-hot fits "encoder", label fits
        # "label_encoders"; an unseen label category maps to -1 (#697).
        t = self.transformers
        if "encoder" in t:
            encoded_df = pd.DataFrame(
                t["encoder"].transform(X[self.categorical_features]),
                columns=t["encoded_columns"],
                index=X.index,
            )
            return pd.concat([X.drop(columns=self.categorical_features), encoded_df], axis=1)
        for col, le in t.get("label_encoders", {}).items():
            codes = {label: code for code, label in enumerate(le.classes_)}
            X[col] = self._label_keys(X[col]).map(codes).fillna(-1).astype(int)
        return X

    def _apply_interactions(self, X: pd.DataFrame) -> pd.DataFrame:
        for feat in self.transformers.get("interaction_features", []):
            value = self._interaction_value(X, feat)
            if value is not None:
                X[feat] = value
        return X

    @staticmethod
    def _interaction_value(X: pd.DataFrame, feat: str):
        sep = "_x_" if "_x_" in feat else "_div_"
        col1, _, col2 = feat.partition(sep)
        if col1 not in X.columns or col2 not in X.columns:
            return None
        return X[col1] * X[col2] if sep == "_x_" else X[col1] / (X[col2] + 1e-8)


def load_feature_engineer(path: str):
    """Load the shipped preprocessing state; return None when the model has none."""
    with open(path, "rb") as f:
        state = pickle.load(f)
    if not state:
        return None
    return StandaloneFeatureEngineer(state)
