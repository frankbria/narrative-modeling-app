# Recipe System Documentation

## Overview

The Recipe System allows users to save, version, share, and reuse transformation pipelines. A recipe is a sequence of transformation steps that can be applied to datasets with compatible schemas.

**Key Features:**
- **Recipe Versioning** - Track changes with parent-child lineage
- **Compatibility Checking** - Verify recipe works with target dataset (80% threshold)
- **Recipe Sharing** - Share recipes with other users (independent copies)
- **Import/Export** - Save recipes as JSON for backup or distribution
- **Recipe Library** - Browse, search, and filter recipes with pagination

---

## Core Concepts

### Recipe
A saved sequence of transformation steps with metadata:
```python
{
    "id": "recipe_abc123",
    "name": "Clean Customer Data",
    "description": "Remove duplicates, handle missing values, normalize names",
    "user_id": "user_xyz789",
    "steps": [
        {"type": "remove_duplicates", "parameters": {...}},
        {"type": "fill_missing", "parameters": {...}},
        {"type": "normalize_text", "parameters": {...}}
    ],
    "version": 1,
    "parent_recipe_id": null,
    "tags": ["cleaning", "customer-data"],
    "is_public": false,
    "created_at": "2025-01-15T10:30:00Z"
}
```

### Recipe Versioning
Recipes use **parent-child lineage tracking**:
- Each version links to its parent via `parent_recipe_id`
- Version numbers auto-increment
- Full version history retrievable via traversal
- Changes documented in `version_notes`

```python
# Original recipe (version 1)
recipe_v1 = {"id": "r1", "version": 1, "parent_recipe_id": null}

# Create version 2
recipe_v2 = {"id": "r2", "version": 2, "parent_recipe_id": "r1"}

# Create version 3
recipe_v3 = {"id": "r3", "version": 3, "parent_recipe_id": "r2"}
```

### Compatibility Checking
Verifies a recipe can be applied to a dataset by comparing schemas:

**Compatibility Score Formula:**
```
score = (matching_columns / required_columns) * 100
```

**Thresholds:**
- ✅ **≥90%** - High compatibility (green badge)
- ⚠️ **70-89%** - Medium compatibility (yellow badge)
- ❌ **<70%** - Low compatibility (red badge)

**Checks:**
- Missing columns in dataset
- Data type mismatches (e.g., recipe expects `int`, dataset has `str`)
- Provides actionable suggestions

### Recipe Sharing
Sharing creates an **independent copy** in the recipient's account:
- Original recipe can be modified without affecting shared copy
- Recipient can update their copy to sync with original (opt-in)
- Shared recipes tracked separately in `SharedRecipe` collection

### Import/Export
**Export Format (JSON v1.0):**
```json
{
    "format_version": "1.0",
    "recipe": {
        "name": "Clean Sales Data",
        "description": "Standard cleaning pipeline",
        "steps": [...],
        "tags": ["cleaning", "sales"],
        "metadata": {
            "author": "Data Team",
            "created_at": "2025-01-15T10:30:00Z"
        }
    }
}
```

