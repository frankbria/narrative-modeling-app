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


@pytest.fixture
def mock_s3_service(mocker):
    """Mock S3 service for testing."""
    mock = mocker.patch("utils.s3_service.download_file_from_s3")
    mock.return_value = "test_file.csv"
    return mock
