"""
Feature definition model for MongoDB.

This model stores feature definitions created by the Visual Feature Builder,
including expression trees, metadata, and validation status.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Dict, List, Optional, Union

from beanie import Document, Indexed, PydanticObjectId
from pydantic import BaseModel, Field, field_validator, model_validator


def get_current_time() -> datetime:
    """Get current UTC time for default timestamps."""
    return datetime.now(timezone.utc)


class NodeType(str, Enum):
    """Types of nodes in an expression tree."""
    COLUMN = "column"
    OPERATION = "operation"
    FUNCTION = "function"
    CONSTANT = "constant"
    CONDITIONAL = "conditional"


class OperationType(str, Enum):
    """Supported operations for expression nodes."""
    # Arithmetic
    ADD = "add"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    DIVIDE = "divide"
    MODULO = "modulo"
    POWER = "power"

    # Comparison
    EQUAL = "equal"
    NOT_EQUAL = "not_equal"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"

    # Logical
    AND = "and"
    OR = "or"
    NOT = "not"


class FunctionType(str, Enum):
    """Supported functions for expression nodes."""
    # Mathematical
    ABS = "abs"
    LOG = "log"
    LOG10 = "log10"
    SQRT = "sqrt"
    EXP = "exp"
    ROUND = "round"
    CEIL = "ceil"
    FLOOR = "floor"
    SIN = "sin"
    COS = "cos"
    TAN = "tan"

    # Statistical
    MEAN = "mean"
    MEDIAN = "median"
    STD = "std"
    MIN = "min"
    MAX = "max"
    SUM = "sum"

    # String
    UPPER = "upper"
    LOWER = "lower"
    TRIM = "trim"
    LENGTH = "length"

    # Date
    YEAR = "year"
    MONTH = "month"
    DAY = "day"
    HOUR = "hour"
    MINUTE = "minute"
    WEEKDAY = "weekday"

    # Type conversion
    TO_NUMERIC = "to_numeric"
    TO_STRING = "to_string"

    # Null handling
    FILL_NULL = "fill_null"
    IS_NULL = "is_null"


class OutputType(str, Enum):
    """Expected output types for features."""
    NUMERIC = "numeric"
    BOOLEAN = "boolean"
    STRING = "string"
    DATETIME = "datetime"
    CATEGORICAL = "categorical"


class ExpressionNode(BaseModel):
    """
    A node in the expression tree representing part of a feature formula.

    Expression trees are built recursively, where each node can have children
    that are also ExpressionNodes. This allows for complex nested expressions.
    """

    node_id: str = Field(..., description="Unique identifier for this node")
    node_type: NodeType = Field(..., description="Type of node: column, operation, function, constant, conditional")

    # Value depends on node_type:
    # - column: column name
    # - operation: operation type (add, subtract, etc.)
    # - function: function name (abs, log, etc.)
    # - constant: the constant value
    # - conditional: "if"
    value: Union[str, float, int, bool, None] = Field(None, description="Node value (meaning depends on node_type)")

    # Children for operations and functions
    children: List["ExpressionNode"] = Field(default_factory=list, description="Child nodes for operations/functions")

    # Additional parameters for functions (e.g., rounding precision)
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Additional parameters for functions")

    # Position for visual rendering (stored for UI persistence)
    position: Optional[Dict[str, float]] = Field(None, description="Position for visual rendering {'x': float, 'y': float}")

    @field_validator('node_type', mode='before')
    @classmethod
    def validate_node_type(cls, v):
        """Convert string to NodeType enum."""
        if isinstance(v, str):
            return NodeType(v)
        return v

    @model_validator(mode='after')
    def validate_children_for_type(self) -> "ExpressionNode":
        """Validate that node has appropriate children for its type."""
        if self.node_type == NodeType.OPERATION:
            # Operations need at least 1 child (unary) or 2 children (binary)
            if self.value == OperationType.NOT.value or self.value == "not":
                if len(self.children) != 1:
                    raise ValueError("NOT operation requires exactly 1 child")
            elif len(self.children) < 2:
                pass  # Allow incomplete trees during construction
        elif self.node_type == NodeType.FUNCTION:
            # Functions need at least 1 child
            pass  # Allow incomplete trees during construction
        elif self.node_type == NodeType.CONDITIONAL:
            # Conditionals need 3 children: condition, if_true, if_false
            if len(self.children) > 0 and len(self.children) != 3:
                pass  # Allow incomplete trees during construction
        return self

    def get_input_columns(self) -> List[str]:
        """Recursively get all column names used in this node and its children."""
        columns = []
        if self.node_type == NodeType.COLUMN and self.value:
            columns.append(str(self.value))
        for child in self.children:
            columns.extend(child.get_input_columns())
        return list(set(columns))

    def to_formula_string(self) -> str:
        """Convert the expression tree to a human-readable formula string."""
        if self.node_type == NodeType.COLUMN:
            return f"[{self.value}]"
        elif self.node_type == NodeType.CONSTANT:
            if isinstance(self.value, str):
                return f'"{self.value}"'
            return str(self.value)
        elif self.node_type == NodeType.OPERATION:
            if len(self.children) < 2:
                return f"({self.value}: incomplete)"
            op_symbols = {
                "add": "+", "subtract": "-", "multiply": "*", "divide": "/",
                "modulo": "%", "power": "**",
                "equal": "==", "not_equal": "!=", "greater_than": ">",
                "less_than": "<", "greater_than_or_equal": ">=", "less_than_or_equal": "<=",
                "and": "AND", "or": "OR"
            }
            symbol = op_symbols.get(str(self.value), str(self.value))
            if self.value == "not":
                return f"NOT({self.children[0].to_formula_string()})"
            return f"({self.children[0].to_formula_string()} {symbol} {self.children[1].to_formula_string()})"
        elif self.node_type == NodeType.FUNCTION:
            if len(self.children) == 0:
                return f"{self.value}()"
            child_formulas = ", ".join(c.to_formula_string() for c in self.children)
            return f"{self.value}({child_formulas})"
        elif self.node_type == NodeType.CONDITIONAL:
            if len(self.children) != 3:
                return "IF(incomplete)"
            return f"IF({self.children[0].to_formula_string()}, {self.children[1].to_formula_string()}, {self.children[2].to_formula_string()})"
        return str(self.value)


# Enable recursive model reference
ExpressionNode.model_rebuild()


class FeatureValidationResult(BaseModel):
    """Validation result for a feature expression."""

    is_valid: bool = Field(..., description="Whether the expression is valid")
    errors: List[str] = Field(default_factory=list, description="Validation errors")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    inferred_type: Optional[OutputType] = Field(None, description="Inferred output type")
    validated_at: datetime = Field(default_factory=get_current_time)


class FeatureStatistics(BaseModel):
    """Statistics for a computed feature."""

    mean: Optional[float] = Field(None, description="Mean value")
    median: Optional[float] = Field(None, description="Median value")
    std: Optional[float] = Field(None, description="Standard deviation")
    min_value: Optional[float] = Field(None, alias="min", description="Minimum value")
    max_value: Optional[float] = Field(None, alias="max", description="Maximum value")
    null_count: int = Field(default=0, ge=0, description="Number of null values")
    unique_count: int = Field(default=0, ge=0, description="Number of unique values")
    total_count: int = Field(default=0, ge=0, description="Total number of values")

    model_config = {
        "populate_by_name": True
    }


class FeatureDefinition(Document):
    """
    Feature definition document.

    Stores feature definitions created by the Visual Feature Builder,
    including the expression tree, metadata, and validation status.
    """

    # Ownership and identification
    user_id: Annotated[str, Indexed()] = Field(..., description="User who created this feature")
    dataset_id: Annotated[str, Indexed()] = Field(..., description="Dataset this feature is for")
    feature_id: Annotated[str, Indexed()] = Field(..., description="Unique feature identifier")

    # Feature metadata
    name: str = Field(..., min_length=1, max_length=255, description="Feature name")
    description: Optional[str] = Field(None, max_length=1000, description="Feature description")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")

    # Expression definition
    expression_tree: ExpressionNode = Field(..., description="Root node of the expression tree")
    formula_string: Optional[str] = Field(None, description="Human-readable formula (auto-generated)")

    # Input/Output
    input_columns: List[str] = Field(default_factory=list, description="Columns used in the expression")
    output_type: OutputType = Field(default=OutputType.NUMERIC, description="Expected output type")

    # Validation
    validation_result: Optional[FeatureValidationResult] = None
    is_valid: bool = Field(default=False, description="Whether feature is valid and ready to use")

    # Statistics (computed during preview)
    statistics: Optional[FeatureStatistics] = None

    # Visual state (for UI persistence)
    canvas_state: Optional[Dict[str, Any]] = Field(None, description="Canvas state for ReactFlow")

    # Timestamps
    created_at: datetime = Field(default_factory=get_current_time)
    updated_at: datetime = Field(default_factory=get_current_time)

    # Version tracking
    version: str = Field(default="1.0.0", description="Feature version")

    class Settings:
        name = "feature_definitions"
        indexes = [
            # Single field indexes
            "user_id",
            "dataset_id",
            "feature_id",
            "created_at",
            "is_valid",
            # Compound indexes
            [("user_id", 1), ("dataset_id", 1)],  # List features for user's dataset
            [("dataset_id", 1), ("created_at", -1)],  # List dataset features chronologically
            [("user_id", 1), ("created_at", -1)],  # List user's features chronologically
            [("dataset_id", 1), ("is_valid", 1)],  # Filter valid features for dataset
            [("dataset_id", 1), ("name", 1)],  # Unique name per dataset
        ]

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {
            PydanticObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
    }

    @model_validator(mode='after')
    def auto_compute_fields(self) -> "FeatureDefinition":
        """Auto-compute derived fields from expression tree."""
        if self.expression_tree:
            # Auto-compute input columns
            self.input_columns = self.expression_tree.get_input_columns()
            # Auto-compute formula string
            self.formula_string = self.expression_tree.to_formula_string()
        return self

    def update_timestamp(self) -> None:
        """Update the updated_at timestamp to current time."""
        self.updated_at = get_current_time()

    def validate_expression(self) -> FeatureValidationResult:
        """
        Validate the expression tree.

        Returns:
            FeatureValidationResult with validation status
        """
        errors: List[str] = []
        warnings: List[str] = []

        if not self.expression_tree:
            errors.append("Expression tree is empty")
            result = FeatureValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings
            )
            self.validation_result = result
            self.is_valid = False
            return result

        # Validate that we have input columns
        if not self.input_columns:
            errors.append("Expression must reference at least one column")

        # Check for incomplete operations
        def check_completeness(node: ExpressionNode, path: str = "root") -> None:
            if node.node_type == NodeType.OPERATION:
                if node.value == "not" or node.value == OperationType.NOT.value:
                    if len(node.children) != 1:
                        errors.append(f"NOT operation at {path} requires exactly 1 child")
                elif len(node.children) < 2:
                    errors.append(f"Operation '{node.value}' at {path} requires at least 2 children")
            elif node.node_type == NodeType.FUNCTION:
                if len(node.children) == 0:
                    # Some functions may not need children (e.g., constants)
                    pass
            elif node.node_type == NodeType.CONDITIONAL:
                if len(node.children) != 3:
                    errors.append(f"Conditional at {path} requires exactly 3 children (condition, if_true, if_false)")

            for i, child in enumerate(node.children):
                check_completeness(child, f"{path}.children[{i}]")

        check_completeness(self.expression_tree)

        result = FeatureValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            inferred_type=self.output_type
        )

        self.validation_result = result
        self.is_valid = result.is_valid
        self.update_timestamp()

        return result

    def mark_valid(self) -> None:
        """Mark feature as valid."""
        self.is_valid = True
        self.update_timestamp()

    def mark_invalid(self, errors: List[str]) -> None:
        """Mark feature as invalid with error messages."""
        self.is_valid = False
        self.validation_result = FeatureValidationResult(
            is_valid=False,
            errors=errors
        )
        self.update_timestamp()
