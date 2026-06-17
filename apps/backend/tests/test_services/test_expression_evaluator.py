"""
Tests for the Expression Evaluator service.

Tests safe evaluation of expression trees using pandas operations.
"""

import numpy as np
import pandas as pd
import pytest

from app.models.feature import ExpressionNode, NodeType
from app.services.expression_evaluator import (
    ColumnNotFoundError,
    ExpressionEvaluator,
)


@pytest.fixture
def evaluator():
    """Create a fresh ExpressionEvaluator instance."""
    return ExpressionEvaluator()


@pytest.fixture
def sample_df():
    """Create a sample dataframe for testing."""
    return pd.DataFrame({
        'a': [1, 2, 3, 4, 5],
        'b': [10, 20, 30, 40, 50],
        'c': [1.5, 2.5, 3.5, 4.5, 5.5],
        'text': ['hello', 'world', 'foo', 'bar', 'baz'],
        'date': pd.to_datetime(['2023-01-01', '2023-02-15', '2023-03-20', '2023-04-10', '2023-05-05']),
        'nullable': [1, None, 3, None, 5],
    })


class TestColumnEvaluation:
    """Tests for column reference evaluation."""

    def test_eval_column_simple(self, evaluator, sample_df):
        """Test simple column reference."""
        node = ExpressionNode(
            node_id="n1",
            node_type=NodeType.COLUMN,
            value="a"
        )
        result, warnings = evaluator.evaluate(node, sample_df)
        pd.testing.assert_series_equal(
            result, sample_df['a'], check_names=False
        )

    def test_eval_column_not_found(self, evaluator, sample_df):
        """Test column not found error."""
        node = ExpressionNode(
            node_id="n1",
            node_type=NodeType.COLUMN,
            value="nonexistent"
        )
        with pytest.raises(ColumnNotFoundError):
            evaluator.evaluate(node, sample_df)


class TestConstantEvaluation:
    """Tests for constant value evaluation."""

    def test_eval_constant_number(self, evaluator, sample_df):
        """Test constant number."""
        node = ExpressionNode(
            node_id="n1",
            node_type=NodeType.CONSTANT,
            value=42
        )
        result, warnings = evaluator.evaluate(node, sample_df)
        assert all(result == 42)

    def test_eval_constant_string(self, evaluator, sample_df):
        """Test constant string."""
        node = ExpressionNode(
            node_id="n1",
            node_type=NodeType.CONSTANT,
            value="test"
        )
        result, warnings = evaluator.evaluate(node, sample_df)
        assert all(result == "test")

    def test_to_series_none_preserves_object_dtype(self, evaluator, sample_df):
        """None broadcasts to object dtype (not coerced to float NaN)."""
        result = evaluator._to_series(None, sample_df)
        assert result.dtype == object
        assert result.isna().all()
        assert len(result) == len(sample_df)


