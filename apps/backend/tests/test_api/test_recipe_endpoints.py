"""
Integration Tests for Enhanced Recipe API Endpoints

Tests cover all 8 new API endpoints from the recipe system enhancement:
1. POST /recipes/{recipe_id}/check-compatibility
2. POST /recipes/{recipe_id}/versions
3. GET /recipes/{recipe_id}/versions
4. POST /recipes/{recipe_id}/duplicate
5. POST /recipes/{recipe_id}/share
6. GET /recipes/shared
7. GET /recipes/{recipe_id}/export/json
8. POST /recipes/import

Following TDD methodology with pytest and async/await patterns.
Uses real MongoDB for integration tests (no mocks).
Tests authentication, authorization, error handling, and request/response schemas.
"""

import pytest
from beanie import PydanticObjectId

from app.services.transformation_engine.recipe_manager import (
    RecipeManager
)


@pytest.mark.integration
class TestRecipeCompatibilityEndpoint:
    """Integration tests for POST /recipes/{recipe_id}/check-compatibility."""

    @pytest.mark.asyncio
    async def test_check_compatibility_success(self, async_authorized_client, setup_database):
        """Test successful compatibility check returns 200 with report."""
        # ARRANGE - Create test recipe with schema snapshot
        recipe = await RecipeManager.create_recipe(
            name="Test Recipe",
            steps=[{"type": "remove_duplicates", "parameters": {}}],
            user_id="test_user_123",
            description="Test",
            schema_snapshot={"age": "int64", "name": "object", "salary": "float64"}
        )

        # ACT - Check compatibility with matching schema
        request_data = {
            "dataset_schema": {
                "age": "int64",
                "name": "object",
                "salary": "float64"
            }
        }

        response = await async_authorized_client.post(
            f"/api/v1/transformations/recipes/{recipe.id}/check-compatibility",
            json=request_data
        )

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert data["is_compatible"] is True
        assert data["compatibility_score"] == 100.0
        assert len(data["missing_columns"]) == 0
        assert len(data["type_mismatches"]) == 0

    @pytest.mark.asyncio
    async def test_check_compatibility_partial_match(self, async_authorized_client, setup_database):
        """Test compatibility check with partial schema match (80% threshold)."""
        # ARRANGE
        recipe = await RecipeManager.create_recipe(
            name="Test Recipe",
            steps=[{"type": "fill_missing", "parameters": {"columns": ["col1"]}}],
            user_id="test_user_123",
            schema_snapshot={
                "col1": "int64",
                "col2": "object",
                "col3": "float64",
                "col4": "int64",
                "col5": "bool"
            }
        )

        # ACT - Check with 4/5 columns (80%)
        request_data = {
            "dataset_schema": {
                "col1": "int64",
                "col2": "object",
                "col3": "float64",
                "col4": "int64"
                # Missing col5
            }
        }

        response = await async_authorized_client.post(
            f"/api/v1/transformations/recipes/{recipe.id}/check-compatibility",
            json=request_data
        )

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert data["is_compatible"] is True  # 80% meets threshold
        assert data["compatibility_score"] == 80.0
        assert "col5" in data["missing_columns"]

    @pytest.mark.asyncio
    async def test_check_compatibility_recipe_not_found(self, async_authorized_client, setup_database):
        """Test compatibility check with non-existent recipe returns 404."""
        # ACT
        request_data = {"dataset_schema": {"col1": "int64"}}

        response = await async_authorized_client.post(
            f"/api/v1/transformations/recipes/{PydanticObjectId()}/check-compatibility",
            json=request_data
        )

        # ASSERT — current contract: a missing recipe is a 404, not a
        # 200-with-incompatible response
        assert response.status_code == 404
        assert "Recipe not found" in response.json()["detail"]


@pytest.mark.integration
class TestRecipeVersioningEndpoints:
    """Integration tests for recipe versioning endpoints."""

    @pytest.mark.asyncio
    async def test_create_recipe_version_success(self, async_authorized_client, setup_database):
        """Test POST /recipes/{recipe_id}/versions creates new version."""
        # ARRANGE
        recipe = await RecipeManager.create_recipe(
            name="Original Recipe",
            steps=[{"type": "remove_duplicates", "parameters": {}}],
            user_id="test_user_123",
            description="Original version"
        )

        # ACT
        request_data = {
            "changes": {
                "name": "Updated Recipe",
                "description": "Version 2"
            },
            "version_notes": "Updated recipe name and description"
        }

        response = await async_authorized_client.post(
            f"/api/v1/transformations/recipes/{recipe.id}/versions",
            json=request_data
        )

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Recipe"
        assert data["description"] == "Version 2"
        # Version tracking is internal, not exposed in response

    @pytest.mark.asyncio
    async def test_create_version_unauthorized_user(self, async_authorized_client, setup_database):
        """Test version creation fails for unauthorized user."""
        # ARRANGE - Create recipe owned by different user
        recipe = await RecipeManager.create_recipe(
            name="Test Recipe",
            steps=[],
            user_id="different_user",
            description="Test"
        )

        # ACT
        request_data = {
            "changes": {"name": "Modified"},
            "version_notes": "Unauthorized change"
        }

        response = await async_authorized_client.post(
            f"/api/v1/transformations/recipes/{recipe.id}/versions",
            json=request_data
        )

        # ASSERT
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_version_history_success(self, async_authorized_client, setup_database):
        """Test GET /recipes/{recipe_id}/versions returns version history."""
        # ARRANGE - Create recipe with versions
        recipe_v1 = await RecipeManager.create_recipe(
            name="Recipe v1",
            steps=[],
            user_id="test_user_123"
        )

        recipe_v2 = await RecipeManager.create_version(
            recipe_id=str(recipe_v1.id),
            user_id="test_user_123",
            changes={"name": "Recipe v2"},
            version_notes="Version 2"
        )

        recipe_v3 = await RecipeManager.create_version(
            recipe_id=str(recipe_v2.id),
            user_id="test_user_123",
            changes={"name": "Recipe v3"},
            version_notes="Version 3"
        )

        # ACT
        response = await async_authorized_client.get(
            f"/api/v1/transformations/recipes/{recipe_v3.id}/versions"
        )

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert "versions" in data
        assert data["total_versions"] == 3
        # Versions should be sorted by version number
        versions = data["versions"]
        assert versions[0]["version"] == 1
        assert versions[1]["version"] == 2
        assert versions[2]["version"] == 3


