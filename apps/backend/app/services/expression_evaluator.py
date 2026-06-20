"""
Expression Evaluator for Visual Feature Builder.

This module provides safe evaluation of expression trees using pandas operations.
NO eval() or exec() is used - only explicit pandas/numpy function mappings.
"""

import logging
from typing import Any

import numpy as np
import pandas as pd

from app.models.feature import (
    ExpressionNode,
    NodeType,
)

logger = logging.getLogger(__name__)


class ExpressionError(Exception):
    """Base exception for expression evaluation errors."""

    def __init__(self, message: str, node_id: str | None = None):
        self.message = message
        self.node_id = node_id
        super().__init__(message)


class TypeMismatchError(ExpressionError):
    """Raised when types are incompatible for an operation."""
    pass


class ColumnNotFoundError(ExpressionError):
    """Raised when a referenced column doesn't exist."""
    pass


class DivisionByZeroWarning(ExpressionError):
    """Warning for potential division by zero."""
    pass


class ExpressionEvaluator:
    """
    Safe expression evaluator using pandas operations.

    This class evaluates expression trees built by the Visual Feature Builder
    using only explicit pandas/numpy function mappings. No eval() or exec().
    """

    # Binary operation mappings
    BINARY_OPERATIONS: dict[str, str] = {
        "add": "add",
        "subtract": "sub",
        "multiply": "mul",
        "divide": "truediv",
        "modulo": "mod",
        "power": "pow",
    }

    # Comparison operation mappings
    COMPARISON_OPERATIONS: dict[str, str] = {
        "equal": "eq",
        "not_equal": "ne",
        "greater_than": "gt",
        "less_than": "lt",
        "greater_than_or_equal": "ge",
        "less_than_or_equal": "le",
    }

    # Mathematical function mappings
    MATH_FUNCTIONS: dict[str, Any] = {
        "abs": np.abs,
        "log": np.log,
        "log10": np.log10,
        "sqrt": np.sqrt,
        "exp": np.exp,
        "sin": np.sin,
        "cos": np.cos,
        "tan": np.tan,
        "ceil": np.ceil,
        "floor": np.floor,
    }

    # Statistical function mappings (require different handling)
    STAT_FUNCTIONS: dict[str, str] = {
        "mean": "mean",
        "median": "median",
        "std": "std",
        "min": "min",
        "max": "max",
        "sum": "sum",
    }

    def __init__(self):
        """Initialize the expression evaluator."""
        self.warnings: list[str] = []

    def evaluate(
        self,
        expression_tree: ExpressionNode,
        dataframe: pd.DataFrame,
        feature_name: str = "computed_feature"
    ) -> tuple[pd.Series, list[str]]:
        """
        Evaluate an expression tree on a dataframe.

        Args:
            expression_tree: Root node of the expression tree
            dataframe: Pandas DataFrame with the data
            feature_name: Name for the resulting series

        Returns:
            Tuple of (computed Series, list of warnings)

        Raises:
            ExpressionError: If evaluation fails
        """
        self.warnings = []

        # Validate columns exist
        input_columns = expression_tree.get_input_columns()
        missing_cols = [col for col in input_columns if col not in dataframe.columns]
        if missing_cols:
            raise ColumnNotFoundError(
                f"Columns not found in dataset: {missing_cols}",
                node_id=expression_tree.node_id
            )

        # Evaluate the expression
        result = self._evaluate_node(expression_tree, dataframe)

        # Ensure result is a Series
        if isinstance(result, (int, float, bool, str)):
            result = pd.Series([result] * len(dataframe), index=dataframe.index)

        result.name = feature_name
        return result, self.warnings

    def _evaluate_node(
        self,
        node: ExpressionNode,
        df: pd.DataFrame
    ) -> pd.Series | Any:
        """
        Recursively evaluate a single node.

        Args:
            node: The expression node to evaluate
            df: The dataframe context

        Returns:
            Series or scalar result
        """
        if node.node_type == NodeType.COLUMN:
            return self._eval_column(node, df)
        elif node.node_type == NodeType.CONSTANT:
            return self._eval_constant(node, df)
        elif node.node_type == NodeType.OPERATION:
            return self._eval_operation(node, df)
        elif node.node_type == NodeType.FUNCTION:
            return self._eval_function(node, df)
        elif node.node_type == NodeType.CONDITIONAL:
            return self._eval_conditional(node, df)
        else:
            raise ExpressionError(
                f"Unknown node type: {node.node_type}",
                node_id=node.node_id
            )

    def _eval_column(self, node: ExpressionNode, df: pd.DataFrame) -> pd.Series:
        """Evaluate a column reference node."""
        column_name = str(node.value)
        if column_name not in df.columns:
            raise ColumnNotFoundError(
                f"Column '{column_name}' not found",
                node_id=node.node_id
            )
        return df[column_name].copy()

    def _eval_constant(
        self,
        node: ExpressionNode,
        df: pd.DataFrame
    ) -> pd.Series | Any:
        """Evaluate a constant value node."""
        # Return scalar - will be broadcast by pandas operations
        return node.value

    def _eval_operation(self, node: ExpressionNode, df: pd.DataFrame) -> pd.Series:
        """Evaluate an operation node."""
        op_type = str(node.value).lower()

        # Handle logical NOT (unary)
        if op_type == "not":
            if len(node.children) != 1:
                raise ExpressionError(
                    "NOT operation requires exactly 1 child",
                    node_id=node.node_id
                )
            child_result = self._evaluate_node(node.children[0], df)
            return self._to_series(~child_result.astype(bool), df)

        # Handle logical AND/OR
        if op_type == "and":
            return self._eval_logical_and(node, df)
        if op_type == "or":
            return self._eval_logical_or(node, df)

        # Binary operations require at least 2 children
        if len(node.children) < 2:
            raise ExpressionError(
                f"Operation '{op_type}' requires at least 2 operands",
                node_id=node.node_id
            )

        # Evaluate children
        left = self._evaluate_node(node.children[0], df)
        right = self._evaluate_node(node.children[1], df)

        # Convert to series if needed
        left = self._to_series(left, df)
        right = self._to_series(right, df)

        # Check for division by zero
        if op_type == "divide":
            zero_count = (right == 0).sum()
            if zero_count > 0:
                self.warnings.append(
                    f"Division by zero detected in {zero_count} rows. "
                    "Result will be inf/nan."
                )

        # Arithmetic operations
        if op_type in self.BINARY_OPERATIONS:
            pandas_op = self.BINARY_OPERATIONS[op_type]
            return getattr(left, pandas_op)(right)

        # Comparison operations
        if op_type in self.COMPARISON_OPERATIONS:
            pandas_op = self.COMPARISON_OPERATIONS[op_type]
            return getattr(left, pandas_op)(right)

        raise ExpressionError(
            f"Unknown operation type: {op_type}",
            node_id=node.node_id
        )

    def _eval_logical_and(self, node: ExpressionNode, df: pd.DataFrame) -> pd.Series:
        """
        Evaluate logical AND operation.

        Note: This implementation evaluates all child operands for all rows. There is
        no per-row short-circuit evaluation - all operands are computed before combining.
        For most vectorized use cases this is acceptable, but if per-row short-circuiting
        is needed (e.g., to avoid errors in subsequent operands), a masked evaluation
        approach would be required, which adds significant complexity.
        """
        if len(node.children) < 2:
            raise ExpressionError(
                "AND operation requires at least 2 operands",
                node_id=node.node_id
            )

        result = self._evaluate_node(node.children[0], df)
        result = self._to_series(result, df).astype(bool)

        for child in node.children[1:]:
            child_result = self._evaluate_node(child, df)
            child_result = self._to_series(child_result, df).astype(bool)
            result = result & child_result

        return result

    def _eval_logical_or(self, node: ExpressionNode, df: pd.DataFrame) -> pd.Series:
        """
        Evaluate logical OR operation.

        Note: This implementation evaluates all child operands for all rows. There is
        no per-row short-circuit evaluation - all operands are computed before combining.
        For most vectorized use cases this is acceptable, but if per-row short-circuiting
        is needed (e.g., to avoid errors in subsequent operands), a masked evaluation
        approach would be required, which adds significant complexity.
        """
        if len(node.children) < 2:
            raise ExpressionError(
                "OR operation requires at least 2 operands",
                node_id=node.node_id
            )

        result = self._evaluate_node(node.children[0], df)
        result = self._to_series(result, df).astype(bool)

        for child in node.children[1:]:
            child_result = self._evaluate_node(child, df)
            child_result = self._to_series(child_result, df).astype(bool)
            result = result | child_result

        return result

    def _eval_function(self, node: ExpressionNode, df: pd.DataFrame) -> pd.Series:
        """Evaluate a function node."""
        func_name = str(node.value).lower()

        # Handle special functions first
        if func_name == "round":
            return self._eval_round(node, df)
        if func_name in ("upper", "lower", "trim", "length"):
            return self._eval_string_function(node, df)
        if func_name in ("year", "month", "day", "hour", "minute", "weekday"):
            return self._eval_date_function(node, df)
        if func_name == "to_numeric":
            return self._eval_to_numeric(node, df)
        if func_name == "to_string":
            return self._eval_to_string(node, df)
        if func_name == "fill_null":
            return self._eval_fill_null(node, df)
        if func_name == "is_null":
            return self._eval_is_null(node, df)

        # Statistical functions (aggregations)
        if func_name in self.STAT_FUNCTIONS:
            return self._eval_stat_function(node, df)

        # Mathematical functions
        if func_name in self.MATH_FUNCTIONS:
            return self._eval_math_function(node, df)

        raise ExpressionError(
            f"Unknown function: {func_name}",
            node_id=node.node_id
        )

    def _eval_math_function(self, node: ExpressionNode, df: pd.DataFrame) -> pd.Series:
        """Evaluate a mathematical function."""
        func_name = str(node.value).lower()
        numpy_func = self.MATH_FUNCTIONS[func_name]

        if len(node.children) == 0:
            raise ExpressionError(
                f"Function '{func_name}' requires at least 1 argument",
                node_id=node.node_id
            )

        child_result = self._evaluate_node(node.children[0], df)
        child_result = self._to_series(child_result, df)

        # Handle potential issues with log/sqrt of negative numbers
        if func_name == "log":
            non_positive = (child_result <= 0).sum()
            if non_positive > 0:
                self.warnings.append(
                    f"log() applied to {non_positive} non-positive values. "
                    "Result will be -inf or nan."
                )
        elif func_name == "sqrt":
            negative = (child_result < 0).sum()
            if negative > 0:
                self.warnings.append(
                    f"sqrt() applied to {negative} negative values. "
                    "Result will be nan."
                )

        return pd.Series(numpy_func(child_result), index=df.index)

    def _eval_stat_function(self, node: ExpressionNode, df: pd.DataFrame) -> pd.Series:
        """Evaluate a statistical function (returns scalar broadcast to series)."""
        func_name = str(node.value).lower()
        pandas_method = self.STAT_FUNCTIONS[func_name]

        if len(node.children) == 0:
            raise ExpressionError(
                f"Function '{func_name}' requires at least 1 argument",
                node_id=node.node_id
            )

        child_result = self._evaluate_node(node.children[0], df)
        child_result = self._to_series(child_result, df)

        # Get the scalar result
        scalar_result = getattr(child_result, pandas_method)()

        # Broadcast to series
        return pd.Series([scalar_result] * len(df), index=df.index)

    def _eval_round(self, node: ExpressionNode, df: pd.DataFrame) -> pd.Series:
        """Evaluate round function with optional precision."""
        if len(node.children) == 0:
            raise ExpressionError(
                "round() requires at least 1 argument",
                node_id=node.node_id
            )

        child_result = self._evaluate_node(node.children[0], df)
        child_result = self._to_series(child_result, df)

        # Get precision from parameters or second child
        decimals = node.parameters.get("decimals", 0)
        if len(node.children) > 1:
            decimals_node = self._evaluate_node(node.children[1], df)
            if isinstance(decimals_node, (int, float)):
                decimals = int(decimals_node)

        return child_result.round(decimals=decimals)

    def _eval_string_function(self, node: ExpressionNode, df: pd.DataFrame) -> pd.Series:
        """Evaluate string functions."""
        func_name = str(node.value).lower()

        if len(node.children) == 0:
            raise ExpressionError(
                f"String function '{func_name}' requires 1 argument",
                node_id=node.node_id
            )

        child_result = self._evaluate_node(node.children[0], df)
        child_result = self._to_series(child_result, df)

        # Convert to string
        str_series = child_result.astype(str)

        if func_name == "upper":
            return str_series.str.upper()
        elif func_name == "lower":
            return str_series.str.lower()
        elif func_name == "trim":
            return str_series.str.strip()
        elif func_name == "length":
            return str_series.str.len()

        raise ExpressionError(
            f"Unknown string function: {func_name}",
            node_id=node.node_id
        )

    def _eval_date_function(self, node: ExpressionNode, df: pd.DataFrame) -> pd.Series:
        """Evaluate date extraction functions."""
        func_name = str(node.value).lower()

        if len(node.children) == 0:
            raise ExpressionError(
                f"Date function '{func_name}' requires 1 argument",
                node_id=node.node_id
            )

        child_result = self._evaluate_node(node.children[0], df)
        child_result = self._to_series(child_result, df)

        # Convert to datetime if not already
        if not pd.api.types.is_datetime64_any_dtype(child_result):
            try:
                child_result = pd.to_datetime(child_result, errors='coerce')
                null_count = child_result.isna().sum()
                if null_count > 0:
                    self.warnings.append(
                        f"Date conversion failed for {null_count} values"
                    )
            except Exception as e:
                raise ExpressionError(
                    f"Could not convert to datetime: {e}",
                    node_id=node.node_id
                )

        date_accessor = child_result.dt
        if func_name == "year":
            return date_accessor.year
        elif func_name == "month":
            return date_accessor.month
        elif func_name == "day":
            return date_accessor.day
        elif func_name == "hour":
            return date_accessor.hour
        elif func_name == "minute":
            return date_accessor.minute
        elif func_name == "weekday":
            return date_accessor.weekday

        raise ExpressionError(
            f"Unknown date function: {func_name}",
            node_id=node.node_id
        )

    def _eval_to_numeric(self, node: ExpressionNode, df: pd.DataFrame) -> pd.Series:
        """Convert to numeric type."""
        if len(node.children) == 0:
            raise ExpressionError(
                "to_numeric() requires 1 argument",
                node_id=node.node_id
            )

        child_result = self._evaluate_node(node.children[0], df)
        child_result = self._to_series(child_result, df)

        result = pd.to_numeric(child_result, errors='coerce')
        null_count = result.isna().sum() - child_result.isna().sum()
        if null_count > 0:
            self.warnings.append(
                f"to_numeric() failed for {null_count} values (set to null)"
            )
        return result

    def _eval_to_string(self, node: ExpressionNode, df: pd.DataFrame) -> pd.Series:
        """Convert to string type."""
        if len(node.children) == 0:
            raise ExpressionError(
                "to_string() requires 1 argument",
                node_id=node.node_id
            )

        child_result = self._evaluate_node(node.children[0], df)
        child_result = self._to_series(child_result, df)

        return child_result.astype(str)

    def _eval_fill_null(self, node: ExpressionNode, df: pd.DataFrame) -> pd.Series:
        """Fill null values with a replacement."""
        if len(node.children) < 2:
            raise ExpressionError(
                "fill_null() requires 2 arguments (value, fill_value)",
                node_id=node.node_id
            )

        child_result = self._evaluate_node(node.children[0], df)
        child_result = self._to_series(child_result, df)

        fill_value = self._evaluate_node(node.children[1], df)
        if isinstance(fill_value, pd.Series):
            fill_value = fill_value.iloc[0] if len(fill_value) > 0 else None

        return child_result.fillna(fill_value)

    def _eval_is_null(self, node: ExpressionNode, df: pd.DataFrame) -> pd.Series:
        """Check if values are null."""
        if len(node.children) == 0:
            raise ExpressionError(
                "is_null() requires 1 argument",
                node_id=node.node_id
            )

        child_result = self._evaluate_node(node.children[0], df)
        child_result = self._to_series(child_result, df)

        return child_result.isna()

    def _eval_conditional(self, node: ExpressionNode, df: pd.DataFrame) -> pd.Series:
        """Evaluate a conditional (if-then-else) node."""
        if len(node.children) != 3:
            raise ExpressionError(
                "Conditional requires 3 children: condition, if_true, if_false",
                node_id=node.node_id
            )

        condition = self._evaluate_node(node.children[0], df)
        condition = self._to_series(condition, df).astype(bool)

        if_true = self._evaluate_node(node.children[1], df)
        if_true = self._to_series(if_true, df)

        if_false = self._evaluate_node(node.children[2], df)
        if_false = self._to_series(if_false, df)

        # Use numpy where for conditional selection
        return pd.Series(
            np.where(condition, if_true, if_false),
            index=df.index
        )

    def _to_series(
        self,
        value: pd.Series | Any,
        df: pd.DataFrame
    ) -> pd.Series:
        """Convert a value to a Series if it isn't already."""
        if isinstance(value, pd.Series):
            return value
        if value is None:
            # Preserve object dtype for None (scalar broadcast would coerce to NaN)
            return pd.Series([None] * len(df), index=df.index)
        # Scalar broadcast: C-level fill with proper dtype (avoids building a
        # len(df) Python list and an object-dtype array)
        return pd.Series(value, index=df.index)

    def validate_expression(
        self,
        expression_tree: ExpressionNode,
        column_info: dict[str, str]
    ) -> tuple[bool, list[str], list[str], str | None]:
        """
        Validate an expression tree without evaluating it.

        Args:
            expression_tree: Root node of the expression tree
            column_info: Dictionary mapping column names to their types

        Returns:
            Tuple of (is_valid, errors, warnings, inferred_type)
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Check input columns exist
        input_columns = expression_tree.get_input_columns()
        for col in input_columns:
            if col not in column_info:
                errors.append(f"Column '{col}' not found in dataset")

        # Validate tree structure
        def validate_node(node: ExpressionNode, path: str = "root") -> str | None:
            """Recursively validate node and return inferred type."""
            if node.node_type == NodeType.COLUMN:
                col_name = str(node.value)
                return column_info.get(col_name, "unknown")

            elif node.node_type == NodeType.CONSTANT:
                if isinstance(node.value, bool):
                    return "boolean"
                elif isinstance(node.value, (int, float)):
                    return "numeric"
                elif isinstance(node.value, str):
                    return "string"
                return "unknown"

            elif node.node_type == NodeType.OPERATION:
                op_type = str(node.value).lower()

                # Check child count
                if op_type == "not":
                    if len(node.children) != 1:
                        errors.append(f"{path}: NOT requires exactly 1 child")
                elif len(node.children) < 2:
                    errors.append(f"{path}: Operation '{op_type}' requires at least 2 children")

                # Validate children
                child_types = []
                for i, child in enumerate(node.children):
                    child_type = validate_node(child, f"{path}.children[{i}]")
                    child_types.append(child_type)

                # Check type compatibility
                if op_type in self.BINARY_OPERATIONS:
                    for i, ct in enumerate(child_types):
                        if ct not in ("numeric", "unknown"):
                            warnings.append(
                                f"{path}: Arithmetic operation on non-numeric type '{ct}'"
                            )
                    return "numeric"

                elif op_type in self.COMPARISON_OPERATIONS:
                    return "boolean"

                elif op_type in ("and", "or", "not"):
                    return "boolean"

                return "unknown"

            elif node.node_type == NodeType.FUNCTION:
                func_name = str(node.value).lower()

                # Validate children
                for i, child in enumerate(node.children):
                    validate_node(child, f"{path}.children[{i}]")

                # Infer return type based on function
                if func_name in self.MATH_FUNCTIONS or func_name in self.STAT_FUNCTIONS:
                    return "numeric"
                elif func_name == "round":
                    return "numeric"
                elif func_name in ("upper", "lower", "trim", "to_string"):
                    return "string"
                elif func_name == "length":
                    return "numeric"
                elif func_name in ("year", "month", "day", "hour", "minute", "weekday"):
                    return "numeric"
                elif func_name == "is_null":
                    return "boolean"
                elif func_name == "to_numeric":
                    return "numeric"

                return "unknown"

            elif node.node_type == NodeType.CONDITIONAL:
                if len(node.children) != 3:
                    errors.append(f"{path}: Conditional requires 3 children")
                else:
                    for i, child in enumerate(node.children):
                        validate_node(child, f"{path}.children[{i}]")
                return "unknown"

            return "unknown"

        inferred_type = validate_node(expression_tree)

        is_valid = len(errors) == 0
        return is_valid, errors, warnings, inferred_type