class TestArithmeticOperations:
    """Tests for arithmetic operations."""

    def test_add_columns(self, evaluator, sample_df):
        """Test adding two columns."""
        node = ExpressionNode(
            node_id="n1",
            node_type=NodeType.OPERATION,
            value="add",
            children=[
                ExpressionNode(node_id="c1", node_type=NodeType.COLUMN, value="a"),
                ExpressionNode(node_id="c2", node_type=NodeType.COLUMN, value="b"),
            ]
        )
        result, warnings = evaluator.evaluate(node, sample_df)
        expected = sample_df['a'] + sample_df['b']
        pd.testing.assert_series_equal(result, expected, check_names=False)

    def test_subtract_columns(self, evaluator, sample_df):
        """Test subtracting columns."""
        node = ExpressionNode(
            node_id="n1",
            node_type=NodeType.OPERATION,
            value="subtract",
            children=[
                ExpressionNode(node_id="c1", node_type=NodeType.COLUMN, value="b"),
                ExpressionNode(node_id="c2", node_type=NodeType.COLUMN, value="a"),
            ]
        )
        result, warnings = evaluator.evaluate(node, sample_df)
        expected = sample_df['b'] - sample_df['a']
        pd.testing.assert_series_equal(result, expected, check_names=False)

    def test_multiply_columns(self, evaluator, sample_df):
        """Test multiplying columns."""
        node = ExpressionNode(
            node_id="n1",
            node_type=NodeType.OPERATION,
            value="multiply",
            children=[
                ExpressionNode(node_id="c1", node_type=NodeType.COLUMN, value="a"),
                ExpressionNode(node_id="c2", node_type=NodeType.COLUMN, value="c"),
            ]
        )
        result, warnings = evaluator.evaluate(node, sample_df)
        expected = sample_df['a'] * sample_df['c']
        pd.testing.assert_series_equal(result, expected, check_names=False)

    def test_divide_columns(self, evaluator, sample_df):
        """Test dividing columns."""
        node = ExpressionNode(
            node_id="n1",
            node_type=NodeType.OPERATION,
            value="divide",
            children=[
                ExpressionNode(node_id="c1", node_type=NodeType.COLUMN, value="b"),
                ExpressionNode(node_id="c2", node_type=NodeType.COLUMN, value="a"),
            ]
        )
        result, warnings = evaluator.evaluate(node, sample_df)
        expected = sample_df['b'] / sample_df['a']
        pd.testing.assert_series_equal(result, expected, check_names=False)

    def test_divide_by_zero_warning(self, evaluator):
        """Test division by zero produces warning."""
        df = pd.DataFrame({'a': [1, 2, 3], 'b': [1, 0, 2]})
        node = ExpressionNode(
            node_id="n1",
            node_type=NodeType.OPERATION,
            value="divide",
            children=[
                ExpressionNode(node_id="c1", node_type=NodeType.COLUMN, value="a"),
                ExpressionNode(node_id="c2", node_type=NodeType.COLUMN, value="b"),
            ]
        )
        result, warnings = evaluator.evaluate(node, df)
        assert len(warnings) > 0
        assert "division by zero" in warnings[0].lower()

    def test_power_operation(self, evaluator, sample_df):
        """Test power operation."""
        node = ExpressionNode(
            node_id="n1",
            node_type=NodeType.OPERATION,
            value="power",
            children=[
                ExpressionNode(node_id="c1", node_type=NodeType.COLUMN, value="a"),
                ExpressionNode(node_id="c2", node_type=NodeType.CONSTANT, value=2),
            ]
        )
        result, warnings = evaluator.evaluate(node, sample_df)
        expected = sample_df['a'] ** 2
        pd.testing.assert_series_equal(result, expected, check_names=False)

    def test_modulo_operation(self, evaluator, sample_df):
        """Test modulo operation."""
        node = ExpressionNode(
            node_id="n1",
            node_type=NodeType.OPERATION,
            value="modulo",
            children=[
                ExpressionNode(node_id="c1", node_type=NodeType.COLUMN, value="b"),
                ExpressionNode(node_id="c2", node_type=NodeType.CONSTANT, value=7),
            ]
        )
        result, warnings = evaluator.evaluate(node, sample_df)
        expected = sample_df['b'] % 7
        pd.testing.assert_series_equal(result, expected, check_names=False)