@pytest.mark.integration
class TestRecipeDuplicationEndpoint:
    """Integration tests for POST /recipes/{recipe_id}/duplicate."""

    @pytest.mark.asyncio
    async def test_duplicate_recipe_success(self, async_authorized_client, setup_database):
        """Test successful recipe duplication."""
        # ARRANGE
        original = await RecipeManager.create_recipe(
            name="Original Recipe",
            steps=[
                {"type": "remove_duplicates", "parameters": {}},
                {"type": "fill_missing", "parameters": {"columns": ["age"]}}
            ],
            user_id="original_user",
            description="Original description",
            tags=["test", "duplicate"],
            is_public=True
        )

        # ACT
        request_data = {"new_name": "My Copy of Recipe"}

        response = await async_authorized_client.post(
            f"/api/v1/transformations/recipes/{original.id}/duplicate",
            json=request_data
        )

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "My Copy of Recipe"
        assert data["user_id"] == "test_user_123"  # Current user owns duplicate
        assert data["is_public"] is False  # Duplicates start as private
        assert len(data["steps"]) == 2  # Steps copied
        assert "test" in data["tags"]  # Tags copied

    @pytest.mark.asyncio
    async def test_duplicate_recipe_not_found(self, async_authorized_client, setup_database):
        """Test duplication fails for non-existent recipe."""
        # ACT
        request_data = {"new_name": "Copy"}

        response = await async_authorized_client.post(
            f"/api/v1/transformations/recipes/{PydanticObjectId()}/duplicate",
            json=request_data
        )

        # ASSERT
        assert response.status_code == 404


@pytest.mark.integration
class TestRecipeSharingEndpoints:
    """Integration tests for recipe sharing endpoints."""

    @pytest.mark.asyncio
    async def test_share_recipe_success(self, async_authorized_client, setup_database):
        """Test POST /recipes/{recipe_id}/share creates independent copy."""
        # ARRANGE
        recipe = await RecipeManager.create_recipe(
            name="Shared Recipe",
            steps=[{"type": "trim_whitespace", "parameters": {}}],
            user_id="test_user_123",
            description="Recipe to share"
        )

        # ACT
        request_data = {"target_user_id": "recipient_456"}

        response = await async_authorized_client.post(
            f"/api/v1/transformations/recipes/{recipe.id}/share",
            json=request_data
        )

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert "shared_recipe_id" in data
        assert data["target_user_id"] == "recipient_456"
        assert "shared_at" in data
        assert "successfully" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_share_recipe_unauthorized(self, async_authorized_client, setup_database):
        """Test sharing fails for recipe owned by different user."""
        # ARRANGE
        recipe = await RecipeManager.create_recipe(
            name="Recipe",
            steps=[],
            user_id="different_user"
        )

        # ACT
        request_data = {"target_user_id": "recipient"}

        response = await async_authorized_client.post(
            f"/api/v1/transformations/recipes/{recipe.id}/share",
            json=request_data
        )

        # ASSERT
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_shared_recipes_success(self, async_authorized_client, setup_database):
        """Test GET /recipes/shared returns recipes shared with user."""
        # ARRANGE - Share multiple recipes with current user
        recipe1 = await RecipeManager.create_recipe(
            name="Recipe 1",
            steps=[],
            user_id="owner_1"
        )

        recipe2 = await RecipeManager.create_recipe(
            name="Recipe 2",
            steps=[],
            user_id="owner_2"
        )

        await RecipeManager.share_recipe(
            recipe_id=str(recipe1.id),
            owner_id="owner_1",
            target_user_id="test_user_123"
        )

        await RecipeManager.share_recipe(
            recipe_id=str(recipe2.id),
            owner_id="owner_2",
            target_user_id="test_user_123"
        )

        # ACT
        response = await async_authorized_client.get(
            "/api/v1/transformations/recipes/shared"
        )

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert "shared_recipes" in data
        assert data["total"] == 2
        assert len(data["shared_recipes"]) == 2

    @pytest.mark.asyncio
    async def test_get_shared_recipes_empty(self, async_authorized_client, setup_database):
        """Test GET /recipes/shared returns empty list when no recipes shared."""
        # ACT
        response = await async_authorized_client.get(
            "/api/v1/transformations/recipes/shared"
        )

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["shared_recipes"]) == 0


