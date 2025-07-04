"""
Comprehensive API tests for YOLO Dataset Management System - FIXED VERSION.

Tests all FastAPI endpoints including dataset import, listing, image management,
and health checks with proper async testing, mocking, and error handling.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient
from fastapi import status
from fastapi.testclient import TestClient
from bson import ObjectId

from src.main import app
from src.models.api import ImportRequest, ImportResponse, JobStatusResponse
from src.models.database import Dataset, ImportJob, Image
from src.utils.exceptions import DatabaseError, ProcessingError
from src.services.database import get_database
from src.services.job_queue import get_job_queue


@pytest.fixture
def mock_database_service():
    """Mock database service with common responses."""
    mock = AsyncMock()
    
    # Default responses for common operations
    mock.create_import_job.return_value = "507f1f77bcf86cd799439011"
    mock.get_import_job.return_value = None
    mock.list_datasets.return_value = {
        "datasets": [],
        "pagination": {
            "page": 1,
            "limit": 20,
            "total_pages": 0,
            "total_items": 0,
            "has_next": False,
            "has_prev": False
        }
    }
    mock.get_dataset.return_value = None
    mock.list_dataset_images.return_value = {
        "dataset_id": "507f1f77bcf86cd799439011",
        "images": [],
        "pagination": {
            "page": 1,
            "limit": 50,
            "total_pages": 0,
            "total_items": 0,
            "has_next": False,
            "has_prev": False
        },
        "filters_applied": {
            "class_filter": None,
            "has_annotations": None
        }
    }
    
    return mock


@pytest.fixture
def mock_job_queue():
    """Mock job queue service."""
    mock = AsyncMock()
    mock.enqueue_import_job.return_value = None
    return mock


@pytest.fixture
async def test_client(mock_database_service, mock_job_queue):
    """Test client with properly mocked dependencies."""
    
    def override_get_database():
        return mock_database_service
    
    def override_get_job_queue():
        return mock_job_queue
    
    # Override FastAPI dependencies
    app.dependency_overrides[get_database] = override_get_database
    app.dependency_overrides[get_job_queue] = override_get_job_queue
    
    try:
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac
    finally:
        # Clean up dependency overrides
        app.dependency_overrides.clear()


@pytest.fixture
def sample_import_request_data():
    """Sample import request data."""
    return {
        "name": "Test Traffic Dataset",
        "description": "Traffic detection with 3 classes for testing",
        "yolo_config_url": "https://storage.googleapis.com/test-bucket/dataset.yaml",
        "dataset_url": "https://storage.googleapis.com/test-bucket/dataset.zip"
    }


@pytest.fixture
def sample_dataset_data():
    """Sample dataset response data with correct structure."""
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
        # Fix: classes should be List[str] for DatasetSummary
        "classes": ["car", "truck", "bus"],
        "storage": {
            "images_path": "gs://bucket/datasets/test/images/",
            "labels_path": "gs://bucket/datasets/test/labels/"
        }
    }


@pytest.fixture
def sample_image_data():
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


class TestDatasetImport:
    """Test dataset import endpoints."""

    async def test_import_valid_request_all_fields(
        self,
        test_client: AsyncClient,
        sample_import_request_data: Dict[str, Any],
        mock_database_service: AsyncMock,
        mock_job_queue: AsyncMock
    ):
        """Test successful dataset import with all fields."""
        response = await test_client.post(
            "/datasets/import",
            json=sample_import_request_data
        )
        
        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        
        # Validate response structure
        assert "job_id" in data
        assert data["status"] == "queued"
        assert data["message"] == "Import job started successfully"
        assert "created_at" in data
        assert "estimated_completion" in data
        
        # Verify UUID format for job_id
        import uuid
        uuid.UUID(data["job_id"])  # Should not raise exception
        
        # Verify service calls
        mock_database_service.create_import_job.assert_called_once()
        mock_job_queue.enqueue_import_job.assert_called_once()

    async def test_import_valid_request_optional_description(
        self,
        test_client: AsyncClient,
        mock_database_service: AsyncMock,
        mock_job_queue: AsyncMock
    ):
        """Test import without optional description field."""
        request_data = {
            "name": "Test Dataset",
            "yolo_config_url": "https://example.com/config.yaml",
            "dataset_url": "https://example.com/dataset.zip"
        }
        
        response = await test_client.post(
            "/datasets/import",
            json=request_data
        )
        
        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert data["status"] == "queued"

    async def test_import_invalid_empty_name(self, test_client: AsyncClient):
        """Test import with empty name."""
        request_data = {
            "name": "",
            "yolo_config_url": "https://example.com/config.yaml",
            "dataset_url": "https://example.com/dataset.zip"
        }
        
        response = await test_client.post("/datasets/import", json=request_data)
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        data = response.json()
        assert "detail" in data

    async def test_import_invalid_urls(self, test_client: AsyncClient):
        """Test import with invalid URL formats."""
        invalid_requests = [
            {
                "name": "Test Dataset",
                "yolo_config_url": "not-a-url",
                "dataset_url": "https://example.com/dataset.zip"
            },
            {
                "name": "Test Dataset", 
                "yolo_config_url": "https://example.com/config.yaml",
                "dataset_url": "invalid-url"
            },
            {
                "name": "Test Dataset",
                "yolo_config_url": "ftp://example.com/config.yaml",  # Wrong protocol
                "dataset_url": "https://example.com/dataset.zip"
            }
        ]
        
        for request_data in invalid_requests:
            response = await test_client.post("/datasets/import", json=request_data)
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_import_missing_required_fields(self, test_client: AsyncClient):
        """Test import with missing required fields."""
        incomplete_requests = [
            {"name": "Test Dataset"},  # Missing URLs
            {"yolo_config_url": "https://example.com/config.yaml"},  # Missing name and dataset_url
            {
                "name": "Test Dataset",
                "yolo_config_url": "https://example.com/config.yaml"
                # Missing dataset_url
            }
        ]
        
        for request_data in incomplete_requests:
            response = await test_client.post("/datasets/import", json=request_data)
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_import_database_error(
        self,
        test_client: AsyncClient,
        sample_import_request_data: Dict[str, Any],
        mock_database_service: AsyncMock
    ):
        """Test import with database error."""
        mock_database_service.create_import_job.side_effect = DatabaseError("Database connection failed")
        
        response = await test_client.post(
            "/datasets/import",
            json=sample_import_request_data
        )
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "error" in data or "detail" in data


class TestJobStatus:
    """Test import job status endpoints."""

    async def test_get_job_status_queued(
        self,
        test_client: AsyncClient,
        mock_database_service: AsyncMock
    ):
        """Test getting status for queued job."""
        job_id = "550e8400-e29b-41d4-a716-446655440000"
        
        mock_database_service.get_import_job.return_value = {
            "job_id": job_id,
            "status": "queued",
            "progress": {
                "percentage": 0,
                "current_step": "queued",  # Fix: Add required field
                "steps_completed": [],
                "total_steps": 6
            },
            "started_at": None,
            "completed_at": None,
            "estimated_completion": datetime.now() + timedelta(minutes=20)
        }
        
        response = await test_client.get(f"/datasets/import/{job_id}/status")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["job_id"] == job_id
        assert data["status"] == "queued"
        assert data["progress"]["percentage"] == 0
        assert "estimated_completion" in data

    async def test_get_job_status_processing(
        self,
        test_client: AsyncClient,
        mock_database_service: AsyncMock
    ):
        """Test getting status for processing job."""
        job_id = "550e8400-e29b-41d4-a716-446655440000"
        
        mock_database_service.get_import_job.return_value = {
            "job_id": job_id,
            "status": "processing",
            "progress": {
                "percentage": 65,
                "current_step": "parsing_annotations",  # Fix: Add required field
                "steps_completed": ["download_config", "download_dataset", "extract_archive"],
                "current_step_progress": "6500/10000 annotations processed",
                "total_steps": 6
            },
            "started_at": datetime.now() - timedelta(minutes=5),
            "completed_at": None,
            "estimated_completion": datetime.now() + timedelta(minutes=10)
        }
        
        response = await test_client.get(f"/datasets/import/{job_id}/status")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["job_id"] == job_id
        assert data["status"] == "processing"
        assert data["progress"]["percentage"] == 65
        assert data["progress"]["current_step"] == "parsing_annotations"
        assert len(data["progress"]["steps_completed"]) == 3

    async def test_get_job_status_completed(
        self,
        test_client: AsyncClient,
        mock_database_service: AsyncMock
    ):
        """Test getting status for completed job."""
        job_id = "550e8400-e29b-41d4-a716-446655440000"
        dataset_id = "507f1f77bcf86cd799439011"
        
        mock_database_service.get_import_job.return_value = {
            "job_id": job_id,
            "status": "completed",
            "progress": {
                "percentage": 100, 
                "current_step": "completed",  # Fix: Add required field
                "total_steps": 6
            },
            "dataset_id": dataset_id,
            "started_at": datetime.now() - timedelta(minutes=15),
            "completed_at": datetime.now(),
            "summary": {
                "total_images": 10000,
                "total_annotations": 25000,
                "classes": ["person", "car", "bicycle"],
                "dataset_size_bytes": 2147483648
            }
        }
        
        response = await test_client.get(f"/datasets/import/{job_id}/status")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["job_id"] == job_id
        assert data["status"] == "completed"
        assert data["progress"]["percentage"] == 100
        assert data["dataset_id"] == dataset_id
        assert "summary" in data
        assert data["summary"]["total_images"] == 10000

    async def test_get_job_status_failed(
        self,
        test_client: AsyncClient,
        mock_database_service: AsyncMock
    ):
        """Test getting status for failed job."""
        job_id = "550e8400-e29b-41d4-a716-446655440000"
        
        mock_database_service.get_import_job.return_value = {
            "job_id": job_id,
            "status": "failed",
            "progress": {
                "percentage": 30,
                "current_step": "failed"  # Fix: Add required field
            },
            "error": {
                "code": "invalid_yolo_format",
                "message": "YOLO dataset archive missing required directories",
                "details": "Archive must contain 'images/' and 'labels/' directories"
            },
            "started_at": datetime.now() - timedelta(minutes=10),
            "completed_at": datetime.now() - timedelta(minutes=5)
        }
        
        response = await test_client.get(f"/datasets/import/{job_id}/status")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["job_id"] == job_id
        assert data["status"] == "failed"
        assert "error" in data
        assert data["error"]["code"] == "invalid_yolo_format"

    async def test_get_job_status_not_found(
        self,
        test_client: AsyncClient,
        mock_database_service: AsyncMock
    ):
        """Test getting status for non-existent job."""
        job_id = "550e8400-e29b-41d4-a716-446655440000"
        mock_database_service.get_import_job.return_value = None
        
        response = await test_client.get(f"/datasets/import/{job_id}/status")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "not found" in data["detail"].lower()

    async def test_get_job_status_invalid_uuid(self, test_client: AsyncClient):
        """Test getting status with invalid job ID format."""
        invalid_job_id = "invalid-job-id-format"
        
        response = await test_client.get(f"/datasets/import/{invalid_job_id}/status")
        
        # The endpoint should still work, but return 404 if not found
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_400_BAD_REQUEST]


class TestDatasetListing:
    """Test dataset listing endpoints."""

    async def test_list_datasets_empty(
        self,
        test_client: AsyncClient,
        mock_database_service: AsyncMock
    ):
        """Test listing datasets when none exist."""
        response = await test_client.get("/datasets")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["datasets"] == []
        assert data["pagination"]["total_items"] == 0
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["limit"] == 20

    async def test_list_datasets_with_data(
        self,
        test_client: AsyncClient,
        mock_database_service: AsyncMock,
        sample_dataset_data: Dict[str, Any]
    ):
        """Test listing datasets with sample data."""
        datasets = [sample_dataset_data]
        mock_database_service.list_datasets.return_value = {
            "datasets": datasets,
            "pagination": {
                "page": 1,
                "limit": 20,
                "total_pages": 1,
                "total_items": 1,
                "has_next": False,
                "has_prev": False
            }
        }
        
        response = await test_client.get("/datasets")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert len(data["datasets"]) == 1
        assert data["pagination"]["total_items"] == 1
        assert data["datasets"][0]["name"] == sample_dataset_data["name"]

    @pytest.mark.parametrize("page,limit", [
        (1, 20),
        (2, 10), 
        (1, 50),
        (3, 5)
    ])
    async def test_list_datasets_pagination_parameters(
        self,
        test_client: AsyncClient,
        mock_database_service: AsyncMock,
        page: int,
        limit: int
    ):
        """Test dataset listing with various pagination parameters."""
        mock_database_service.list_datasets.return_value = {
            "datasets": [],
            "pagination": {
                "page": page,
                "limit": limit,
                "total_pages": 0,
                "total_items": 0,
                "has_next": False,
                "has_prev": page > 1
            }
        }
        
        response = await test_client.get(f"/datasets?page={page}&limit={limit}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["pagination"]["page"] == page
        assert data["pagination"]["limit"] == limit

    @pytest.mark.parametrize("status_filter", ["completed", "processing", "failed", "queued"])
    async def test_list_datasets_status_filtering(
        self,
        test_client: AsyncClient,
        mock_database_service: AsyncMock,
        status_filter: str
    ):
        """Test dataset listing with status filtering."""
        response = await test_client.get(f"/datasets?status={status_filter}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["filters_applied"]["status"] == status_filter
        
        # Verify the filter was passed to the database service
        mock_database_service.list_datasets.assert_called_once()
        call_kwargs = mock_database_service.list_datasets.call_args[1]
        assert call_kwargs["status"] == status_filter

    @pytest.mark.parametrize("sort_by,sort_order", [
        ("created_at", "desc"),
        ("created_at", "asc"),
        ("name", "asc"),
        ("name", "desc")
    ])
    async def test_list_datasets_sorting(
        self,
        test_client: AsyncClient,
        mock_database_service: AsyncMock,
        sort_by: str,
        sort_order: str
    ):
        """Test dataset listing with different sorting options."""
        response = await test_client.get(f"/datasets?sort_by={sort_by}&sort_order={sort_order}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["filters_applied"]["sort_by"] == sort_by
        assert data["filters_applied"]["sort_order"] == sort_order

    async def test_list_datasets_invalid_pagination(self, test_client: AsyncClient):
        """Test dataset listing with invalid pagination parameters."""
        invalid_params = [
            "?page=0",  # Page must be >= 1
            "?limit=0",  # Limit must be >= 1
            "?limit=101",  # Limit must be <= 100
            "?page=invalid",  # Page must be integer
            "?limit=invalid"  # Limit must be integer
        ]
        
        for params in invalid_params:
            response = await test_client.get(f"/datasets{params}")
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_list_datasets_invalid_sort_order(self, test_client: AsyncClient):
        """Test dataset listing with invalid sort order."""
        response = await test_client.get("/datasets?sort_order=invalid")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_list_datasets_database_error(
        self,
        test_client: AsyncClient,
        mock_database_service: AsyncMock
    ):
        """Test dataset listing with database error."""
        mock_database_service.list_datasets.side_effect = DatabaseError("Database connection failed")
        
        response = await test_client.get("/datasets")
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestDatasetDetails:
    """Test individual dataset detail endpoints."""

    async def test_get_dataset_valid_id(
        self,
        test_client: AsyncClient,
        mock_database_service: AsyncMock,
        sample_dataset_data: Dict[str, Any]
    ):
        """Test getting dataset details with valid ID."""
        dataset_id = "507f1f77bcf86cd799439011"
        mock_database_service.get_dataset.return_value = sample_dataset_data
        
        response = await test_client.get(f"/datasets/{dataset_id}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["id"] == dataset_id
        assert data["name"] == sample_dataset_data["name"]
        assert data["status"] == sample_dataset_data["status"]
        assert "stats" in data
        assert "classes" in data
        assert "storage" in data

    async def test_get_dataset_not_found(
        self,
        test_client: AsyncClient,
        mock_database_service: AsyncMock
    ):
        """Test getting non-existent dataset."""
        dataset_id = "507f1f77bcf86cd799439011"
        mock_database_service.get_dataset.return_value = None
        
        response = await test_client.get(f"/datasets/{dataset_id}")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "not found" in data["detail"].lower()

    async def test_get_dataset_invalid_object_id(self, test_client: AsyncClient):
        """Test getting dataset with invalid ObjectId format."""
        invalid_id = "invalid-object-id"
        
        response = await test_client.get(f"/datasets/{invalid_id}")
        
        # Should return 404 since invalid ObjectId won't be found
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_get_dataset_database_error(
        self,
        test_client: AsyncClient,
        mock_database_service: AsyncMock
    ):
        """Test getting dataset with database error."""
        dataset_id = "507f1f77bcf86cd799439011"
        mock_database_service.get_dataset.side_effect = DatabaseError("Database connection failed")
        
        response = await test_client.get(f"/datasets/{dataset_id}")
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestDatasetImages:
    """Test dataset image listing endpoints."""

    async def test_list_images_valid_dataset(
        self,
        test_client: AsyncClient,
        mock_database_service: AsyncMock,
        sample_dataset_data: Dict[str, Any],
        sample_image_data: list
    ):
        """Test listing images for valid dataset."""
        dataset_id = "507f1f77bcf86cd799439011"
        
        # Mock dataset exists
        mock_database_service.get_dataset.return_value = sample_dataset_data
        
        # Mock image listing
        mock_database_service.list_dataset_images.return_value = {
            "dataset_id": dataset_id,
            "images": sample_image_data,
            "pagination": {
                "page": 1,
                "limit": 50,
                "total_pages": 1,
                "total_items": 2,
                "has_next": False,
                "has_prev": False
            },
            "filters_applied": {
                "class_filter": None,
                "has_annotations": None
            }
        }
        
        response = await test_client.get(f"/datasets/{dataset_id}/images")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["dataset_id"] == dataset_id
        assert len(data["images"]) == 2
        assert data["pagination"]["total_items"] == 2
        
        # Verify image structure
        image = data["images"][0]
        assert "id" in image
        assert "filename" in image
        assert "annotations" in image
        assert "annotation_count" in image

    async def test_list_images_empty_dataset(
        self,
        test_client: AsyncClient,
        mock_database_service: AsyncMock,
        sample_dataset_data: Dict[str, Any]
    ):
        """Test listing images for dataset with no images."""
        dataset_id = "507f1f77bcf86cd799439011"
        
        mock_database_service.get_dataset.return_value = sample_dataset_data
        # Default mock returns empty images list
        
        response = await test_client.get(f"/datasets/{dataset_id}/images")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["dataset_id"] == dataset_id
        assert data["images"] == []
        assert data["pagination"]["total_items"] == 0

    async def test_list_images_pagination(
        self,
        test_client: AsyncClient,
        mock_database_service: AsyncMock,
        sample_dataset_data: Dict[str, Any]
    ):
        """Test image listing with pagination parameters."""
        dataset_id = "507f1f77bcf86cd799439011"
        page, limit = 2, 25
        
        mock_database_service.get_dataset.return_value = sample_dataset_data
        mock_database_service.list_dataset_images.return_value = {
            "dataset_id": dataset_id,
            "images": [],
            "pagination": {
                "page": page,
                "limit": limit,
                "total_pages": 3,
                "total_items": 75,
                "has_next": True,
                "has_prev": True
            },
            "filters_applied": {
                "class_filter": None,
                "has_annotations": None
            }
        }
        
        response = await test_client.get(f"/datasets/{dataset_id}/images?page={page}&limit={limit}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["pagination"]["page"] == page
        assert data["pagination"]["limit"] == limit

    @pytest.mark.parametrize("class_filter", ["car", "truck", "bus"])
    async def test_list_images_class_filtering(
        self,
        test_client: AsyncClient,
        mock_database_service: AsyncMock,
        sample_dataset_data: Dict[str, Any],
        class_filter: str
    ):
        """Test image listing with class filtering."""
        dataset_id = "507f1f77bcf86cd799439011"
        
        mock_database_service.get_dataset.return_value = sample_dataset_data
        
        # Fix: Ensure filters_applied includes the filter
        mock_database_service.list_dataset_images.return_value = {
            "dataset_id": dataset_id,
            "images": [],
            "pagination": {
                "page": 1,
                "limit": 50,
                "total_pages": 0,
                "total_items": 0,
                "has_next": False,
                "has_prev": False
            },
            "filters_applied": {
                "class_filter": class_filter,  # Fix: Include the actual filter
                "has_annotations": None
            }
        }
        
        response = await test_client.get(f"/datasets/{dataset_id}/images?class_filter={class_filter}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["filters_applied"]["class_filter"] == class_filter
        
        # Verify filter was passed to database service
        mock_database_service.list_dataset_images.assert_called_once()
        call_kwargs = mock_database_service.list_dataset_images.call_args[1]
        assert call_kwargs["class_filter"] == class_filter

    @pytest.mark.parametrize("has_annotations", [True, False])
    async def test_list_images_annotation_filtering(
        self,
        test_client: AsyncClient,
        mock_database_service: AsyncMock,
        sample_dataset_data: Dict[str, Any],
        has_annotations: bool
    ):
        """Test image listing with annotation presence filtering."""
        dataset_id = "507f1f77bcf86cd799439011"
        
        mock_database_service.get_dataset.return_value = sample_dataset_data
        
        # Fix: Ensure filters_applied includes the filter
        mock_database_service.list_dataset_images.return_value = {
            "dataset_id": dataset_id,
            "images": [],
            "pagination": {
                "page": 1,
                "limit": 50,
                "total_pages": 0,
                "total_items": 0,
                "has_next": False,
                "has_prev": False
            },
            "filters_applied": {
                "class_filter": None,
                "has_annotations": has_annotations  # Fix: Include the actual filter
            }
        }
        
        response = await test_client.get(f"/datasets/{dataset_id}/images?has_annotations={has_annotations}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["filters_applied"]["has_annotations"] == has_annotations

    @pytest.mark.parametrize("sort_by,sort_order", [
        ("filename", "asc"),
        ("filename", "desc"),
        ("annotation_count", "asc"),
        ("annotation_count", "desc")
    ])
    async def test_list_images_sorting(
        self,
        test_client: AsyncClient,
        mock_database_service: AsyncMock,
        sample_dataset_data: Dict[str, Any],
        sort_by: str,
        sort_order: str
    ):
        """Test image listing with sorting options."""
        dataset_id = "507f1f77bcf86cd799439011"
        
        mock_database_service.get_dataset.return_value = sample_dataset_data
        
        response = await test_client.get(
            f"/datasets/{dataset_id}/images?sort_by={sort_by}&sort_order={sort_order}"
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify sorting parameters were passed
        call_kwargs = mock_database_service.list_dataset_images.call_args[1]
        assert call_kwargs["sort_by"] == sort_by
        assert call_kwargs["sort_order"] == sort_order

    async def test_list_images_dataset_not_found(
        self,
        test_client: AsyncClient,
        mock_database_service: AsyncMock
    ):
        """Test listing images for non-existent dataset."""
        dataset_id = "507f1f77bcf86cd799439011"
        mock_database_service.get_dataset.return_value = None
        
        response = await test_client.get(f"/datasets/{dataset_id}/images")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_list_images_invalid_pagination(
        self,
        test_client: AsyncClient,
        mock_database_service: AsyncMock,
        sample_dataset_data: Dict[str, Any]
    ):
        """Test image listing with invalid pagination parameters."""
        dataset_id = "507f1f77bcf86cd799439011"
        mock_database_service.get_dataset.return_value = sample_dataset_data
        
        invalid_params = [
            "?page=0",
            "?limit=0", 
            "?limit=201"  # Max limit is 200
        ]
        
        for params in invalid_params:
            response = await test_client.get(f"/datasets/{dataset_id}/images{params}")
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestHealthCheck:
    """Test health check endpoint."""

    async def test_health_check_healthy(self, test_client: AsyncClient):
        """Test healthy service response."""
        # Mock all health checks to return healthy
        with patch('src.api.health.health_check_database') as mock_db_health, \
             patch('src.api.health.health_check_queue') as mock_queue_health, \
             patch('src.api.health.health_check_storage') as mock_storage_health:
            
            mock_db_health.return_value = {"status": "healthy"}
            mock_queue_health.return_value = {"status": "healthy"}
            mock_storage_health.return_value = {"status": "healthy"}
            
            response = await test_client.get("/health")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data
        assert "dependencies" in data
        assert data["dependencies"]["mongodb"] == "healthy"
        assert data["dependencies"]["job_queue"] == "healthy"
        assert data["dependencies"]["storage"] == "healthy"

    async def test_health_check_unhealthy_dependencies(self, test_client: AsyncClient):
        """Test unhealthy dependencies response."""
        with patch('src.api.health.health_check_database') as mock_db_health, \
             patch('src.api.health.health_check_queue') as mock_queue_health, \
             patch('src.api.health.health_check_storage') as mock_storage_health:
            
            # Mock database as unhealthy
            mock_db_health.return_value = {"status": "unhealthy", "error": "Connection timeout"}
            mock_queue_health.return_value = {"status": "healthy"}
            mock_storage_health.return_value = {"status": "healthy"}
            
            response = await test_client.get("/health")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["status"] == "unhealthy"
        assert "errors" in data
        assert any("MongoDB" in error for error in data["errors"])

    async def test_health_check_exception_handling(self, test_client: AsyncClient):
        """Test health check with exception during health checks."""
        with patch('src.api.health.health_check_database') as mock_db_health:
            mock_db_health.side_effect = Exception("Unexpected error")
            
            response = await test_client.get("/health")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["status"] == "unhealthy"
        assert "errors" in data


class TestConcurrentRequests:
    """Test API behavior under concurrent load."""

    async def test_concurrent_health_checks(self, test_client: AsyncClient):
        """Test multiple concurrent health check requests."""
        with patch('src.api.health.health_check_database') as mock_db_health, \
             patch('src.api.health.health_check_queue') as mock_queue_health, \
             patch('src.api.health.health_check_storage') as mock_storage_health:
            
            mock_db_health.return_value = {"status": "healthy"}
            mock_queue_health.return_value = {"status": "healthy"}
            mock_storage_health.return_value = {"status": "healthy"}
            
            async def make_health_request():
                return await test_client.get("/health")
            
            # Make 10 concurrent requests
            tasks = [make_health_request() for _ in range(10)]
            responses = await asyncio.gather(*tasks)
        
        # All requests should succeed
        for response in responses:
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "status" in data

    async def test_concurrent_dataset_listing(
        self,
        test_client: AsyncClient,
        mock_database_service: AsyncMock
    ):
        """Test concurrent dataset listing requests."""
        async def make_dataset_request():
            return await test_client.get("/datasets")
        
        # Make 5 concurrent requests
        tasks = [make_dataset_request() for _ in range(5)]
        responses = await asyncio.gather(*tasks)
        
        # All requests should succeed
        for response in responses:
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "datasets" in data


class TestErrorResponses:
    """Test consistent error response formats."""

    async def test_404_error_format(self, test_client: AsyncClient):
        """Test 404 error response format."""
        response = await test_client.get("/datasets/507f1f77bcf86cd799439011")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "detail" in data

    async def test_422_validation_error_format(self, test_client: AsyncClient):
        """Test 422 validation error response format."""
        response = await test_client.post("/datasets/import", json={})
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], list)

    async def test_500_error_format(
        self,
        test_client: AsyncClient,
        mock_database_service: AsyncMock
    ):
        """Test 500 internal server error format."""
        mock_database_service.list_datasets.side_effect = Exception("Database error")
        
        response = await test_client.get("/datasets")
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "error" in data or "detail" in data


class TestRootEndpoint:
    """Test root API information endpoint."""

    async def test_root_endpoint(self, test_client: AsyncClient):
        """Test root endpoint returns API information."""
        response = await test_client.get("/")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["service"] == "YOLO Dataset Management API"
        assert "version" in data
        assert "documentation" in data
        assert "health" in data
        assert data["health"] == "/health"