class TestComparisonOperations:
    """Tests for comparison operations."""

    def test_equal_operation(self, evaluator, sample_df):
        """Test equal comparison."""
        node = ExpressionNode(
            node_id="n1",
            node_type=NodeType.OPERATION,
            value="equal",
            children=[
                ExpressionNode(node_id="c1", node_type=NodeType.COLUMN, value="a"),
                ExpressionNode(node_id="c2", node_type=NodeType.CONSTANT, value=3),
            ]
        )
        result, warnings = evaluator.evaluate(node, sample_df)
        expected = sample_df['a'] == 3
        pd.testing.assert_series_equal(result, expected, check_names=False)

    def test_greater_than_operation(self, evaluator, sample_df):
        """Test greater than comparison."""
        node = ExpressionNode(
            node_id="n1",
            node_type=NodeType.OPERATION,
            value="greater_than",
            children=[
                ExpressionNode(node_id="c1", node_type=NodeType.COLUMN, value="a"),
                ExpressionNode(node_id="c2", node_type=NodeType.CONSTANT, value=3),
            ]
        )
        result, warnings = evaluator.evaluate(node, sample_df)
        expected = sample_df['a'] > 3
        pd.testing.assert_series_equal(result, expected, check_names=False)

    def test_less_than_operation(self, evaluator, sample_df):
        """Test less than comparison."""
        node = ExpressionNode(
            node_id="n1",
            node_type=NodeType.OPERATION,
            value="less_than",
            children=[
                ExpressionNode(node_id="c1", node_type=NodeType.COLUMN, value="a"),
                ExpressionNode(node_id="c2", node_type=NodeType.CONSTANT, value=3),
            ]
        )
        result, warnings = evaluator.evaluate(node, sample_df)
        expected = sample_df['a'] < 3
        pd.testing.assert_series_equal(result, expected, check_names=False)


class TestLogicalOperations:
    """Tests for logical operations."""

    def test_and_operation(self, evaluator, sample_df):
        """Test logical AND."""
        node = ExpressionNode(
            node_id="n1",
            node_type=NodeType.OPERATION,
            value="and",
            children=[
                ExpressionNode(
                    node_id="c1",
                    node_type=NodeType.OPERATION,
                    value="greater_than",
                    children=[
                        ExpressionNode(node_id="c1a", node_type=NodeType.COLUMN, value="a"),
                        ExpressionNode(node_id="c1b", node_type=NodeType.CONSTANT, value=2),
                    ]
                ),
                ExpressionNode(
                    node_id="c2",
                    node_type=NodeType.OPERATION,
                    value="less_than",
                    children=[
                        ExpressionNode(node_id="c2a", node_type=NodeType.COLUMN, value="a"),
                        ExpressionNode(node_id="c2b", node_type=NodeType.CONSTANT, value=5),
                    ]
                ),
            ]
        )
        result, warnings = evaluator.evaluate(node, sample_df)
        expected = (sample_df['a'] > 2) & (sample_df['a'] < 5)
        pd.testing.assert_series_equal(result, expected, check_names=False)

    def test_or_operation(self, evaluator, sample_df):
        """Test logical OR."""
        node = ExpressionNode(
            node_id="n1",
            node_type=NodeType.OPERATION,
            value="or",
            children=[
                ExpressionNode(
                    node_id="c1",
                    node_type=NodeType.OPERATION,
                    value="equal",
                    children=[
                        ExpressionNode(node_id="c1a", node_type=NodeType.COLUMN, value="a"),
                        ExpressionNode(node_id="c1b", node_type=NodeType.CONSTANT, value=1),
                    ]
                ),
                ExpressionNode(
                    node_id="c2",
                    node_type=NodeType.OPERATION,
                    value="equal",
                    children=[
                        ExpressionNode(node_id="c2a", node_type=NodeType.COLUMN, value="a"),
                        ExpressionNode(node_id="c2b", node_type=NodeType.CONSTANT, value=5),
                    ]
                ),
            ]
        )
        result, warnings = evaluator.evaluate(node, sample_df)
        expected = (sample_df['a'] == 1) | (sample_df['a'] == 5)
        pd.testing.assert_series_equal(result, expected, check_names=False)

    def test_not_operation(self, evaluator, sample_df):
        """Test logical NOT."""
        node = ExpressionNode(
            node_id="n1",
            node_type=NodeType.OPERATION,
            value="not",
            children=[
                ExpressionNode(
                    node_id="c1",
                    node_type=NodeType.OPERATION,
                    value="greater_than",
                    children=[
                        ExpressionNode(node_id="c1a", node_type=NodeType.COLUMN, value="a"),
                        ExpressionNode(node_id="c1b", node_type=NodeType.CONSTANT, value=3),
                    ]
                ),
            ]
        )
        result, warnings = evaluator.evaluate(node, sample_df)
        expected = ~(sample_df['a'] > 3)
        pd.testing.assert_series_equal(result, expected, check_names=False)


