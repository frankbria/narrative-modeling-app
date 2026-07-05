"""
Shared test configurations and fixtures for MCP Server tests.
"""

import pytest
import logging


@pytest.fixture(autouse=True)
def setup_logging():
    """Configure logging for tests."""
    logging.basicConfig(level=logging.DEBUG)
    yield
    logging.getLogger().handlers.clear()
