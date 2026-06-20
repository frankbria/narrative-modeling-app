"""
Recipe manager for saving and loading transformation pipelines
"""
import logging
from datetime import datetime
from typing import Any

from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TransformationStep(BaseModel):
    """A single transformation step in a recipe"""
    step_id: str
    transformation_type: str
    parameters: dict[str, Any]
    description: str | None = None
    order: int


class TransformationRecipe(Document):
    """A saved transformation recipe"""
    name: str
    description: str | None = None
    user_id: str
    dataset_id: str | None = None
    steps: list[TransformationStep]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_public: bool = False
    tags: list[str] = Field(default_factory=list)
    usage_count: int = 0
    rating: float | None = None
    schema_snapshot: dict[str, str] | None = None  # Column types when recipe was created

    # Versioning fields
    version: int = 1
    parent_recipe_id: PydanticObjectId | None = None

    # Metadata for creator and tracking
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Settings:
        name = "transformation_recipes"
        indexes = [
            [("user_id", 1)],
            [("is_public", 1)],
            [("tags", 1)],
            [("name", "text"), ("description", "text")],  # Text search index
            [("created_at", -1)],  # Chronological sorting
            [("parent_recipe_id", 1)],  # Version lineage queries
        ]


class RecipeExecutionHistory(Document):
    """History of recipe executions"""
    recipe_id: PydanticObjectId
    user_id: str
    dataset_id: str
    executed_at: datetime = Field(default_factory=datetime.utcnow)
    success: bool
    rows_affected: int
    execution_time_ms: int
    error_message: str | None = None

    class Settings:
        name = "recipe_execution_history"
        indexes = [
            [("recipe_id", 1)],
            [("user_id", 1)],
            [("executed_at", -1)],
        ]


class SharedRecipe(Document):
    """Independent copy of a shared recipe (not linked to original)"""
    name: str
    description: str | None = None
    user_id: str  # User who received the shared recipe
    original_recipe_id: PydanticObjectId  # Reference to original recipe
    original_owner_id: str  # Original creator
    steps: list[TransformationStep]
    shared_at: datetime = Field(default_factory=datetime.utcnow)
    tags: list[str] = Field(default_factory=list)
    schema_snapshot: dict[str, str] | None = None
    version: int = 1
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Settings:
        name = "shared_recipes"
        indexes = [
            [("user_id", 1)],  # Find recipes shared with user
            [("original_recipe_id", 1)],  # Track shared copies
            [("shared_at", -1)],  # Chronological
        ]


class CompatibilityReport(BaseModel):
    """Report on recipe-dataset compatibility"""
    is_compatible: bool
    missing_columns: list[str] = Field(default_factory=list)
    type_mismatches: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    compatibility_score: float = Field(ge=0.0, le=100.0)  # 0-100%


