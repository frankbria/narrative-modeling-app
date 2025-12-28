# Visual Feature Builder

## Overview

The Visual Feature Builder is a drag-and-drop interface for creating custom features (derived columns) from existing dataset columns. Users can visually construct expressions using columns, operations, and functions, then preview and save them.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │   Palettes   │  │    Canvas    │  │   Preview Panel        │ │
│  │ - Columns    │  │  (ReactFlow) │  │ - Statistics           │ │
│  │ - Operations │  │  ┌───┐ ┌───┐ │  │ - Distribution         │ │
│  │ - Functions  │──▶│ [A]─┬▶[+]──▶│  │ - Sample Data          │ │
│  └──────────────┘  │  └───┘ │     │  │ - Validation           │ │
│                    │       ┌┴──┐  │  └────────────────────────┘ │
│                    │       [B] │  │                              │
│                    │       └───┘  │                              │
│                    └──────────────┘                              │
└────────────────────────────┬────────────────────────────────────┘
                             │ REST API
┌────────────────────────────▼────────────────────────────────────┐
│                         Backend                                  │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    Feature Router                            │ │
│  │  POST /features/preview  - Preview expression                │ │
│  │  POST /features/validate - Validate expression               │ │
│  │  POST /features          - Save feature                      │ │
│  │  GET  /features          - List features                     │ │
│  │  POST /features/:id/apply - Apply to dataset                 │ │
│  └──────────────────────────┬──────────────────────────────────┘ │
│                             │                                    │
│  ┌──────────────────────────▼──────────────────────────────────┐ │
│  │                Expression Evaluator                          │ │
│  │  - Safe evaluation (no eval())                               │ │
│  │  - Pandas/NumPy operations                                   │ │
│  │  - Type inference                                            │ │
│  │  - Validation                                                │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## API Endpoints

### Feature CRUD Operations

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/datasets/{dataset_id}/features` | POST | Create a new feature |
| `/api/v1/datasets/{dataset_id}/features` | GET | List all features for dataset |
| `/api/v1/datasets/{dataset_id}/features/{feature_id}` | GET | Get feature details |
| `/api/v1/datasets/{dataset_id}/features/{feature_id}` | PUT | Update feature |
| `/api/v1/datasets/{dataset_id}/features/{feature_id}` | DELETE | Delete feature |

### Preview & Validation

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/datasets/{dataset_id}/features/preview` | POST | Preview feature on sample data |
| `/api/v1/datasets/{dataset_id}/features/validate` | POST | Validate expression tree |
| `/api/v1/datasets/{dataset_id}/features/{feature_id}/apply` | POST | Apply feature to dataset |

### Metadata

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/feature-builder/operations` | GET | List available operations |
| `/api/v1/feature-builder/functions` | GET | List available functions |

## Expression Tree Format

Features are defined using an expression tree structure:

```json
{
  "node_id": "root-1",
  "node_type": "operation",
  "value": "add",
  "children": [
    {
      "node_id": "col-1",
      "node_type": "column",
      "value": "price",
      "children": []
    },
    {
      "node_id": "col-2",
      "node_type": "column",
      "value": "tax",
      "children": []
    }
  ],
  "parameters": {}
}
```

### Node Types

| Type | Description | Value Field | Children |
|------|-------------|-------------|----------|
| `column` | Reference to dataset column | Column name | None |
| `constant` | Literal value | Number/string | None |
| `operation` | Binary/unary operation | Operation type | 1-2 children |
| `function` | Transform function | Function type | 1 child |
| `conditional` | IF-THEN-ELSE | None | 3 children (condition, if_true, if_false) |

## Supported Operations

### Arithmetic
- `add` (+), `subtract` (-), `multiply` (*), `divide` (/)
- `modulo` (%), `power` (^)

### Comparison
- `equal` (==), `not_equal` (!=)
- `greater_than` (>), `less_than` (<)
- `greater_than_or_equal` (>=), `less_than_or_equal` (<=)

### Logical
- `and`, `or`, `not`

## Supported Functions

### Mathematical
- `abs`, `log`, `log10`, `sqrt`, `exp`
- `round` (with decimals parameter), `ceil`, `floor`

### Statistical (Column-level)
- `mean`, `median`, `std`, `min`, `max`, `sum`

### String
- `upper`, `lower`, `trim`, `length`

### Date
- `year`, `month`, `day`, `hour`, `weekday`

### Utility
- `to_numeric`, `to_string`
- `fill_null` (with fill_value parameter)
- `is_null`

## Data Models

### FeatureDefinition (MongoDB Document)

```python
class FeatureDefinition(Document):
    feature_id: str              # Unique identifier
    user_id: str                 # Owner
    dataset_id: str              # Associated dataset
    name: str                    # Feature name
    description: Optional[str]   # Description
    tags: List[str]              # Categorization tags
    expression_tree: ExpressionNode  # The formula
    formula_string: Optional[str]    # Human-readable formula
    input_columns: List[str]     # Columns used
    output_type: OutputType      # numeric/text/boolean/datetime
    is_valid: bool               # Validation status
    validation_result: Optional[dict]
    statistics: Optional[dict]
    canvas_state: Optional[dict] # UI state for ReactFlow
    created_at: datetime
    updated_at: datetime