**Import Behavior:**
- Creates new recipe (doesn't overwrite)
- Resets version to 1 (breaks parent lineage)
- Optional name override

---

## API Reference

### Base URL
```
http://localhost:8000/api/v1/transformations
```

### Authentication
All endpoints require authentication via Bearer token:
```
Authorization: Bearer <token>
```

---

### Endpoints

#### 1. Check Recipe Compatibility
**POST** `/recipes/{recipe_id}/check-compatibility`

Verify if a recipe is compatible with a dataset schema.

**Request:**
```json
{
    "dataset_schema": {
        "customer_id": "int64",
        "name": "string",
        "email": "string",
        "age": "int64"
    }
}
```

**Response (200 OK):**
```json
{
    "is_compatible": true,
    "missing_columns": [],
    "type_mismatches": [],
    "warnings": ["Column 'phone' is optional but not present"],
    "suggestions": [],
    "compatibility_score": 95.5
}
```

**Error Responses:**
- `404` - Recipe not found
- `400` - Invalid schema format

---

#### 2. Create Recipe Version
**POST** `/recipes/{recipe_id}/versions`

Create a new version of an existing recipe.

**Request:**
```json
{
    "changes": {
        "steps": [...],
        "description": "Updated to handle new data format"
    },
    "version_notes": "Added email validation step"
}
```

**Response (200 OK):**
```json
{
    "id": "recipe_new_version",
    "name": "Clean Customer Data",
    "version": 2,
    "parent_recipe_id": "recipe_original",
    ...
}
```

**Authorization:**
- Only recipe owner can create versions

---

#### 3. Get Version History
**GET** `/recipes/{recipe_id}/versions`

Retrieve complete version history for a recipe.

**Response (200 OK):**
```json
{
    "versions": [
        {
            "id": "r3",
            "version": 3,
            "parent_recipe_id": "r2",
            "created_at": "2025-01-17T14:00:00Z",
            "version_notes": "Added data quality checks"
        },
        {
            "id": "r2",
            "version": 2,
            "parent_recipe_id": "r1",
            "created_at": "2025-01-16T10:00:00Z",
            "version_notes": "Updated normalization rules"
        },
        {
            "id": "r1",
            "version": 1,
            "parent_recipe_id": null,
            "created_at": "2025-01-15T09:00:00Z"
        }
    ],
    "total_versions": 3
}
```

---

#### 4. Duplicate Recipe
**POST** `/recipes/{recipe_id}/duplicate`

Create a copy of an existing recipe.

**Request:**
```json
{
    "new_name": "Clean Customer Data (Copy)"
}
```

**Response (200 OK):**
```json
{
    "id": "recipe_duplicate",
    "name": "Clean Customer Data (Copy)",
    "version": 1,
    "parent_recipe_id": null,
    ...
}
```

**Notes:**
- Creates independent copy (version reset to 1)
- User becomes owner of duplicate

---

#### 5. Share Recipe
**POST** `/recipes/{recipe_id}/share`

Share a recipe with another user.

**Request:**
```json
{
    "target_user_id": "user_recipient_123"
}
```

**Response (200 OK):**
```json
{
    "shared_recipe_id": "shared_abc789",
    "target_user_id": "user_recipient_123",
    "shared_at": "2025-01-15T10:30:00Z",
    "message": "Recipe shared successfully"
}
```

**Authorization:**
- Only recipe owner or public recipes can be shared

**Behavior:**
- Creates independent copy in `SharedRecipe` collection
- Recipient can modify without affecting original

---

#### 6. Get Shared Recipes
**GET** `/recipes/shared`

Retrieve all recipes shared with the current user.

**Response (200 OK):**
```json
{
    "shared_recipes": [
        {
            "id": "shared_abc789",
            "name": "Clean Sales Data",
            "description": "Standard cleaning pipeline",
            "original_recipe_id": "recipe_original",
            "original_owner_id": "user_xyz789",
            "shared_at": "2025-01-15T10:30:00Z",
            "version": 2,
            "tags": ["cleaning", "sales"],
            "steps_count": 5
        }
    ],
    "total": 1
}
```

---

#### 7. Export Recipe as JSON
**GET** `/recipes/{recipe_id}/export/json`

Export a recipe in JSON format for backup or sharing.

**Response (200 OK):**
```json
{
    "format_version": "1.0",
    "recipe": {
        "name": "Clean Customer Data",
        "description": "Remove duplicates and normalize",
        "steps": [...],
        "tags": ["cleaning", "customer"],
        "metadata": {
            "version": 2,
            "created_at": "2025-01-15T10:30:00Z"
        }
    }
}
```

**Authorization:**
- Recipe must be owned by user or be public

---

#### 8. Import Recipe
**POST** `/recipes/import`

Import a recipe from JSON data.

**Request:**
```json
{
    "json_data": {
        "format_version": "1.0",
        "recipe": {...}
    },
    "name_override": "Imported Sales Cleaning Recipe"
}
```

**Response (200 OK):**
```json
{
    "id": "recipe_imported",
    "name": "Imported Sales Cleaning Recipe",
    "version": 1,
    ...
}
```

**Validation:**
- Checks format version compatibility
- Validates recipe structure
- Resets version to 1 on import

---

## Database Models

### TransformationRecipe
```python
class TransformationRecipe(Document):
    name: str
    description: str
    user_id: str
    steps: List[RecipeStep]
    version: int = 1
    parent_recipe_id: Optional[PydanticObjectId] = None
    is_public: bool = False
    tags: List[str] = []
    usage_count: int = 0
    rating: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = {}

    class Settings:
        name = "transformation_recipes"
        indexes = [
            [("name", "text"), ("description", "text")],
            [("created_at", -1)],
            [("parent_recipe_id", 1)]
        ]
```

### SharedRecipe
```python
class SharedRecipe(Document):
    user_id: str  # Recipient
    original_recipe_id: PydanticObjectId
    original_owner_id: str
    shared_at: datetime
    name: str
    description: str
    steps: List[RecipeStep]
    version: int
    tags: List[str]

    class Settings:
        name = "shared_recipes"
        indexes = [
            [("user_id", 1), ("shared_at", -1)]
        ]
```

---

## Service Layer

### RecipeManager
Primary service class for recipe operations.

**Key Methods:**
```python
async def create_recipe(recipe_data: Dict, user_id: str) -> TransformationRecipe
async def get_recipe(recipe_id: str, user_id: str) -> TransformationRecipe
async def list_recipes(user_id: str, **filters) -> List[TransformationRecipe]
async def delete_recipe(recipe_id: str, user_id: str) -> None

# Versioning
async def create_version(recipe_id: str, user_id: str, changes: Dict, notes: str) -> TransformationRecipe
async def get_version_history(recipe_id: str) -> List[TransformationRecipe]

# Sharing
async def share_recipe(recipe_id: str, owner_id: str, target_user_id: str) -> SharedRecipe
async def get_shared_recipes(user_id: str) -> List[SharedRecipe]
async def update_shared_recipe(shared_id: str, user_id: str, original_id: str) -> SharedRecipe

# Import/Export
def export_recipe_to_json(recipe: TransformationRecipe) -> Dict
async def import_recipe_from_json(json_data: Dict, user_id: str, name_override: str = None) -> TransformationRecipe

# Utility
async def duplicate_recipe(recipe_id: str, user_id: str, new_name: str) -> TransformationRecipe
```

### RecipeCompatibilityChecker
Handles schema compatibility validation.

```python
class RecipeCompatibilityChecker:
    @staticmethod
    async def check_compatibility(
        recipe_id: str,
        dataset_schema: Dict[str, str]
    ) -> CompatibilityReport
```

**CompatibilityReport:**
```python
{
    "is_compatible": bool,
    "missing_columns": List[str],
    "type_mismatches": List[Dict],
    "warnings": List[str],
    "suggestions": List[str],
    "compatibility_score": float  # 0-100
}
```

---

## Testing

### Unit Tests
**File:** `tests/test_services/test_recipe_manager_enhancement.py`

**Coverage:**
- Recipe compatibility checking (6 tests)
- Recipe versioning (1 test)
- Recipe duplication (1 test)
- Recipe sharing (3 tests)
- Import/export (7 tests)

**Total:** 18 unit tests

### Integration Tests
**File:** `tests/test_api/test_recipe_endpoints.py`

**Coverage:**
- All 8 recipe API endpoints
- Authentication and authorization
- Error handling (404, 400, 403)
- Request/response schema validation

**Total:** 18 integration tests

### Frontend Tests
**Files:**
- `__tests__/components/recipes/*.test.tsx` (144 tests)
- `e2e/recipes/recipe-management.spec.ts` (20+ scenarios)

**Coverage:** 79.66% code coverage

### Running Tests

**Backend:**
```bash
cd apps/backend
uv run pytest tests/test_services/test_recipe_manager_enhancement.py -v
uv run pytest tests/test_api/test_recipe_endpoints.py -v
```

**Frontend:**
```bash
cd apps/frontend
npm test -- __tests__/components/recipes
npx playwright test e2e/recipes/recipe-management.spec.ts
```

---

## Usage Examples

### Example 1: Check Compatibility
```python
from app.services.transformation_engine.recipe_manager import RecipeCompatibilityChecker

dataset_schema = {
    "customer_id": "int64",
    "name": "string",
    "email": "string"
}

report = await RecipeCompatibilityChecker.check_compatibility(
    recipe_id="recipe_abc123",
    dataset_schema=dataset_schema
)

if report.is_compatible:
    print(f"Compatible! Score: {report.compatibility_score}%")
else:
    print(f"Not compatible. Missing: {report.missing_columns}")
```

### Example 2: Create Recipe Version
```python
from app.services.transformation_engine.recipe_manager import RecipeManager

manager = RecipeManager()

new_version = await manager.create_version(
    recipe_id="recipe_abc123",
    user_id="user_xyz789",
    changes={
        "steps": [...],
        "description": "Updated for new data format"
    },
    version_notes="Added email validation step"
)

print(f"Created version {new_version.version}")
```

### Example 3: Share Recipe
```python
shared_recipe = await manager.share_recipe(
    recipe_id="recipe_abc123",
    owner_id="user_xyz789",
    target_user_id="user_recipient_456"
)

print(f"Shared recipe ID: {shared_recipe.id}")
```

### Example 4: Export/Import
```python
# Export
json_data = manager.export_recipe_to_json(recipe)
with open("recipe_backup.json", "w") as f:
    json.dump(json_data, f, indent=2)

# Import
with open("recipe_backup.json", "r") as f:
    json_data = json.load(f)

imported_recipe = await manager.import_recipe_from_json(
    json_data=json_data,
    user_id="user_new_owner",
    name_override="Imported Recipe"
)
```

---

## Best Practices

### 1. Recipe Naming
- Use descriptive names (e.g., "Clean Customer Data" not "Recipe 1")
- Include data type or domain (e.g., "Sales Data Cleaning")
- Keep under 50 characters

### 2. Versioning
- Create versions for significant changes only
- Document changes in `version_notes`
- Consider backward compatibility

### 3. Sharing
- Share only tested, stable recipes
- Document any prerequisites or assumptions
- Use descriptive names and descriptions

### 4. Compatibility
- Always check compatibility before applying recipes
- Review warnings and suggestions
- Test on sample data first

### 5. Tags
- Use consistent tag naming (lowercase, hyphenated)
- Common tags: `cleaning`, `feature-engineering`, `validation`
- Limit to 3-5 relevant tags per recipe

---

## Troubleshooting

### "Recipe not compatible" error
**Cause:** Missing columns or type mismatches
**Solution:** Check compatibility report for missing columns and suggestions

### "Unauthorized to create version" error
**Cause:** User doesn't own the recipe
**Solution:** Duplicate recipe first, then create versions

### Import fails with "Invalid format"
**Cause:** JSON format doesn't match v1.0 specification
**Solution:** Verify `format_version` field and recipe structure

### Shared recipe not appearing
**Cause:** Recipe wasn't successfully shared
**Solution:** Check share endpoint response and verify target user ID

---

## Future Enhancements

- **Multi-user sharing** - Share with multiple users at once
- **Recipe templates** - Pre-built recipes for common tasks
- **Recipe marketplace** - Public recipe exchange
- **Automated testing** - Test recipes against sample datasets
- **Recipe analytics** - Track usage patterns and success rates
- **Recipe recommendations** - Suggest recipes based on dataset characteristics

---

**Last Updated:** 2025-01-18
**Version:** 1.0
**Maintained By:** Development Team