class TestMathFunctions:
    """Tests for mathematical functions."""

    def test_abs_function(self, evaluator):
        """Test absolute value function."""
        df = pd.DataFrame({'a': [-1, -2, 3, -4, 5]})
        node = ExpressionNode(
            node_id="n1",
            node_type=NodeType.FUNCTION,
            value="abs",
            children=[
                ExpressionNode(node_id="c1", node_type=NodeType.COLUMN, value="a"),
            ]
        )
        result, warnings = evaluator.evaluate(node, df)
        expected = df['a'].abs()
        pd.testing.assert_series_equal(result, expected, check_names=False)

    def test_sqrt_function(self, evaluator, sample_df):
        """Test square root function."""
        node = ExpressionNode(
            node_id="n1",
            node_type=NodeType.FUNCTION,
            value="sqrt",
            children=[
                ExpressionNode(node_id="c1", node_type=NodeType.COLUMN, value="a"),
            ]
        )
        result, warnings = evaluator.evaluate(node, sample_df)
        expected = np.sqrt(sample_df['a'])
        pd.testing.assert_series_equal(result, pd.Series(expected, index=sample_df.index), check_names=False)

    def test_log_function(self, evaluator, sample_df):
        """Test natural log function."""
        node = ExpressionNode(
            node_id="n1",
            node_type=NodeType.FUNCTION,
            value="log",
            children=[
                ExpressionNode(node_id="c1", node_type=NodeType.COLUMN, value="a"),
            ]
        )
        result, warnings = evaluator.evaluate(node, sample_df)
        expected = np.log(sample_df['a'])
        pd.testing.assert_series_equal(result, pd.Series(expected, index=sample_df.index), check_names=False)

    def test_log_negative_warning(self, evaluator):
        """Test log of negative produces warning."""
        df = pd.DataFrame({'a': [1, -2, 3]})
        node = ExpressionNode(
            node_id="n1",
            node_type=NodeType.FUNCTION,
            value="log",
            children=[
                ExpressionNode(node_id="c1", node_type=NodeType.COLUMN, value="a"),
            ]
        )
        result, warnings = evaluator.evaluate(node, df)
        assert len(warnings) > 0

    def test_round_function(self, evaluator, sample_df):
        """Test round function."""
        node = ExpressionNode(
            node_id="n1",
            node_type=NodeType.FUNCTION,
            value="round",
            children=[
                ExpressionNode(node_id="c1", node_type=NodeType.COLUMN, value="c"),
            ],
            parameters={"decimals": 0}
        )
        result, warnings = evaluator.evaluate(node, sample_df)
        expected = sample_df['c'].round(0)
        pd.testing.assert_series_equal(result, expected, check_names=False)


class TestStatFunctions:
    """Tests for statistical functions."""

    def test_mean_function(self, evaluator, sample_df):
        """Test mean function (broadcasts scalar to series)."""
        node = ExpressionNode(
            node_id="n1",
            node_type=NodeType.FUNCTION,
            value="mean",
            children=[
                ExpressionNode(node_id="c1", node_type=NodeType.COLUMN, value="a"),
            ]
        )
        result, warnings = evaluator.evaluate(node, sample_df)
        expected_mean = sample_df['a'].mean()
        assert all(result == expected_mean)

    def test_sum_function(self, evaluator, sample_df):
        """Test sum function (broadcasts scalar to series)."""
        node = ExpressionNode(
            node_id="n1",
            node_type=NodeType.FUNCTION,
            value="sum",
            children=[
                ExpressionNode(node_id="c1", node_type=NodeType.COLUMN, value="a"),
            ]
        )
        result, warnings = evaluator.evaluate(node, sample_df)
        expected_sum = sample_df['a'].sum()
        assert all(result == expected_sum)