```

## Frontend Components

### FeatureBuilder
Main container component with ReactFlow canvas, palettes, and preview panel.

### FeatureNode
Custom ReactFlow node for visualizing expression tree nodes. Different colors for each node type:
- Column: Blue
- Operation: Green
- Function: Orange
- Constant: Purple
- Conditional: Yellow

### Palettes
- **ColumnPalette**: Draggable columns grouped by type with search
- **OperationPalette**: Arithmetic, comparison, and logical operations
- **FunctionPalette**: Mathematical, statistical, string, date, and utility functions

### FeaturePreview
Statistics, distribution chart, and sample data table for preview results.

### FeatureMetadata
Modal for entering feature name, description, and tags.

### FeatureList
List of saved features with search, tag filtering, edit, delete, and duplicate actions.

## Expression Evaluator

The ExpressionEvaluator class safely evaluates expression trees using Pandas operations. Key features:

- **No eval()**: All operations use explicit Pandas/NumPy function mappings
- **Type Safety**: Validates column types and infers output types
- **Null Handling**: Proper NaN propagation
- **Error Handling**: Graceful handling of division by zero, log of negative, etc.

### Example Usage

```python
from app.services.expression_evaluator import ExpressionEvaluator
import pandas as pd

df = pd.DataFrame({'price': [100, 200], 'quantity': [5, 10]})

evaluator = ExpressionEvaluator(df)
tree = ExpressionNode(
    node_id='root',
    node_type=NodeType.OPERATION,
    value='multiply',
    children=[
        ExpressionNode(node_id='1', node_type=NodeType.COLUMN, value='price'),
        ExpressionNode(node_id='2', node_type=NodeType.COLUMN, value='quantity'),
    ]
)

result = evaluator.evaluate(tree)
# Returns: pd.Series([500, 2000])
```

## Testing

### Backend Tests
```bash
cd apps/backend && uv run pytest tests/test_services/test_expression_evaluator.py -v
```

35 test cases covering:
- Column evaluation
- Constant values
- Arithmetic operations
- Comparison operations
- Logical operations
- Mathematical functions
- Statistical functions
- String functions
- Date functions
- Conditional expressions
- Null handling
- Validation

### Frontend Tests
```bash
cd apps/frontend && npm test -- feature-builder
```

169 test cases covering all components:
- FeatureNode
- ColumnPalette
- OperationPalette
- FunctionPalette
- FeaturePreview
- FeatureMetadata
- FeatureList

## Security Considerations

1. **No eval()**: Expression evaluation uses explicit function mappings only
2. **Authentication**: All endpoints require valid auth token
3. **Authorization**: Users can only access their own features
4. **Input Validation**: Pydantic schemas validate all request data
5. **Column Validation**: Verifies columns exist in dataset before evaluation

## Performance Notes

- Preview operations use sampling (configurable, default 100 rows)
- Statistics calculated using NumPy for efficiency
- Expression trees cached in canvas_state for quick editing
- MongoDB indexes on (user_id, dataset_id) for efficient queries
