"""
Unit test configuration for middleware tests.

These tests need FastAPI but minimal app setup.
"""

import pytest
from fastapi import FastAPI

@pytest.fixture
def minimal_app():
    """Create a minimal FastAPI app for middleware testing."""
    return FastAPI()