class TestStringFunctions:
    """Tests for string functions."""

    def test_upper_function(self, evaluator, sample_df):
        """Test uppercase function."""
        node = ExpressionNode(
            node_id="n1",
            node_type=NodeType.FUNCTION,
            value="upper",
            children=[
                ExpressionNode(node_id="c1", node_type=NodeType.COLUMN, value="text"),
            ]
        )
        result, warnings = evaluator.evaluate(node, sample_df)
        expected = sample_df['text'].str.upper()
        pd.testing.assert_series_equal(result, expected, check_names=False)

    def test_length_function(self, evaluator, sample_df):
        """Test length function."""
        node = ExpressionNode(
            node_id="n1",
            node_type=NodeType.FUNCTION,
            value="length",
            children=[
                ExpressionNode(node_id="c1", node_type=NodeType.COLUMN, value="text"),
            ]
        )
        result, warnings = evaluator.evaluate(node, sample_df)
        expected = sample_df['text'].str.len()
        pd.testing.assert_series_equal(result, expected, check_names=False)


class TestDateFunctions:
    """Tests for date functions."""

    def test_year_function(self, evaluator, sample_df):
        """Test year extraction."""
        node = ExpressionNode(
            node_id="n1",
            node_type=NodeType.FUNCTION,
            value="year",
            children=[
                ExpressionNode(node_id="c1", node_type=NodeType.COLUMN, value="date"),
            ]
        )
        result, warnings = evaluator.evaluate(node, sample_df)
        expected = sample_df['date'].dt.year
        pd.testing.assert_series_equal(result, expected, check_names=False)

    def test_month_function(self, evaluator, sample_df):
        """Test month extraction."""
        node = ExpressionNode(
            node_id="n1",
            node_type=NodeType.FUNCTION,
            value="month",
            children=[
                ExpressionNode(node_id="c1", node_type=NodeType.COLUMN, value="date"),
            ]
        )
        result, warnings = evaluator.evaluate(node, sample_df)
        expected = sample_df['date'].dt.month
        pd.testing.assert_series_equal(result, expected, check_names=False)


class TestConditional:
    """Tests for conditional (if-then-else) expressions."""

    def test_conditional_simple(self, evaluator, sample_df):
        """Test simple conditional."""
        node = ExpressionNode(
            node_id="n1",
            node_type=NodeType.CONDITIONAL,
            value="if",
            children=[
                # Condition: a > 3
                ExpressionNode(
                    node_id="cond",
                    node_type=NodeType.OPERATION,
                    value="greater_than",
                    children=[
                        ExpressionNode(node_id="c1", node_type=NodeType.COLUMN, value="a"),
                        ExpressionNode(node_id="c2", node_type=NodeType.CONSTANT, value=3),
                    ]
                ),
                # If true: return b
                ExpressionNode(node_id="if_true", node_type=NodeType.COLUMN, value="b"),
                # If false: return 0
                ExpressionNode(node_id="if_false", node_type=NodeType.CONSTANT, value=0),
            ]
        )
        result, warnings = evaluator.evaluate(node, sample_df)
        expected = np.where(sample_df['a'] > 3, sample_df['b'], 0)
        pd.testing.assert_series_equal(
            result, pd.Series(expected, index=sample_df.index), check_names=False
        )


