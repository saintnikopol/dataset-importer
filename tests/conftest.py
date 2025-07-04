"""
Essential test configuration for YOLO Dataset Management.
Simplified, focused fixtures that match actual implementation.
"""

import asyncio
import pytest
import tempfile
import shutil
from typing import Dict, Any
from unittest.mock import AsyncMock
from pathlib import Path

import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi.testclient import TestClient
from httpx import AsyncClient

from src.main import app
from src.config import Settings, Environment
from src.services.database import init_database, close_database


# Core Configuration
@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Test configuration matching actual Settings model."""
    return Settings(
        environment=Environment.LOCAL,
        mongodb_url="mongodb://localhost:27017/test_yolo_datasets",
        redis_url="redis://localhost:6379/1",
        log_level="DEBUG",
        storage_path="./test_storage"
    )


# Database Fixtures
@pytest.fixture(scope="session")
async def test_db_client(test_settings: Settings) -> AsyncClient:
    """Test database client with proper initialization."""
    # Override settings for testing
    with patch('src.config.settings', test_settings):
        await init_database()
        yield
        await close_database()


@pytest.fixture
def temp_dir() -> Path:
    """Temporary directory for file operations."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


# API Client Fixtures  
@pytest.fixture
async def async_client() -> AsyncClient:
    """Async test client for API testing."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


# Data Factories (Simple)
@pytest.fixture
def sample_import_request_data() -> Dict[str, Any]:
    """Sample import request data matching actual API."""
    return {
        "name": "Test Traffic Dataset",
        "description": "Traffic detection with 3 classes",
        "yolo_config_url": "https://example.com/dataset.yaml",
        "dataset_url": "https://example.com/dataset.zip"
    }


@pytest.fixture  
def sample_yolo_config_yaml() -> str:
    """Valid YOLO config in real ultralytics format."""
    return """
path: /datasets/traffic
train: images/train
val: images/val
test: images/test

names:
  0: car
  1: truck
  2: bus
"""


@pytest.fixture
def sample_yolo_annotation_lines() -> str:
    """Valid YOLO annotation format."""
    return "0 0.5 0.5 0.3 0.4\n1 0.2 0.3 0.1 0.2\n0 0.8 0.7 0.15 0.25"


# Mock Services (Simple)
@pytest.fixture
def mock_storage_service():
    """Mock storage service with essential methods."""
    mock = AsyncMock()
    mock.upload_file.return_value = "test/path/file.jpg"
    mock.download_file.return_value = b"test-content"
    return mock


@pytest.fixture
def mock_job_queue():
    """Mock job queue with essential methods."""
    mock = AsyncMock()
    mock.enqueue_import_job.return_value = None
    return mock


# Database Cleanup
@pytest.fixture(autouse=True)
async def cleanup_test_data():
    """Clean up test data after each test."""
    yield
    # Cleanup would happen here if database is initialized
    pass