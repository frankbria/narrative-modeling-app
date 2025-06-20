"""
Recipe manager for saving and loading transformation pipelines
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
from pydantic import BaseModel, Field
from beanie import Document, PydanticObjectId
import logging

logger = logging.getLogger(__name__)


class TransformationStep(BaseModel):
    """A single transformation step in a recipe"""
    step_id: str
    transformation_type: str
    parameters: Dict[str, Any]
    description: Optional[str] = None
    order: int


class TransformationRecipe(Document):
    """A saved transformation recipe"""
    name: str
    description: Optional[str] = None
    user_id: str
    dataset_id: Optional[str] = None
    steps: List[TransformationStep]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_public: bool = False
    tags: List[str] = Field(default_factory=list)
    usage_count: int = 0
    rating: Optional[float] = None
    schema_snapshot: Optional[Dict[str, str]] = None  # Column types when recipe was created
    
    class Settings:
        name = "transformation_recipes"
        indexes = [
            [("user_id", 1)],
            [("is_public", 1)],
            [("tags", 1)],
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
    error_message: Optional[str] = None
    
    class Settings:
        name = "recipe_execution_history"
        indexes = [
            [("recipe_id", 1)],
            [("user_id", 1)],
            [("executed_at", -1)],
        ]


class RecipeManager:
    """Manages transformation recipes"""
    
    @staticmethod
    async def create_recipe(
        name: str,
        steps: List[Dict[str, Any]],
        user_id: str,
        description: Optional[str] = None,
        dataset_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        is_public: bool = False,
        schema_snapshot: Optional[Dict[str, str]] = None
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
    async def get_recipe(recipe_id: str) -> Optional[TransformationRecipe]:
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
    ) -> List[TransformationRecipe]:
        """Get all recipes for a user"""
        query = {"$or": [{"user_id": user_id}]}
        
        if include_public:
            query["$or"].append({"is_public": True})
        
        recipes = await TransformationRecipe.find(query).sort("-created_at").to_list()
        return recipes
    
    @staticmethod
    async def get_public_recipes(
        tags: Optional[List[str]] = None,
        limit: int = 50
    ) -> List[TransformationRecipe]:
        """Get public recipes, optionally filtered by tags"""
        query = {"is_public": True}
        
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
        updates: Dict[str, Any]
    ) -> Optional[TransformationRecipe]:
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
        error_message: Optional[str] = None
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
    async def get_popular_recipes(limit: int = 10) -> List[TransformationRecipe]:
        """Get most popular public recipes"""
        recipes = await TransformationRecipe.find({"is_public": True})\
            .sort("-usage_count")\
            .limit(limit)\
            .to_list()
        
        return recipes
    
    @staticmethod
    async def search_recipes(
        query: str,
        user_id: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> List[TransformationRecipe]:
        """Search recipes by name or description"""
        search_query = {
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