class RecipeCompatibilityChecker:
    """Checks compatibility between recipes and datasets"""

    @staticmethod
    async def check_compatibility(
        recipe_id: str,
        dataset_schema: dict[str, str]
    ) -> CompatibilityReport:
        """
        Check if recipe can be applied to dataset.

        Args:
            recipe_id: Recipe to check
            dataset_schema: Target dataset's column schema {column_name: type}

        Returns:
            Compatibility report with score, warnings, and suggestions
        """
        try:
            recipe = await TransformationRecipe.get(PydanticObjectId(recipe_id))
            if not recipe:
                return CompatibilityReport(
                    is_compatible=False,
                    warnings=["Recipe not found"],
                    compatibility_score=0.0
                )

            recipe_schema = recipe.schema_snapshot or {}
            missing_columns = []
            type_mismatches = []
            warnings = []
            suggestions = []

            # Check each required column from recipe
            for col_name, expected_type in recipe_schema.items():
                if col_name not in dataset_schema:
                    missing_columns.append(col_name)
                    suggestions.append(
                        f"Column '{col_name}' is missing. "
                        f"Consider renaming a similar column or removing steps using this column."
                    )
                elif dataset_schema[col_name] != expected_type:
                    type_mismatches.append({
                        "column": col_name,
                        "expected": expected_type,
                        "actual": dataset_schema[col_name]
                    })
                    warnings.append(
                        f"Column '{col_name}' type mismatch: "
                        f"expected {expected_type}, got {dataset_schema[col_name]}"
                    )

            # Calculate compatibility score
            if not recipe_schema:
                # No schema snapshot, assume compatible but warn
                compatibility_score = 100.0
                warnings.append("Recipe has no schema snapshot - compatibility cannot be fully verified")
            else:
                total_cols = len(recipe_schema)
                matched_cols = total_cols - len(missing_columns) - len(type_mismatches)
                compatibility_score = (matched_cols / total_cols * 100) if total_cols > 0 else 0.0

            # Determine overall compatibility
            is_compatible = compatibility_score >= 80.0  # 80% threshold

            if not is_compatible and compatibility_score >= 50.0:
                suggestions.append(
                    "Partial compatibility detected. "
                    "You may need to modify the recipe or adapt your dataset."
                )

            return CompatibilityReport(
                is_compatible=is_compatible,
                missing_columns=missing_columns,
                type_mismatches=type_mismatches,
                warnings=warnings,
                suggestions=suggestions,
                compatibility_score=round(compatibility_score, 1)
            )

        except Exception as e:
            logger.error(f"Error checking compatibility: {str(e)}")
            return CompatibilityReport(
                is_compatible=False,
                warnings=[f"Error checking compatibility: {str(e)}"],
                compatibility_score=0.0
            )


