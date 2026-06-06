"""Tests for the canonical Beanie document model registry.

The registry (app/models/registry.py) is the single source of truth for
database initialization. The app lifespan (app/main.py) and the test database
fixture (tests/conftest.py) must both use it so the two can never drift —
drift previously left VisualizationCache, TransformationConfig, RevisedData,
SharedRecipe, and DataIssueRecord unregistered at app startup (issue #160).
"""

import importlib
import inspect
import pkgutil

import pytest
from beanie import Document


pytestmark = pytest.mark.unit


def _app_models_document_classes():
    """Discover every Document subclass defined under app.models."""
    import app.models

    discovered = set()
    for module_info in pkgutil.iter_modules(app.models.__path__):
        module = importlib.import_module(f"app.models.{module_info.name}")
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(obj, Document)
                and obj is not Document
                and obj.__module__ == module.__name__
            ):
                discovered.add(obj)
    return discovered


def test_registry_contains_every_app_models_document():
    """Every Document subclass under app.models must be in DOCUMENT_MODELS."""
    from app.models.registry import DOCUMENT_MODELS

    missing = _app_models_document_classes() - set(DOCUMENT_MODELS)
    assert not missing, (
        f"Document models missing from app.models.registry.DOCUMENT_MODELS: "
        f"{sorted(cls.__name__ for cls in missing)}"
    )


def test_registry_contains_recipe_manager_documents():
    """Recipe manager documents live in app.services but must be registered."""
    from app.models.registry import DOCUMENT_MODELS
    from app.services.transformation_engine.recipe_manager import (
        RecipeExecutionHistory,
        SharedRecipe,
        TransformationRecipe,
    )

    for cls in (TransformationRecipe, SharedRecipe, RecipeExecutionHistory):
        assert cls in DOCUMENT_MODELS, f"{cls.__name__} missing from DOCUMENT_MODELS"


def test_registry_has_no_duplicates():
    from app.models.registry import DOCUMENT_MODELS

    names = [cls.__name__ for cls in DOCUMENT_MODELS]
    assert len(names) == len(set(names)), f"Duplicate models in registry: {names}"


def test_app_lifespan_uses_registry():
    """app.main must initialize Beanie from the canonical registry."""
    import app.main
    from app.models.registry import DOCUMENT_MODELS

    assert getattr(app.main, "DOCUMENT_MODELS", None) is DOCUMENT_MODELS
