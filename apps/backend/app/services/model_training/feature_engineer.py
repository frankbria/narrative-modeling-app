"""
Feature engineering for AutoML
"""

import json
import logging
import re
import warnings
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd
from pydantic import ValidationError as PydanticValidationError
from sklearn.feature_selection import SelectKBest, f_classif, f_regression
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import (
    LabelEncoder,
    MinMaxScaler,
    OneHotEncoder,
    RobustScaler,
    StandardScaler,
)

from app.models.feature import (
    ExpressionNode,
    FunctionType,
    NodeType,
    OperationType,
)
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

# A text column whose values are this unique per row is an identifier (#806).
IDENTIFIER_UNIQUE_RATIO = 0.95
# A unique, monotone integer column is only a row counter if it is also NAMED
# like one: a file sorted by a real integer feature (sqft) is unique and monotone too.
_IDENTIFIER_NAME = re.compile(
    r"^(unnamed: \d+|(.*[\s_.-])?(id|uuid|guid|key|pk|index|idx|row|rownum|row_?number|number|num|no))$",
    re.IGNORECASE,
)


# A date column is left out of the features too (#840): read from CSV it is text,
# and one-hot encoding it makes a feature per distinct date. Text counts as a date
# when this share of a sample is WRITTEN as a full date and parses as one. Parsing
# alone is not enough: dateutil also reads "Jan", "Mon" and "1/2" as dates, and
# those are categories.
DATE_PARSE_RATIO = 0.95
_DATE_SAMPLE = 1000
_MONTH_NAME = r"[A-Za-z]{3,9}\.?"
_DATE_SHAPE = re.compile(
    r"^\s*(?:[A-Za-z]{3,9},? )?(?:"  # an optional weekday: "Wed, 31 Jan 2024"
    r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}"  # 2024-01-31
    r"|\d{1,2}[-/]\d{1,2}[-/](?:\d{4}|\d{2})"  # 01/31/2024, 1/2/24
    r"|\d{1,2}\.\d{1,2}\.\d{4}"  # 31.01.2024
    rf"|\d{{1,2}}[ -]{_MONTH_NAME}[ ,-]+\d{{2,4}}"  # 31 Jan 2024, 31-Jan-24
    rf"|{_MONTH_NAME} \d{{1,2}},? \d{{4}}"  # Jan 31, 2024
    r")(?:[T ]\d{1,2}:\d{2}.*)?\s*$"  # an optional time
)


def _is_text(s: pd.Series) -> bool:
    return s.dtype == object or isinstance(s.dtype, pd.CategoricalDtype) or pd.api.types.is_string_dtype(s)


def _is_text_identifier(s: pd.Series) -> bool:
    """Text that is (nearly) unique over its filled cells; blanks don't make an ID
    less unique."""
    filled = s.notna().sum()
    return _is_text(s) and bool(filled) and s.nunique() / filled >= IDENTIFIER_UNIQUE_RATIO


def _is_date_column(s: pd.Series) -> bool:
    """A datetime column (Parquet keeps the type), or text written as full dates."""
    if pd.api.types.is_datetime64_any_dtype(s):
        return True
    if not _is_text(s):
        return False
    filled = s.dropna()
    # Drawn from the whole column: a sorted file's first rows can be unlike the rest.
    sample = filled.sample(n=min(len(filled), _DATE_SAMPLE), random_state=0).astype(str)
    return bool(len(sample)) and _date_share(sample) >= DATE_PARSE_RATIO


def _date_share(sample: pd.Series) -> float:
    """The share of the values that are shaped like a full date and parse as one."""
    shaped = sample[sample.str.match(_DATE_SHAPE)]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # "mixed" parses each value on its own
        parsed = pd.to_datetime(shaped, errors="coerce", format="mixed", utc=True)
    return float(parsed.notna().sum()) / len(sample)


