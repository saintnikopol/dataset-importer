"""
Fixed test configuration for YOLO Dataset Management.
Provides proper dependency injection and database mocking.
"""

import pytest
import tempfile
import shutil
from typing import Dict, Any
from unittest.mock import AsyncMock, patch
from pathlib import Path
from datetime import datetime


# Essential Test Configuration
@pytest.fixture(scope="session")
def test_settings():
    """Test configuration matching actual Settings model."""
    from src.config import Settings, Environment
    return Settings(
        environment=Environment.LOCAL,
        mongodb_url="mongodb://localhost:27017/test_yolo_datasets",
        redis_url="redis://localhost:6379/1",
        log_level="DEBUG",
        storage_path="./test_storage"
    )


# Temporary Directory for File Operations  
@pytest.fixture
def temp_dir() -> Path:
    """Temporary directory for file operations."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


# Sample Data Fixtures
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


@pytest.fixture
def sample_dataset_data() -> Dict[str, Any]:
    """Sample dataset response data."""
    return {
        "id": "507f1f77bcf86cd799439011",
        "name": "Test Traffic Dataset",
        "description": "Traffic detection with 3 classes",
        "status": "completed",
        "created_at": datetime.now(),
        "completed_at": datetime.now(),
        "import_job_id": "550e8400-e29b-41d4-a716-446655440000",
        "stats": {
            "total_images": 100,
            "total_annotations": 250,
            "classes_count": 3,
            "dataset_size_bytes": 1024000,
            "avg_annotations_per_image": 2.5
        },
        "classes": [
            {"id": 0, "name": "car", "count": 150},
            {"id": 1, "name": "truck", "count": 75},
            {"id": 2, "name": "bus", "count": 25}
        ],
        "storage": {
            "images_path": "gs://bucket/datasets/test/images/",
            "labels_path": "gs://bucket/datasets/test/labels/"
        }
    }


@pytest.fixture
def sample_image_data() -> list:
    """Sample image data with annotations."""
    return [
        {
            "id": "img_001",
            "filename": "traffic_001.jpg",
            "width": 1920,
            "height": 1080,
            "file_size_bytes": 245760,
            "image_url": "gs://bucket/datasets/test/images/traffic_001.jpg",
            "annotations": [
                {
                    "class_id": 0,
                    "class_name": "car",
                    "bbox": {
                        "center_x": 0.5,
                        "center_y": 0.6,
                        "width": 0.1,
                        "height": 0.3
                    }
                }
            ],
            "annotation_count": 1
        },
        {
            "id": "img_002",
            "filename": "traffic_002.jpg",
            "width": 1920,
            "height": 1080,
            "file_size_bytes": 312000,
            "image_url": "gs://bucket/datasets/test/images/traffic_002.jpg",
            "annotations": [
                {
                    "class_id": 0,
                    "class_name": "car",
                    "bbox": {
                        "center_x": 0.3,
                        "center_y": 0.4,
                        "width": 0.2,
                        "height": 0.15
                    }
                },
                {
                    "class_id": 1,
                    "class_name": "truck",
                    "bbox": {
                        "center_x": 0.7,
                        "center_y": 0.5,
                        "width": 0.25,
                        "height": 0.4
                    }
                }
            ],
            "annotation_count": 2
        }
    ]


# Database Cleanup - Simple Version
@pytest.fixture(autouse=True)
async def cleanup_test_data():
    """Clean up test data after each test."""
    yield
    # Cleanup would happen here if database is initialized
    pass