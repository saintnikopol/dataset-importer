"""
Comprehensive API tests for YOLO Dataset Management System.

Tests all FastAPI endpoints including dataset import, listing, image management,
and health checks with proper async testing, mocking, and error handling.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient
from fastapi import status
from bson import ObjectId

from src.main import app
from src.models.api import ImportRequest, ImportResponse, JobStatusResponse
from src.models.database import Dataset, ImportJob, Image
from src.utils.exceptions import DatabaseError, ProcessingError


@pytest.fixture
async def async_client():
    """Async HTTP client for API testing."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


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
        "filters_applied": {}
    }
    
    return mock


@pytest.fixture
def mock_job_queue():
    """Mock job queue service."""
    mock = AsyncMock()
    mock.enqueue_import_job.return_value = None
    return mock


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
        async_client: AsyncClient,
        sample_import_request_data: Dict[str, Any],
        mock_database_service: AsyncMock,
        mock_job_queue: AsyncMock
    ):
        """Test successful dataset import with all fields."""
        with patch('src.api.import_jobs.get_database', return_value=mock_database_service), \
             patch('src.api.import_jobs.get_job_queue', return_value=mock_job_queue):
            
            response = await async_client.post(
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
        async_client: AsyncClient,
        mock_database_service: AsyncMock,
        mock_job_queue: AsyncMock
    ):
        """Test import without optional description field."""
        request_data = {
            "name": "Test Dataset",
            "yolo_config_url": "https://example.com/config.yaml",
            "dataset_url": "https://example.com/dataset.zip"
        }
        
        with patch('src.api.import_jobs.get_database', return_value=mock_database_service), \
             patch('src.api.import_jobs.get_job_queue', return_value=mock_job_queue):
            
            response = await async_client.post(
                "/datasets/import",
                json=request_data
            )
        
        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert data["status"] == "queued"

    async def test_import_invalid_empty_name(self, async_client: AsyncClient):
        """Test import with empty name."""
        request_data = {
            "name": "",
            "yolo_config_url": "https://example.com/config.yaml",
            "dataset_url": "https://example.com/dataset.zip"
        }
        
        response = await async_client.post("/datasets/import", json=request_data)
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        data = response.json()
        assert "detail" in data

    async def test_import_invalid_urls(self, async_client: AsyncClient):
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
            response = await async_client.post("/datasets/import", json=request_data)
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_import_missing_required_fields(self, async_client: AsyncClient):
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
            response = await async_client.post("/datasets/import", json=request_data)
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_import_database_error(
        self,
        async_client: AsyncClient,
        sample_import_request_data: Dict[str, Any],
        mock_database_service: AsyncMock
    ):
        """Test import with database error."""
        mock_database_service.create_import_job.side_effect = DatabaseError("Database connection failed")
        
        with patch('src.api.import_jobs.get_database', return_value=mock_database_service):
            response = await async_client.post(
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
        async_client: AsyncClient,
        mock_database_service: AsyncMock
    ):
        """Test getting status for queued job."""
        job_id = "550e8400-e29b-41d4-a716-446655440000"
        
        mock_database_service.get_import_job.return_value = {
            "job_id": job_id,
            "status": "queued",
            "progress": {
                "percentage": 0,
                "current_step": "queued",
                "steps_completed": [],
                "total_steps": 6
            },
            "started_at": None,
            "completed_at": None,
            "estimated_completion": datetime.now() + timedelta(minutes=20)
        }
        
        with patch('src.api.import_jobs.get_database', return_value=mock_database_service):
            response = await async_client.get(f"/datasets/import/{job_id}/status")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["job_id"] == job_id
        assert data["status"] == "queued"
        assert data["progress"]["percentage"] == 0
        assert "estimated_completion" in data

    async def test_get_job_status_processing(
        self,
        async_client: AsyncClient,
        mock_database_service: AsyncMock
    ):
        """Test getting status for processing job."""
        job_id = "550e8400-e29b-41d4-a716-446655440000"
        
        mock_database_service.get_import_job.return_value = {
            "job_id": job_id,
            "status": "processing",
            "progress": {
                "percentage": 65,
                "current_step": "parsing_annotations",
                "steps_completed": ["download_config", "download_dataset", "extract_archive"],
                "current_step_progress": "6500/10000 annotations processed",
                "total_steps": 6
            },
            "started_at": datetime.now() - timedelta(minutes=5),
            "completed_at": None,
            "estimated_completion": datetime.now() + timedelta(minutes=10)
        }
        
        with patch('src.api.import_jobs.get_database', return_value=mock_database_service):
            response = await async_client.get(f"/datasets/import/{job_id}/status")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["job_id"] == job_id
        assert data["status"] == "processing"
        assert data["progress"]["percentage"] == 65
        assert data["progress"]["current_step"] == "parsing_annotations"
        assert len(data["progress"]["steps_completed"]) == 3

    async def test_get_job_status_completed(
        self,
        async_client: AsyncClient,
        mock_database_service: AsyncMock
    ):
        """Test getting status for completed job."""
        job_id = "550e8400-e29b-41d4-a716-446655440000"
        dataset_id = "507f1f77bcf86cd799439011"
        
        mock_database_service.get_import_job.return_value = {
            "job_id": job_id,
            "status": "completed",
            "progress": {"percentage": 100, "total_steps": 6},
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
        
        with patch('src.api.import_jobs.get_database', return_value=mock_database_service):
            response = await async_client.get(f"/datasets/import/{job_id}/status")
        
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
        async_client: AsyncClient,
        mock_database_service: AsyncMock
    ):
        """Test getting status for failed job."""
        job_id = "550e8400-e29b-41d4-a716-446655440000"
        
        mock_database_service.get_import_job.return_value = {
            "job_id": job_id,
            "status": "failed",
            "progress": {"percentage": 30},
            "error": {
                "code": "invalid_yolo_format",
                "message": "YOLO dataset archive missing required directories",
                "details": "Archive must contain 'images/' and 'labels/' directories"
            },
            "started_at": datetime.now() - timedelta(minutes=10),
            "completed_at": datetime.now() - timedelta(minutes=5)
        }
        
        with patch('src.api.import_jobs.get_database', return_value=mock_database_service):
            response = await async_client.get(f"/datasets/import/{job_id}/status")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["job_id"] == job_id
        assert data["status"] == "failed"
        assert "error" in data
        assert data["error"]["code"] == "invalid_yolo_format"

    async def test_get_job_status_not_found(
        self,
        async_client: AsyncClient,
        mock_database_service: AsyncMock
    ):
        """Test getting status for non-existent job."""
        job_id = "550e8400-e29b-41d4-a716-446655440000"
        mock_database_service.get_import_job.return_value = None
        
        with patch('src.api.import_jobs.get_database', return_value=mock_database_service):
            response = await async_client.get(f"/datasets/import/{job_id}/status")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "not found" in data["detail"].lower()

    async def test_get_job_status_invalid_uuid(self, async_client: AsyncClient):
        """Test getting status with invalid job ID format."""
        invalid_job_id = "invalid-job-id-format"
        
        response = await async_client.get(f"/datasets/import/{invalid_job_id}/status")
        
        # The endpoint should still work, but return 404 if not found
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_400_BAD_REQUEST]