class RecipeManager:
    """Manages transformation recipes"""
    
    @staticmethod
    async def create_recipe(
        name: str,
        steps: list[dict[str, Any]],
        user_id: str,
        description: str | None = None,
        dataset_id: str | None = None,
        tags: list[str] | None = None,
        is_public: bool = False,
        schema_snapshot: dict[str, str] | None = None
    ) -> TransformationRecipe:
        """Create a new transformation recipe"""
        
        # Convert steps to TransformationStep objects
        transformation_steps = []
        for i, step in enumerate(steps):
            transformation_steps.append(
                TransformationStep(
                    step_id=f"step_{i+1}",
                    transformation_type=step['type'],
                    parameters=step['parameters'],
                    description=step.get('description'),
                    order=i
                )
            )
        
        recipe = TransformationRecipe(
            name=name,
            description=description,
            user_id=user_id,
            dataset_id=dataset_id,
            steps=transformation_steps,
            is_public=is_public,
            tags=tags or [],
            schema_snapshot=schema_snapshot
        )
        
        await recipe.save()
        logger.info(f"Created recipe '{name}' for user {user_id}")
        
        return recipe
    
    @staticmethod
    async def get_recipe(recipe_id: str) -> TransformationRecipe | None:
        """Get a recipe by ID"""
        try:
            recipe = await TransformationRecipe.get(PydanticObjectId(recipe_id))
            return recipe
        except Exception as e:
            logger.error(f"Error getting recipe {recipe_id}: {str(e)}")
            return None
    
    @staticmethod
    async def get_user_recipes(
        user_id: str,
        include_public: bool = True
    ) -> list[TransformationRecipe]:
        """Get all recipes for a user"""
        query: dict[str, Any] = {"$or": [{"user_id": user_id}]}

        if include_public:
            query["$or"].append({"is_public": True})
        
        recipes = await TransformationRecipe.find(query).sort("-created_at").to_list()
        return recipes
    
    @staticmethod
    async def get_public_recipes(
        tags: list[str] | None = None,
        limit: int = 50
    ) -> list[TransformationRecipe]:
        """Get public recipes, optionally filtered by tags"""
        query: dict[str, Any] = {"is_public": True}

        if tags:
            query["tags"] = {"$in": tags}
        
        recipes = await TransformationRecipe.find(query)\
            .sort([("rating", -1), ("usage_count", -1)])\
            .limit(limit)\
            .to_list()
        
        return recipes
    
    @staticmethod
    async def update_recipe(
        recipe_id: str,
        user_id: str,
        updates: dict[str, Any]
    ) -> TransformationRecipe | None:
        """Update a recipe"""
        try:
            recipe = await TransformationRecipe.get(PydanticObjectId(recipe_id))
            
            if not recipe or recipe.user_id != user_id:
                logger.error(f"Recipe {recipe_id} not found or unauthorized")
                return None
            
            # Update allowed fields
            allowed_fields = ['name', 'description', 'steps', 'tags', 'is_public']
            for field in allowed_fields:
                if field in updates:
                    setattr(recipe, field, updates[field])
            
            recipe.updated_at = datetime.utcnow()
            await recipe.save()
            
            return recipe
            
        except Exception as e:
            logger.error(f"Error updating recipe {recipe_id}: {str(e)}")
            return None
    
    @staticmethod
    async def delete_recipe(recipe_id: str, user_id: str) -> bool:
        """Delete a recipe"""
        try:
            recipe = await TransformationRecipe.get(PydanticObjectId(recipe_id))
            
            if not recipe or recipe.user_id != user_id:
                return False
            
            await recipe.delete()
            logger.info(f"Deleted recipe {recipe_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting recipe {recipe_id}: {str(e)}")
            return False
    
    @staticmethod
    async def record_execution(
        recipe_id: str,
        user_id: str,
        dataset_id: str,
        success: bool,
        rows_affected: int,
        execution_time_ms: int,
        error_message: str | None = None
    ) -> None:
        """Record recipe execution"""
        history = RecipeExecutionHistory(
            recipe_id=PydanticObjectId(recipe_id),
            user_id=user_id,
            dataset_id=dataset_id,
            success=success,
            rows_affected=rows_affected,
            execution_time_ms=execution_time_ms,
            error_message=error_message
        )
        
        await history.save()
        
        # Update recipe usage count
        if success:
            recipe = await TransformationRecipe.get(PydanticObjectId(recipe_id))
            if recipe:
                recipe.usage_count += 1
                await recipe.save()
    
    @staticmethod
    async def get_popular_recipes(limit: int = 10) -> list[TransformationRecipe]:
        """Get most popular public recipes"""
        recipes = await TransformationRecipe.find({"is_public": True})\
            .sort("-usage_count")\
            .limit(limit)\
            .to_list()
        
        return recipes
    
    @staticmethod
    async def search_recipes(
        query: str,
        user_id: str | None = None,
        tags: list[str] | None = None
    ) -> list[TransformationRecipe]:
        """Search recipes by name or description"""
        search_query: dict[str, Any] = {
            "$or": [
                {"name": {"$regex": query, "$options": "i"}},
                {"description": {"$regex": query, "$options": "i"}}
            ]
        }

        # Add user filter
        if user_id:
            search_query["$and"] = [
                {"$or": [{"user_id": user_id}, {"is_public": True}]}
            ]
        else:
            search_query["is_public"] = True

        # Add tag filter
        if tags:
            if "$and" in search_query:
                search_query["$and"].append({"tags": {"$in": tags}})
            else:
                search_query["tags"] = {"$in": tags}
        
        recipes = await TransformationRecipe.find(search_query)\
            .sort("-rating")\
            .limit(50)\
            .to_list()
        
        return recipes
    
    @staticmethod
    async def create_version(
        recipe_id: str,
        user_id: str,
        changes: dict[str, Any],
        version_notes: str | None = None
    ) -> TransformationRecipe | None:
        """
        Create a new version of a recipe.

        Args:
            recipe_id: Original recipe ID
            user_id: User creating the version
            changes: Changes to apply
            version_notes: Optional notes about this version

        Returns:
            New recipe version or None if failed
        """
        try:
            original = await TransformationRecipe.get(PydanticObjectId(recipe_id))

            if not original or original.user_id != user_id:
                logger.error(f"Recipe {recipe_id} not found or unauthorized")
                return None

            # Create new recipe with incremented version
            new_version = TransformationRecipe(
                name=changes.get('name', original.name),
                description=changes.get('description', original.description),
                user_id=user_id,
                dataset_id=changes.get('dataset_id', original.dataset_id),
                steps=changes.get('steps', original.steps),
                is_public=changes.get('is_public', original.is_public),
                tags=changes.get('tags', original.tags),
                schema_snapshot=changes.get('schema_snapshot', original.schema_snapshot),
                version=original.version + 1,
                parent_recipe_id=original.id,
                metadata={
                    **original.metadata,
                    'version_notes': version_notes,
                    'versioned_from': str(original.id),
                    'created_from_version': original.version
                }
            )

            await new_version.save()
            logger.info(f"Created version {new_version.version} of recipe {recipe_id}")

            return new_version

        except Exception as e:
            logger.error(f"Error creating recipe version: {str(e)}")
            return None

    @staticmethod
    async def get_version_history(recipe_id: str) -> list[TransformationRecipe]:
        """
        Get all versions of a recipe in chronological order.

        Args:
            recipe_id: Recipe ID (can be any version)

        Returns:
            List of recipe versions
        """
        try:
            # Get the recipe to find root
            recipe = await TransformationRecipe.get(PydanticObjectId(recipe_id))
            if not recipe:
                return []

            # Find root by walking up parent chain
            current = recipe
            while current.parent_recipe_id:
                parent = await TransformationRecipe.get(current.parent_recipe_id)
                if not parent:
                    break
                current = parent
            root_id = current.id

            # Get all versions by collecting entire tree
            versions = []
            to_process = [root_id]
            seen = set()

            while to_process:
                current_id = to_process.pop(0)
                if current_id in seen:
                    continue
                seen.add(current_id)

                recipe_obj = await TransformationRecipe.get(current_id)
                if recipe_obj:
                    versions.append(recipe_obj)

                    # Find children of this recipe
                    children = await TransformationRecipe.find(
                        {"parent_recipe_id": current_id}
                    ).to_list()

                    for child in children:
                        to_process.append(child.id)

            return sorted(versions, key=lambda r: r.version)

        except Exception as e:
            logger.error(f"Error getting version history: {str(e)}")
            return []

    @staticmethod
    async def duplicate_recipe(
        recipe_id: str,
        user_id: str,
        new_name: str
    ) -> TransformationRecipe | None:
        """
        Duplicate a recipe as a template for the user.

        Args:
            recipe_id: Recipe to duplicate
            user_id: User creating the duplicate
            new_name: Name for the duplicate

        Returns:
            Duplicated recipe or None if failed
        """
        try:
            original = await TransformationRecipe.get(PydanticObjectId(recipe_id))
            if not original:
                return None

            duplicate = TransformationRecipe(
                name=new_name,
                description=f"Duplicated from: {original.name}",
                user_id=user_id,
                dataset_id=None,  # Don't copy dataset reference
                steps=original.steps,
                is_public=False,  # Duplicates start as private
                tags=original.tags,
                schema_snapshot=original.schema_snapshot,
                version=1,
                metadata={
                    'duplicated_from': str(original.id),
                    'original_name': original.name,
                    'original_owner': original.user_id
                }
            )

            await duplicate.save()
            logger.info(f"Duplicated recipe {recipe_id} as '{new_name}' for user {user_id}")

            return duplicate

        except Exception as e:
            logger.error(f"Error duplicating recipe: {str(e)}")
            return None

    @staticmethod
    async def share_recipe(
        recipe_id: str,
        owner_id: str,
        target_user_id: str
    ) -> SharedRecipe | None:
        """
        Share a recipe with another user (creates independent copy).

        Args:
            recipe_id: Recipe to share
            owner_id: Recipe owner (for authorization)
            target_user_id: User to share with

        Returns:
            Shared recipe copy or None if failed
        """
        try:
            original = await TransformationRecipe.get(PydanticObjectId(recipe_id))

            if not original or original.user_id != owner_id:
                logger.error(f"Recipe {recipe_id} not found or unauthorized")
                return None

            # Create independent copy for target user
            shared = SharedRecipe(
                name=original.name,
                description=original.description,
                user_id=target_user_id,
                original_recipe_id=original.id,
                original_owner_id=owner_id,
                steps=original.steps,
                tags=original.tags,
                schema_snapshot=original.schema_snapshot,
                version=original.version,
                metadata={
                    'shared_from': str(original.id),
                    'shared_by': owner_id,
                    'original_name': original.name
                }
            )

            await shared.save()
            logger.info(f"Shared recipe {recipe_id} with user {target_user_id}")

            return shared

        except Exception as e:
            logger.error(f"Error sharing recipe: {str(e)}")
            return None

    @staticmethod
    async def get_shared_recipes(user_id: str) -> list[SharedRecipe]:
        """
        Get all recipes shared with a user.

        Args:
            user_id: User to get shared recipes for

        Returns:
            List of shared recipes
        """
        try:
            shared_recipes = await SharedRecipe.find(
                {"user_id": user_id}
            ).sort("-shared_at").to_list()

            return shared_recipes

        except Exception as e:
            logger.error(f"Error getting shared recipes: {str(e)}")
            return []

    @staticmethod
    async def update_shared_recipe(
        shared_recipe_id: str,
        user_id: str,
        original_recipe_id: str
    ) -> SharedRecipe | None:
        """
        Update a shared recipe to match current version of original.

        Args:
            shared_recipe_id: Shared recipe to update
            user_id: User who owns the shared copy
            original_recipe_id: Original recipe to sync from

        Returns:
            Updated shared recipe or None if failed
        """
        try:
            shared = await SharedRecipe.get(PydanticObjectId(shared_recipe_id))
            original = await TransformationRecipe.get(PydanticObjectId(original_recipe_id))

            if not shared or not original:
                return None

            if shared.user_id != user_id:
                logger.error(f"Unauthorized access to shared recipe {shared_recipe_id}")
                return None

            # Update shared copy with current original version
            shared.name = original.name
            shared.description = original.description
            shared.steps = original.steps
            shared.tags = original.tags
            shared.schema_snapshot = original.schema_snapshot
            shared.version = original.version
            shared.metadata['last_synced'] = datetime.utcnow().isoformat()

            await shared.save()
            logger.info(f"Updated shared recipe {shared_recipe_id} from original {original_recipe_id}")

            return shared

        except Exception as e:
            logger.error(f"Error updating shared recipe: {str(e)}")
            return None

    @staticmethod
    def export_recipe_to_json(recipe: TransformationRecipe) -> dict[str, Any]:
        """
        Export recipe as JSON for portability.

        Args:
            recipe: Recipe to export

        Returns:
            JSON-serializable dictionary
        """
        return {
            "format_version": "1.0",
            "recipe": {
                "name": recipe.name,
                "description": recipe.description,
                "version": recipe.version,
                "tags": recipe.tags,
                "schema_snapshot": recipe.schema_snapshot,
                "steps": [
                    {
                        "step_id": step.step_id,
                        "transformation_type": step.transformation_type,
                        "parameters": step.parameters,
                        "description": step.description,
                        "order": step.order
                    }
                    for step in recipe.steps
                ],
                "metadata": {
                    **recipe.metadata,
                    "exported_at": datetime.utcnow().isoformat(),
                    "exported_from_version": recipe.version
                }
            }
        }

    @staticmethod
    async def import_recipe_from_json(
        json_data: dict[str, Any],
        user_id: str,
        name_override: str | None = None
    ) -> TransformationRecipe | None:
        """
        Import recipe from JSON.

        Args:
            json_data: JSON data (from export_recipe_to_json)
            user_id: User importing the recipe
            name_override: Optional name override

        Returns:
            Imported recipe or None if failed
        """
        try:
            # Validate format
            if json_data.get("format_version") != "1.0":
                logger.error("Unsupported recipe format version")
                return None

            recipe_data = json_data.get("recipe", {})

            # Convert steps
            steps = []
            for step_data in recipe_data.get("steps", []):
                steps.append(TransformationStep(
                    step_id=step_data["step_id"],
                    transformation_type=step_data["transformation_type"],
                    parameters=step_data["parameters"],
                    description=step_data.get("description"),
                    order=step_data["order"]
                ))

            # Create recipe
            imported = TransformationRecipe(
                name=name_override or recipe_data.get("name", "Imported Recipe"),
                description=recipe_data.get("description"),
                user_id=user_id,
                steps=steps,
                tags=recipe_data.get("tags", []),
                schema_snapshot=recipe_data.get("schema_snapshot"),
                version=1,  # Start at version 1 for imports
                metadata={
                    **recipe_data.get("metadata", {}),
                    "imported_at": datetime.utcnow().isoformat(),
                    "imported_by": user_id
                }
            )

            await imported.save()
            logger.info(f"Imported recipe '{imported.name}' for user {user_id}")

            return imported

        except Exception as e:
            logger.error(f"Error importing recipe: {str(e)}")
            return None

    @staticmethod
    def export_recipe_to_code(recipe: TransformationRecipe, language: str = "python") -> str:
        """Export recipe to executable code"""
        if language == "python":
            code = "# Auto-generated transformation code\n"
            code += "import pandas as pd\n"
            code += "import numpy as np\n\n"
            code += f"# Recipe: {recipe.name}\n"
            if recipe.description:
                code += f"# Description: {recipe.description}\n"
            code += f"# Created: {recipe.created_at}\n\n"
            
            code += "def apply_transformations(df):\n"
            code += "    df_transformed = df.copy()\n\n"
            
            for step in recipe.steps:
                code += f"    # Step {step.order + 1}: {step.transformation_type}\n"
                
                # Generate code based on transformation type
                if step.transformation_type == "remove_duplicates":
                    subset = step.parameters.get('subset')
                    keep = step.parameters.get('keep', 'first')
                    if subset:
                        code += f"    df_transformed = df_transformed.drop_duplicates(subset={subset}, keep='{keep}')\n"
                    else:
                        code += f"    df_transformed = df_transformed.drop_duplicates(keep='{keep}')\n"
                
                elif step.transformation_type == "fill_missing":
                    columns = step.parameters.get('columns', [])
                    value = step.parameters.get('value')
                    method = step.parameters.get('method')
                    
                    if columns:
                        for col in columns:
                            if value is not None:
                                code += f"    df_transformed['{col}'] = df_transformed['{col}'].fillna({repr(value)})\n"
                            elif method:
                                if method in ['mean', 'median']:
                                    code += f"    df_transformed['{col}'] = df_transformed['{col}'].fillna(df_transformed['{col}'].{method}())\n"
                                elif method == 'mode':
                                    code += f"    df_transformed['{col}'] = df_transformed['{col}'].fillna(df_transformed['{col}'].mode()[0] if len(df_transformed['{col}'].mode()) > 0 else np.nan)\n"
                                else:
                                    code += f"    df_transformed['{col}'] = df_transformed['{col}'].fillna(method='{method}')\n"
                
                elif step.transformation_type == "trim_whitespace":
                    columns = step.parameters.get('columns', [])
                    if columns:
                        for col in columns:
                            code += f"    df_transformed['{col}'] = df_transformed['{col}'].astype(str).str.strip()\n"
                    else:
                        code += "    # Trim whitespace from all string columns\n"
                        code += "    string_columns = df_transformed.select_dtypes(include=['object']).columns\n"
                        code += "    for col in string_columns:\n"
                        code += "        df_transformed[col] = df_transformed[col].astype(str).str.strip()\n"
                
                code += "\n"
            
            code += "    return df_transformed\n"
            
            return code
        
        else:
            raise NotImplementedError(f"Code generation for {language} not implemented")