@pytest.mark.integration
class TestRecipeImportExportEndpoints:
    """Integration tests for recipe import/export endpoints."""

    @pytest.mark.asyncio
    async def test_export_recipe_json_success(self, async_authorized_client, setup_database):
        """Test GET /recipes/{recipe_id}/export/json returns JSON format."""
        # ARRANGE
        recipe = await RecipeManager.create_recipe(
            name="Export Test Recipe",
            steps=[
                {"type": "remove_duplicates", "parameters": {}},
                {"type": "fill_missing", "parameters": {"columns": ["age"], "value": 0}}
            ],
            user_id="test_user_123",
            description="Recipe for export",
            tags=["export", "test"],
            schema_snapshot={"age": "int64", "name": "object"}
        )

        # ACT
        response = await async_authorized_client.get(
            f"/api/v1/transformations/recipes/{recipe.id}/export/json"
        )

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert data["format_version"] == "1.0"
        assert "recipe" in data
        recipe_data = data["recipe"]
        assert recipe_data["name"] == "Export Test Recipe"
        assert recipe_data["description"] == "Recipe for export"
        assert len(recipe_data["steps"]) == 2
        assert recipe_data["tags"] == ["export", "test"]
        assert recipe_data["schema_snapshot"] == {"age": "int64", "name": "object"}

    @pytest.mark.asyncio
    async def test_export_recipe_unauthorized(self, async_authorized_client, setup_database):
        """Test export fails for private recipe owned by different user."""
        # ARRANGE
        recipe = await RecipeManager.create_recipe(
            name="Private Recipe",
            steps=[],
            user_id="different_user",
            is_public=False
        )

        # ACT
        response = await async_authorized_client.get(
            f"/api/v1/transformations/recipes/{recipe.id}/export/json"
        )

        # ASSERT
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_export_recipe_public_allowed(self, async_authorized_client, setup_database):
        """Test export succeeds for public recipe regardless of owner."""
        # ARRANGE
        recipe = await RecipeManager.create_recipe(
            name="Public Recipe",
            steps=[],
            user_id="different_user",
            is_public=True
        )

        # ACT
        response = await async_authorized_client.get(
            f"/api/v1/transformations/recipes/{recipe.id}/export/json"
        )

        # ASSERT
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_import_recipe_success(self, async_authorized_client, setup_database):
        """Test POST /recipes/import creates new recipe from JSON."""
        # ARRANGE
        json_data = {
            "format_version": "1.0",
            "recipe": {
                "name": "Imported Recipe",
                "description": "Imported from JSON",
                "version": 1,
                "tags": ["imported", "test"],
                "schema_snapshot": {"col1": "int64", "col2": "object"},
                "steps": [
                    {
                        "step_id": "step_1",
                        "transformation_type": "remove_duplicates",
                        "parameters": {},
                        "description": "Remove duplicate rows",
                        "order": 0
                    }
                ],
                "metadata": {"source": "external"}
            }
        }

        # ACT
        request_data = {
            "json_data": json_data,
            "name_override": None
        }

        response = await async_authorized_client.post(
            "/api/v1/transformations/recipes/import",
            json=request_data
        )

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Imported Recipe"
        assert data["description"] == "Imported from JSON"
        assert data["user_id"] == "test_user_123"  # Owned by importing user
        assert len(data["steps"]) == 1
        assert "imported" in data["tags"]

    @pytest.mark.asyncio
    async def test_import_recipe_with_name_override(self, async_authorized_client, setup_database):
        """Test import uses name_override when provided."""
        # ARRANGE
        json_data = {
            "format_version": "1.0",
            "recipe": {
                "name": "Original Name",
                "description": None,
                "version": 1,
                "tags": [],
                "schema_snapshot": None,
                "steps": [],
                "metadata": {}
            }
        }

        # ACT
        request_data = {
            "json_data": json_data,
            "name_override": "Overridden Name"
        }

        response = await async_authorized_client.post(
            "/api/v1/transformations/recipes/import",
            json=request_data
        )

        # ASSERT
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Overridden Name"

    @pytest.mark.asyncio
    async def test_import_recipe_invalid_format(self, async_authorized_client, setup_database):
        """Test import fails with invalid format version."""
        # ARRANGE
        json_data = {
            "format_version": "2.0",  # Unsupported version
            "recipe": {}
        }

        # ACT
        request_data = {
            "json_data": json_data,
            "name_override": None
        }

        response = await async_authorized_client.post(
            "/api/v1/transformations/recipes/import",
            json=request_data
        )

        # ASSERT
        assert response.status_code == 400
        data = response.json()
        assert "invalid recipe format" in data["detail"].lower()