class TestNullHandling:
    """Tests for null value handling."""

    def test_fill_null_function(self, evaluator, sample_df):
        """Test fill_null function."""
        node = ExpressionNode(
            node_id="n1",
            node_type=NodeType.FUNCTION,
            value="fill_null",
            children=[
                ExpressionNode(node_id="c1", node_type=NodeType.COLUMN, value="nullable"),
                ExpressionNode(node_id="c2", node_type=NodeType.CONSTANT, value=0),
            ]
        )
        result, warnings = evaluator.evaluate(node, sample_df)
        expected = sample_df['nullable'].fillna(0)
        pd.testing.assert_series_equal(result, expected, check_names=False)

    def test_is_null_function(self, evaluator, sample_df):
        """Test is_null function."""
        node = ExpressionNode(
            node_id="n1",
            node_type=NodeType.FUNCTION,
            value="is_null",
            children=[
                ExpressionNode(node_id="c1", node_type=NodeType.COLUMN, value="nullable"),
            ]
        )
        result, warnings = evaluator.evaluate(node, sample_df)
        expected = sample_df['nullable'].isna()
        pd.testing.assert_series_equal(result, expected, check_names=False)


class TestValidation:
    """Tests for expression validation."""

    def test_validate_valid_expression(self, evaluator):
        """Test validating a valid expression."""
        column_info = {'a': 'numeric', 'b': 'numeric'}
        node = ExpressionNode(
            node_id="n1",
            node_type=NodeType.OPERATION,
            value="add",
            children=[
                ExpressionNode(node_id="c1", node_type=NodeType.COLUMN, value="a"),
                ExpressionNode(node_id="c2", node_type=NodeType.COLUMN, value="b"),
            ]
        )
        is_valid, errors, warnings, inferred_type = evaluator.validate_expression(
            node, column_info
        )
        assert is_valid
        assert len(errors) == 0
        assert inferred_type == "numeric"

    def test_validate_missing_column(self, evaluator):
        """Test validation catches missing column."""
        column_info = {'a': 'numeric'}
        node = ExpressionNode(
            node_id="n1",
            node_type=NodeType.COLUMN,
            value="nonexistent"
        )
        is_valid, errors, warnings, inferred_type = evaluator.validate_expression(
            node, column_info
        )
        assert not is_valid
        assert len(errors) > 0
        assert "not found" in errors[0].lower()


class TestNestedExpressions:
    """Tests for nested/complex expressions."""

    def test_nested_operations(self, evaluator, sample_df):
        """Test nested operations: (a + b) * c"""
        node = ExpressionNode(
            node_id="n1",
            node_type=NodeType.OPERATION,
            value="multiply",
            children=[
                ExpressionNode(
                    node_id="add",
                    node_type=NodeType.OPERATION,
                    value="add",
                    children=[
                        ExpressionNode(node_id="c1", node_type=NodeType.COLUMN, value="a"),
                        ExpressionNode(node_id="c2", node_type=NodeType.COLUMN, value="b"),
                    ]
                ),
                ExpressionNode(node_id="c3", node_type=NodeType.COLUMN, value="c"),
            ]
        )
        result, warnings = evaluator.evaluate(node, sample_df)
        expected = (sample_df['a'] + sample_df['b']) * sample_df['c']
        pd.testing.assert_series_equal(result, expected, check_names=False)

    def test_function_with_operation(self, evaluator, sample_df):
        """Test function with operation as argument: log(a + 1)"""
        node = ExpressionNode(
            node_id="n1",
            node_type=NodeType.FUNCTION,
            value="log",
            children=[
                ExpressionNode(
                    node_id="add",
                    node_type=NodeType.OPERATION,
                    value="add",
                    children=[
                        ExpressionNode(node_id="c1", node_type=NodeType.COLUMN, value="a"),
                        ExpressionNode(node_id="c2", node_type=NodeType.CONSTANT, value=1),
                    ]
                ),
            ]
        )
        result, warnings = evaluator.evaluate(node, sample_df)
        expected = np.log(sample_df['a'] + 1)
        pd.testing.assert_series_equal(result, pd.Series(expected, index=sample_df.index), check_names=False)