class TestDatasetListing:
    """Test dataset listing endpoints."""

    async def test_list_datasets_empty(
        self,
        async_client: AsyncClient,
        mock_database_service: AsyncMock
    ):
        """Test listing datasets when none exist."""
        with patch('src.api.datasets.get_database', return_value=mock_database_service):
            response = await async_client.get("/datasets")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["datasets"] == []
        assert data["pagination"]["total_items"] == 0
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["limit"] == 20

    async def test_list_datasets_with_data(
        self,
        async_client: AsyncClient,
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
        
        with patch('src.api.datasets.get_database', return_value=mock_database_service):
            response = await async_client.get("/datasets")
        
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
        async_client: AsyncClient,
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
        
        with patch('src.api.datasets.get_database', return_value=mock_database_service):
            response = await async_client.get(f"/datasets?page={page}&limit={limit}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["pagination"]["page"] == page
        assert data["pagination"]["limit"] == limit

    @pytest.mark.parametrize("status_filter", ["completed", "processing", "failed", "queued"])
    async def test_list_datasets_status_filtering(
        self,
        async_client: AsyncClient,
        mock_database_service: AsyncMock,
        status_filter: str
    ):
        """Test dataset listing with status filtering."""
        with patch('src.api.datasets.get_database', return_value=mock_database_service):
            response = await async_client.get(f"/datasets?status={status_filter}")
        
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
        async_client: AsyncClient,
        mock_database_service: AsyncMock,
        sort_by: str,
        sort_order: str
    ):
        """Test dataset listing with different sorting options."""
        with patch('src.api.datasets.get_database', return_value=mock_database_service):
            response = await async_client.get(f"/datasets?sort_by={sort_by}&sort_order={sort_order}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["filters_applied"]["sort_by"] == sort_by
        assert data["filters_applied"]["sort_order"] == sort_order

    async def test_list_datasets_invalid_pagination(self, async_client: AsyncClient):
        """Test dataset listing with invalid pagination parameters."""
        invalid_params = [
            "?page=0",  # Page must be >= 1
            "?limit=0",  # Limit must be >= 1
            "?limit=101",  # Limit must be <= 100
            "?page=invalid",  # Page must be integer
            "?limit=invalid"  # Limit must be integer
        ]
        
        for params in invalid_params:
            response = await async_client.get(f"/datasets{params}")
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_list_datasets_invalid_sort_order(self, async_client: AsyncClient):
        """Test dataset listing with invalid sort order."""
        response = await async_client.get("/datasets?sort_order=invalid")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_list_datasets_database_error(
        self,
        async_client: AsyncClient,
        mock_database_service: AsyncMock
    ):
        """Test dataset listing with database error."""
        mock_database_service.list_datasets.side_effect = DatabaseError("Database connection failed")
        
        with patch('src.api.datasets.get_database', return_value=mock_database_service):
            response = await async_client.get("/datasets")
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestDatasetDetails:
    """Test individual dataset detail endpoints."""

    async def test_get_dataset_valid_id(
        self,
        async_client: AsyncClient,
        mock_database_service: AsyncMock,
        sample_dataset_data: Dict[str, Any]
    ):
        """Test getting dataset details with valid ID."""
        dataset_id = "507f1f77bcf86cd799439011"
        mock_database_service.get_dataset.return_value = sample_dataset_data
        
        with patch('src.api.datasets.get_database', return_value=mock_database_service):
            response = await async_client.get(f"/datasets/{dataset_id}")
        
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
        async_client: AsyncClient,
        mock_database_service: AsyncMock
    ):
        """Test getting non-existent dataset."""
        dataset_id = "507f1f77bcf86cd799439011"
        mock_database_service.get_dataset.return_value = None
        
        with patch('src.api.datasets.get_database', return_value=mock_database_service):
            response = await async_client.get(f"/datasets/{dataset_id}")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "not found" in data["detail"].lower()

    async def test_get_dataset_invalid_object_id(self, async_client: AsyncClient):
        """Test getting dataset with invalid ObjectId format."""
        invalid_id = "invalid-object-id"
        
        response = await async_client.get(f"/datasets/{invalid_id}")
        
        # Should return 404 since invalid ObjectId won't be found
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_get_dataset_database_error(
        self,
        async_client: AsyncClient,
        mock_database_service: AsyncMock
    ):
        """Test getting dataset with database error."""
        dataset_id = "507f1f77bcf86cd799439011"
        mock_database_service.get_dataset.side_effect = DatabaseError("Database connection failed")
        
        with patch('src.api.datasets.get_database', return_value=mock_database_service):
            response = await async_client.get(f"/datasets/{dataset_id}")
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestDatasetImages:
    """Test dataset image listing endpoints."""

    async def test_list_images_valid_dataset(
        self,
        async_client: AsyncClient,
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
            "filters_applied": {}
        }
        
        with patch('src.api.datasets.get_database', return_value=mock_database_service):
            response = await async_client.get(f"/datasets/{dataset_id}/images")
        
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
        async_client: AsyncClient,
        mock_database_service: AsyncMock,
        sample_dataset_data: Dict[str, Any]
    ):
        """Test listing images for dataset with no images."""
        dataset_id = "507f1f77bcf86cd799439011"
        
        mock_database_service.get_dataset.return_value = sample_dataset_data
        # Default mock returns empty images list
        
        with patch('src.api.datasets.get_database', return_value=mock_database_service):
            response = await async_client.get(f"/datasets/{dataset_id}/images")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["dataset_id"] == dataset_id
        assert data["images"] == []
        assert data["pagination"]["total_items"] == 0

    async def test_list_images_pagination(
        self,
        async_client: AsyncClient,
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
            "filters_applied": {}
        }
        
        with patch('src.api.datasets.get_database', return_value=mock_database_service):
            response = await async_client.get(f"/datasets/{dataset_id}/images?page={page}&limit={limit}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["pagination"]["page"] == page
        assert data["pagination"]["limit"] == limit

    @pytest.mark.parametrize("class_filter", ["car", "truck", "bus"])
    async def test_list_images_class_filtering(
        self,
        async_client: AsyncClient,
        mock_database_service: AsyncMock,
        sample_dataset_data: Dict[str, Any],
        class_filter: str
    ):
        """Test image listing with class filtering."""
        dataset_id = "507f1f77bcf86cd799439011"
        
        mock_database_service.get_dataset.return_value = sample_dataset_data
        
        with patch('src.api.datasets.get_database', return_value=mock_database_service):
            response = await async_client.get(f"/datasets/{dataset_id}/images?class_filter={class_filter}")
        
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
        async_client: AsyncClient,
        mock_database_service: AsyncMock,
        sample_dataset_data: Dict[str, Any],
        has_annotations: bool
    ):
        """Test image listing with annotation presence filtering."""
        dataset_id = "507f1f77bcf86cd799439011"
        
        mock_database_service.get_dataset.return_value = sample_dataset_data
        
        with patch('src.api.datasets.get_database', return_value=mock_database_service):
            response = await async_client.get(f"/datasets/{dataset_id}/images?has_annotations={has_annotations}")
        
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
        async_client: AsyncClient,
        mock_database_service: AsyncMock,
        sample_dataset_data: Dict[str, Any],
        sort_by: str,
        sort_order: str
    ):
        """Test image listing with sorting options."""
        dataset_id = "507f1f77bcf86cd799439011"
        
        mock_database_service.get_dataset.return_value = sample_dataset_data
        
        with patch('src.api.datasets.get_database', return_value=mock_database_service):
            response = await async_client.get(
                f"/datasets/{dataset_id}/images?sort_by={sort_by}&sort_order={sort_order}"
            )
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify sorting parameters were passed
        call_kwargs = mock_database_service.list_dataset_images.call_args[1]
        assert call_kwargs["sort_by"] == sort_by
        assert call_kwargs["sort_order"] == sort_order

    async def test_list_images_dataset_not_found(
        self,
        async_client: AsyncClient,
        mock_database_service: AsyncMock
    ):
        """Test listing images for non-existent dataset."""
        dataset_id = "507f1f77bcf86cd799439011"
        mock_database_service.get_dataset.return_value = None
        
        with patch('src.api.datasets.get_database', return_value=mock_database_service):
            response = await async_client.get(f"/datasets/{dataset_id}/images")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_list_images_invalid_pagination(
        self,
        async_client: AsyncClient,
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
            with patch('src.api.datasets.get_database', return_value=mock_database_service):
                response = await async_client.get(f"/datasets/{dataset_id}/images{params}")
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestHealthCheck:
    """Test health check endpoint."""

    async def test_health_check_healthy(self, async_client: AsyncClient):
        """Test healthy service response."""
        with patch('src.api.health.health_check_database') as mock_db_health, \
             patch('src.api.health.health_check_queue') as mock_queue_health, \
             patch('src.api.health.health_check_storage') as mock_storage_health:
            
            # Mock all dependencies as healthy
            mock_db_health.return_value = {"status": "healthy"}
            mock_queue_health.return_value = {"status": "healthy"}
            mock_storage_health.return_value = {"status": "healthy"}
            
            response = await async_client.get("/health")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data
        assert "dependencies" in data
        assert data["dependencies"]["mongodb"] == "healthy"
        assert data["dependencies"]["job_queue"] == "healthy"
        assert data["dependencies"]["storage"] == "healthy"

    async def test_health_check_unhealthy_dependencies(self, async_client: AsyncClient):
        """Test unhealthy dependencies response."""
        with patch('src.api.health.health_check_database') as mock_db_health, \
             patch('src.api.health.health_check_queue') as mock_queue_health, \
             patch('src.api.health.health_check_storage') as mock_storage_health:
            
            # Mock database as unhealthy
            mock_db_health.return_value = {"status": "unhealthy", "error": "Connection timeout"}
            mock_queue_health.return_value = {"status": "healthy"}
            mock_storage_health.return_value = {"status": "healthy"}
            
            response = await async_client.get("/health")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["status"] == "unhealthy"
        assert "errors" in data
        assert any("MongoDB" in error for error in data["errors"])

    async def test_health_check_exception_handling(self, async_client: AsyncClient):
        """Test health check with exception during health checks."""
        with patch('src.api.health.health_check_database') as mock_db_health:
            mock_db_health.side_effect = Exception("Unexpected error")
            
            response = await async_client.get("/health")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["status"] == "unhealthy"
        assert "errors" in data


class TestConcurrentRequests:
    """Test API behavior under concurrent load."""

    async def test_concurrent_health_checks(self, async_client: AsyncClient):
        """Test multiple concurrent health check requests."""
        async def make_health_request():
            return await async_client.get("/health")
        
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
        async_client: AsyncClient,
        mock_database_service: AsyncMock
    ):
        """Test concurrent dataset listing requests."""
        async def make_dataset_request():
            with patch('src.api.datasets.get_database', return_value=mock_database_service):
                return await async_client.get("/datasets")
        
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

    async def test_404_error_format(self, async_client: AsyncClient):
        """Test 404 error response format."""
        response = await async_client.get("/datasets/507f1f77bcf86cd799439011")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "detail" in data

    async def test_422_validation_error_format(self, async_client: AsyncClient):
        """Test 422 validation error response format."""
        response = await async_client.post("/datasets/import", json={})
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], list)

    async def test_500_error_format(
        self,
        async_client: AsyncClient,
        mock_database_service: AsyncMock
    ):
        """Test 500 internal server error format."""
        mock_database_service.list_datasets.side_effect = Exception("Database error")
        
        with patch('src.api.datasets.get_database', return_value=mock_database_service):
            response = await async_client.get("/datasets")
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "error" in data or "detail" in data


class TestRootEndpoint:
    """Test root API information endpoint."""

    async def test_root_endpoint(self, async_client: AsyncClient):
        """Test root endpoint returns API information."""
        response = await async_client.get("/")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["service"] == "YOLO Dataset Management API"
        assert "version" in data
        assert "documentation" in data
        assert "health" in data
        assert data["health"] == "/health"