def _is_row_counter(name: Any, s: pd.Series) -> bool:
    """An ID-named integer column, unique and monotone in the ORIGINAL row order:
    the index is sorted first because the training split shuffles rows."""
    return (
        pd.api.types.is_numeric_dtype(s)
        and _IDENTIFIER_NAME.match(re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", str(name))) is not None
        and s.notna().all()
        and s.is_unique
        and _monotone_integers(s.sort_index())
    )


def _monotone_integers(s: pd.Series) -> bool:
    return bool((s % 1 == 0).all()) and (s.is_monotonic_increasing or s.is_monotonic_decreasing)


def parse_feature_definition(definition_code: str | None) -> ExpressionNode:
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
        # RecursionError: pathologically deep JSON blows the parser's stack
        # before any tree validation can run — treat it as an invalid
        # definition (422), not a server error (500).
        if not isinstance(definition_code, str):
            raise TypeError("Feature definition must be a JSON string")
        data = json.loads(definition_code)
    except (json.JSONDecodeError, TypeError, RecursionError) as e:
        raise UnsafeFeatureDefinitionError(
            message=(
                "Feature definition must be a JSON-serialized expression tree. "
                "Raw code is not supported — recreate the feature with the "
                "Visual Feature Builder."
            )
        ) from e

    if not isinstance(data, dict):
        raise UnsafeFeatureDefinitionError(
            message="Feature definition must be a JSON object describing an expression tree"
        )

    try:
        tree = ExpressionNode.model_validate(data)
    except PydanticValidationError as e:
        raise UnsafeFeatureDefinitionError(
            message="Feature definition is not a valid expression tree",
            details={"errors": [err["msg"] for err in e.errors()]},
        ) from e
    except RecursionError as e:
        # Belt-and-braces: pydantic-core's internal recursion limit (~254)
        # raises ValidationError long before the stack could overflow, so
        # this branch is unreachable today — but correctness here must not
        # depend on pydantic internals.
        raise UnsafeFeatureDefinitionError(
            message="Feature definition is not a valid expression tree",
            details={"errors": ["expression tree is too deeply nested"]},
        ) from e

    _validate_tree_whitelist(tree)
    return tree


# NOTE: these whitelists must stay in sync with what ExpressionEvaluator
# actually implements — a new OperationType/FunctionType variant that the
# evaluator doesn't handle would pass save-time validation here but fail
# at apply time.
_ALLOWED_OPERATIONS = frozenset(op.value for op in OperationType)
_ALLOWED_FUNCTIONS = frozenset(fn.value for fn in FunctionType)

# Far deeper than any legitimate feature expression, far shallower than the
# Python recursion limit — crafted deep trees get a clean 422, never a 500.
_MAX_TREE_DEPTH = 50


def _validate_tree_whitelist(node: ExpressionNode, _depth: int = 0) -> None:
    """
    Reject expression trees referencing operations/functions outside the
    whitelist, so invalid definitions fail at save time rather than at apply
    time (GH-132 review finding). Also bounds tree depth so recursive
    traversal (here and in ExpressionEvaluator) can never overflow the stack.
    """
    if _depth > _MAX_TREE_DEPTH:
        raise UnsafeFeatureDefinitionError(
            message=(
                f"Expression tree exceeds maximum allowed depth ({_MAX_TREE_DEPTH})"
            ),
            details={"node_id": node.node_id},
        )
    if node.node_type == NodeType.OPERATION:
        if str(node.value).lower() not in _ALLOWED_OPERATIONS:
            raise UnsafeFeatureDefinitionError(
                message=f"Operation '{node.value}' is not allowed",
                details={"node_id": node.node_id},
            )
    elif node.node_type == NodeType.FUNCTION:
        if str(node.value).lower() not in _ALLOWED_FUNCTIONS:
            raise UnsafeFeatureDefinitionError(
                message=f"Function '{node.value}' is not allowed",
                details={"node_id": node.node_id},
            )
    for child in node.children:
        _validate_tree_whitelist(child, _depth + 1)


@dataclass
class FeatureEngineeringConfig:
    """Configuration for feature engineering"""
    handle_missing: bool = True
    scale_features: bool = True
    encode_categorical: bool = True
    create_interactions: bool = False
    select_features: bool = True
    max_features: int | None = None
    scaling_method: str = "standard"  # standard, minmax, robust
    encoding_method: str = "onehot"  # onehot, label
    missing_strategy: str = "mean"  # mean, median, most_frequent, constant
    keep_columns: list[str] = field(default_factory=list)  # never excluded as identifiers
    exclude_columns: list[str] = field(default_factory=list)  # left out by the caller's choice (#969)


@dataclass
class FeatureEngineeringResult:
    """Result of feature engineering"""
    X_transformed: pd.DataFrame
    feature_names: list[str]
    transformers: dict[str, Any]
    feature_importance: dict[str, float] | None
    metadata: dict[str, Any]


class FeatureEngineer:
    """Automated feature engineering for ML models"""
    
    def __init__(self, config: FeatureEngineeringConfig | None = None):
        self.config = config or FeatureEngineeringConfig()
        self.transformers: dict[str, Any] = {}
        self.feature_names: list[str] = []
        self.numeric_features: list[str] = []
        self.categorical_features: list[str] = []
        self.excluded_features: list[str] = []
        self.excluded_dates: list[str] = []
        self.excluded_empty: list[str] = []
        self.excluded_by_choice: list[str] = []

    async def fit_transform(
        self,
        X: pd.DataFrame,
        y: pd.Series | None = None,
        problem_type: str | None = None
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
        X_transformed = self._exclude_unlearnable(self._coerce_booleans(X.copy()))
        X_transformed = self._datetimes_as_text(X_transformed)
        self._identify_feature_types(X_transformed)
        X_transformed = await self._fit_categorical_steps(X_transformed)
        X_transformed = await self._fit_numeric_steps(X_transformed)
        X_transformed, feature_importance = await self._fit_selection(X_transformed, y, problem_type)

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
                # Identifiers only: train_model_task persists this key as
                # ``excluded_identifier_columns``. Dates are reported apart (#840).
                "excluded_features": self._excluded_identifiers(),
                "excluded_date_columns": self.excluded_dates,
                "excluded_empty_columns": self.excluded_empty,
                "excluded_user_columns": self.excluded_by_choice,
                "final_feature_count": len(self.feature_names)
            }
        )
    
    def _exclude_unlearnable(self, X: pd.DataFrame) -> pd.DataFrame:
        """Record and drop the columns left out of the features: the caller's own
        choice (#969), per-row identifiers (#806), dates (#840) and columns with no
        value at all (#911). ``excluded_features`` holds all four, in column order,
        and is what ``transform`` and the export drop."""
        self._find_unlearnable(X)
        if not self.excluded_features:
            return X
        if len(self.excluded_features) == X.shape[1]:
            raise ValueError(self._nothing_left())
        logger.info("Excluding columns from features: %s", self.excluded_features)
        return X.drop(columns=self.excluded_features)

    def _nothing_left(self) -> str:
        if self.excluded_by_choice:
            return (
                "Every feature column was left out or cannot be learned from, "
                "so there is nothing to learn from"
            )
        return (
            "Every feature column is a per-row identifier, a date or empty, "
            "so there is nothing to learn from"
        )

    def _find_unlearnable(self, X: pd.DataFrame) -> None:
        keep = self.config.keep_columns
        chosen = set(self.config.exclude_columns)
        self.excluded_by_choice = [col for col in X.columns if col in chosen]
        # A column left out by choice is reported as that and as nothing else, and
        # stays out even if it is also named in ``keep``: keeping only overrides a rule.
        rest = X.drop(columns=self.excluded_by_choice)
        # Not subject to ``keep``: there is no value to encode, and an imputer drops
        # a column it has nothing to learn a fill from. An empty date is "empty".
        self.excluded_empty = self._empty_columns(rest)
        self.excluded_dates = self._date_columns(rest.drop(columns=self.excluded_empty), keep)
        left_out = {
            *self.excluded_by_choice,
            *self.excluded_empty,
            *self.excluded_dates,
            *self._identifier_columns(rest, keep),
        }
        self.excluded_features = [col for col in X.columns if col in left_out]

    @staticmethod
    def _empty_columns(X: pd.DataFrame) -> list[str]:
        """Columns with no value in any row the engineer is fitted on. pandas reads
        an unused CSV column as float64, all NaN."""
        return [col for col in X.columns if not X[col].notna().any()]

    @staticmethod
    def _datetimes_as_text(X: pd.DataFrame) -> pd.DataFrame:
        """A datetime column still in the frame was kept by the caller
        (``keep_columns``). It is in neither feature list as it is and no estimator
        takes it, so it becomes the text a CSV would have held. Each value is written
        on its own (a date, with its time when it has one), so the fit, the engine's
        test split and a served frame all key it alike. A blank stays a blank."""
        for col in X.columns[[pd.api.types.is_datetime64_any_dtype(t) for t in X.dtypes]]:
            X[col] = X[col].dt.strftime("%Y-%m-%d %H:%M:%S").str.removesuffix(" 00:00:00")
        return X

    def _excluded_identifiers(self) -> list[str]:
        # getattr: engineers pickled before #806 / #840 / #911 / #969 lack one list or another.
        other = {
            *getattr(self, "excluded_dates", []),
            *getattr(self, "excluded_empty", []),
            *getattr(self, "excluded_by_choice", []),
        }
        return [col for col in getattr(self, "excluded_features", []) if col not in other]

    def exclusion_notes(self) -> list[str]:
        """One sentence for the training log per kind of column left out of the features."""
        kinds = (
            ("per-row identifier", self._excluded_identifiers()),
            ("date", getattr(self, "excluded_dates", [])),
            ("empty", getattr(self, "excluded_empty", [])),
        )
        chosen = getattr(self, "excluded_by_choice", [])
        by_choice = [f"Left out of the features by choice: {', '.join(chosen)}"] if chosen else []
        return by_choice + [
            f"Excluded {kind} columns from the features: {', '.join(columns)}"
            for kind, columns in kinds
            if columns
        ]

    async def _fit_categorical_steps(self, X: pd.DataFrame) -> pd.DataFrame:
        """Impute missing values, then encode the categoricals."""
        if self.config.handle_missing:
            X = await self._handle_missing_values(X)
        if self.config.encode_categorical and self.categorical_features:
            X = await self._encode_categorical_features(X)
        return X

    async def _fit_numeric_steps(self, X: pd.DataFrame) -> pd.DataFrame:
        """Scale the numerics, then build interactions."""
        if self.config.scale_features and self.numeric_features:
            X = await self._scale_numeric_features(X)
        if self.config.create_interactions:
            X = await self._create_interaction_features(X)
        return X

    async def _fit_selection(
        self, X: pd.DataFrame, y: pd.Series | None, problem_type: str | None
    ) -> tuple[pd.DataFrame, dict[str, float] | None]:
        """Select the best features when asked and a target is given."""
        if self.config.select_features and y is not None:
            return await self._select_features(X, y, problem_type)
        return X, None

    async def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """Transform new data using fitted transformers, in fit's step order."""
        return self._transform_prepared(self._prepare(X))

    def served(self, X: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, str]]]:
        """What a serving path needs from one request's records: the transformed frame
        and the input warnings, from one ``_prepare`` (#909). Synchronous so a caller
        can run it in a worker thread; it reads the fitted state and writes none."""
        prepared = self._prepare(X)
        # Before the transform, which fills the prepared frame's blanks in place.
        warnings = self._warnings_of(prepared)
        return self._transform_prepared(prepared), warnings

    def _transform_prepared(self, X: pd.DataFrame) -> pd.DataFrame:
        X_transformed = self._apply_imputers(X)
        X_transformed = self._apply_encoders(X_transformed)
        if "scaler" in self.transformers:
            X_transformed[self.numeric_features] = self.transformers["scaler"].transform(
                X_transformed[self.numeric_features]
            )
        X_transformed = self._apply_interactions(X_transformed)
        if "selector" in self.transformers:
            # Only keep columns that exist in the transformed data
            available_features = [f for f in self.transformers["selected_features"] if f in X_transformed.columns]
            X_transformed = X_transformed[available_features]
        return X_transformed

    def _prepare(self, X: pd.DataFrame) -> pd.DataFrame:
        """A copy of the frame as ``transform`` and ``input_warnings`` both read it:
        booleans as text, identifier columns dropped, and a JSON null (``None``) in a
        categorical column turned into the NaN a blank cell is. The imputers fill
        NaN only, so a null used to skip the fill a blank got at training (#838)."""
        X = self._coerce_booleans(X.copy())
        # getattr: engineers pickled before #806 have no exclusion list.
        X = self._datetimes_as_text(X.drop(columns=getattr(self, "excluded_features", []), errors="ignore"))
        for col in self.categorical_features:
            if col in X.columns:
                X[col] = X[col].where(X[col].notna(), np.nan)
        return X

    def input_warnings(self, X: pd.DataFrame) -> list[dict[str, str]]:
        """Per row, the inputs whose value the model did not learn from (#838).

        ``"missing"`` is a null, served as the training fill (the mean, or the most
        frequent value). ``"unseen"`` is a category absent from training, which
        one-hot serves as an all-zeros block and label encoding as the most frequent
        value. A clean row is an empty dict. Only the columns supplied are read, and
        nothing is stored on the engineer, which is shared across requests."""
        return self._warnings_of(self._prepare(X))

    def _warnings_of(self, X: pd.DataFrame) -> list[dict[str, str]]:
        report: list[dict[str, str]] = [{} for _ in range(len(X))]
        for col in [c for c in self.numeric_features + self.categorical_features if c in X.columns]:
            missing = X[col].isna().to_numpy()
            self._mark(report, col, missing, "missing")
            self._mark(report, col, self._unseen(X[col], col) & ~missing, "unseen")
        return report

    @staticmethod
    def _mark(report: list[dict[str, str]], col: str, rows: np.ndarray, reason: str) -> None:
        for i in np.flatnonzero(rows):
            report[i][col] = reason

    def _unseen(self, values: pd.Series, col: str) -> np.ndarray:
        """Which values have no fitted category; none in a column that is not encoded."""
        if "encoder" in self.transformers and col in self.categorical_features:
            categories = self.transformers["encoder"].categories_[self.categorical_features.index(col)]
            return self._hits(values, categories) < 0
        encoder = self.transformers.get("label_encoders", {}).get(col)
        if encoder is None:
            return np.zeros(len(values), dtype=bool)
        return ~self._label_keys(values).isin(encoder.classes_).to_numpy()

    def _apply_imputers(self, X: pd.DataFrame) -> pd.DataFrame:
        if "imputer_numeric" in self.transformers:
            X[self.numeric_features] = self.transformers["imputer_numeric"].transform(X[self.numeric_features])
        if "imputer_categorical" in self.transformers:
            X[self.categorical_features] = self.transformers["imputer_categorical"].transform(
                X[self.categorical_features]
            )
        return X

    def _apply_encoders(self, X: pd.DataFrame) -> pd.DataFrame:
        """Gate on the key each method actually fitted: one-hot sets "encoder",
        label sets "label_encoders" (#697). A label category unseen at fit time
        is served like a missing one (see ``_unseen_label_code``) instead of raising."""
        if "encoder" in self.transformers:
            return pd.concat([X.drop(columns=self.categorical_features), self._one_hot(X)], axis=1)
        for col, le in self.transformers.get("label_encoders", {}).items():
            codes = {label: code for code, label in enumerate(le.classes_)}
            unseen = self._unseen_label_code(col, codes)
            X[col] = self._label_keys(X[col]).map(codes).fillna(unseen).astype(int)
        return X

    _NUMERIC_CATEGORIES = ("integer", "floating", "mixed-integer-float")

    def _one_hot(self, X: pd.DataFrame) -> pd.DataFrame:
        """The one-hot block, matched on ``_match_keys`` (#906).

        The fitted encoder matches by raw value and type, so the form's ``"1"`` for a
        category fitted as the int ``1`` (or ``true`` for one fitted as ``"True"``)
        was an all-zeros block. For a value the encoder would have matched the output
        is the same; a value with no category is still all zeros."""
        blocks = []
        for col, categories in zip(self.categorical_features, self.transformers["encoder"].categories_):
            hit = self._hits(X[col], categories)
            block = np.zeros((len(X), len(categories)))
            block[hit >= 0, hit[hit >= 0]] = 1.0
            blocks.append(block)
        return pd.DataFrame(np.hstack(blocks), columns=self.transformers["encoded_columns"], index=X.index)

    def _hits(self, values: pd.Series, categories: Any) -> np.ndarray:
        """The position of each value's fitted category, -1 where it has none."""
        # By value: the imputer hands fit an object block, so the dtype says nothing.
        numeric = pd.api.types.infer_dtype(categories, skipna=True) in self._NUMERIC_CATEGORIES
        fitted = self._match_keys(pd.Series(categories, dtype=object), numeric)
        position = {key: i for i, key in enumerate(fitted)}
        return np.array([position.get(key, -1) for key in self._match_keys(values, numeric)], dtype=int)

    @staticmethod
    def _match_keys(values: pd.Series, numeric: bool) -> list[tuple[bool, str]]:
        """What one-hot matches a value on: its label key, as label encoding does.

        Two additions. A missing value is kept apart from the text that spells its
        key (``"nan"``), since without an imputer both can be categories of one
        column. And in a column fitted on numbers, text that reads as a number is
        that number, so ``"1.0"`` and ``"01"`` select the category ``1``."""
        if numeric:
            as_number = pd.to_numeric(values, errors="coerce")
            values = values.where(as_number.isna(), as_number)
        return list(zip(values.isna(), FeatureEngineer._label_keys(values)))

    def _unseen_label_code(self, col: str, codes: dict[str, int]) -> int:
        """Code for a category unseen at fit: the column's most-frequent training
        value, which is what a blank cell is already imputed to — so an unseen
        value is served like a missing one rather than as an out-of-range code a
        linear model would extrapolate from (#697). -1 only when no categorical
        imputer was fitted (``handle_missing=False``)."""
        stats = getattr(self.transformers.get("imputer_categorical"), "statistics_", None)
        if stats is None or col not in self.categorical_features:
            return -1
        mode = stats[self.categorical_features.index(col)]
        return codes.get(self._label_keys(pd.Series([mode])).iloc[0], -1)

    def _apply_interactions(self, X: pd.DataFrame) -> pd.DataFrame:
        """Recreate the interaction features fit created, where both inputs exist."""
        for feat in self.transformers.get("interaction_features", []):
            value = self._interaction_value(X, feat)
            if value is not None:
                X[feat] = value
        return X

    @staticmethod
    def _interaction_value(X: pd.DataFrame, feat: str) -> pd.Series | None:
        sep = "_x_" if "_x_" in feat else "_div_"
        col1, _, col2 = feat.partition(sep)
        if col1 not in X.columns or col2 not in X.columns:
            return None
        return X[col1] * X[col2] if sep == "_x_" else X[col1] / (X[col2] + 1e-8)

    @staticmethod
    def _coerce_booleans(df: pd.DataFrame) -> pd.DataFrame:
        """Cast boolean columns to strings so they are handled as ordinary
        categoricals (issue #82).

        pandas parses ``true``/``false`` CSV values to ``bool`` dtype, which is
        neither numeric nor object — such columns would otherwise be dropped
        from both feature lists, silently passing through the training matrix
        while the prediction form/contract never collects them. Coercing to
        ``str`` at both fit and transform time keeps the encoder's categories
        ("True"/"False") consistent with what the form submits.
        """
        bool_cols = list(df.select_dtypes(include=["bool"]).columns)
        for col in bool_cols:
            df[col] = df[col].astype(str)
        return df

    @staticmethod
    def _label_keys(s: pd.Series) -> pd.Series:
        """The string a label encoder keys a value on, at fit and at serving.

        Integral floats drop their ``.0``: a column fitted as floats (NaNs force
        float64) must still match the same value sent as an int (#697).
        """
        return s.map(lambda v: str(int(v)) if isinstance(v, (float, np.floating)) and float(v).is_integer() else str(v))

    @staticmethod
    def _identifier_columns(df: pd.DataFrame, keep: list[str]) -> list[str]:
        """Per-row identifiers, which carry no signal and one-hot into a feature
        per row (#806). ``keep`` is the caller's override."""
        return [
            col
            for col in df.columns
            if col not in keep and (_is_text_identifier(df[col]) or _is_row_counter(col, df[col]))
        ]

    @staticmethod
    def _date_columns(df: pd.DataFrame, keep: list[str]) -> list[str]:
        """Date columns, which are not one-hot encoded (#840). ``keep`` is the
        caller's override: a kept date is encoded as text (``_datetimes_as_text``
        makes text of a datetime column first)."""
        return [col for col in df.columns if col not in keep and _is_date_column(df[col])]

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
        """Fit the imputers and fill the blanks.

        No column here is empty: ``_exclude_unlearnable`` left those out (#911). An
        imputer drops a column it has no value to learn a fill from, and this step
        used to answer the resulting shape mismatch by dropping every categorical
        column, which failed the run or, worse, trained without them."""
        if self.numeric_features:
            numeric_imputer = SimpleImputer(strategy=self.config.missing_strategy)
            df[self.numeric_features] = numeric_imputer.fit_transform(df[self.numeric_features])
            self.transformers["imputer_numeric"] = numeric_imputer
        if self.categorical_features:
            categorical_imputer = SimpleImputer(strategy="most_frequent")
            df[self.categorical_features] = categorical_imputer.fit_transform(df[self.categorical_features])
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
                df[col] = le.fit_transform(self._label_keys(df[col]))
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
        problem_type: str | None = None
    ) -> tuple[pd.DataFrame, dict[str, float]]:
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
    ) -> tuple[pd.DataFrame, dict[str, Any]]:
        """
        Apply a single feature suggestion to a dataframe.

        Args:
            df: Input dataframe
            suggestion: FeatureSuggestion object with feature details

        Returns:
            Tuple of (transformed dataframe, metadata dict)
        """
        df = df.copy()
        metadata: dict[str, Any] = {
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

    def _apply_polynomial(
        self,
        df: pd.DataFrame,
        name: str,
        input_cols: list[str],
        params: dict[str, Any]
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
        input_cols: list[str],
        params: dict[str, Any]
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
        input_cols: list[str],
        params: dict[str, Any]
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
        input_cols: list[str],
        params: dict[str, Any]
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
        input_cols: list[str],
        params: dict[str, Any]
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
        input_cols: list[str],
        params: dict[str, Any]
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
        input_cols: list[str],
        params: dict[str, Any]
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
        input_cols: list[str],
        params: dict[str, Any]
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
        input_cols: list[str],
        params: dict[str, Any]
    ) -> pd.DataFrame:
        """Apply generic transformation based on formula (limited support)"""
        # Simplified implementation; complex formulas belong in expression
        # trees evaluated by ExpressionEvaluator (see apply_stored_feature)
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
            ) from e

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
