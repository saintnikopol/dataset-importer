"""
API request and response models for YOLO Dataset Management.
Defines the structure of HTTP requests and responses.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl, field_validator
from enum import Enum


class ImportRequest(BaseModel):
    """Request model for dataset import."""
    name: str = Field(..., min_length=1, max_length=255, description="Dataset name")
    description: Optional[str] = Field(None, max_length=1000, description="Dataset description")
    yolo_config_url: HttpUrl = Field(..., description="URL to YOLO config file (dataset.yaml)")
    annotations_url: HttpUrl = Field(..., description="URL to annotations archive (.zip)")
    images_url: HttpUrl = Field(..., description="URL to images archive (.zip)")
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """Validate dataset name."""
        if not v.strip():
            raise ValueError('Dataset name cannot be empty')
        return v.strip()
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Traffic Detection Dataset",
                "description": "Urban traffic detection with 3 classes",
                "yolo_config_url": "https://storage.googleapis.com/bucket/dataset.yaml",
                "annotations_url": "https://storage.googleapis.com/bucket/labels.zip",
                "images_url": "https://storage.googleapis.com/bucket/images.zip"
            }
        }
    }


class ImportJobData(BaseModel):
    """Data structure for background job processing."""
    job_id: str = Field(..., description="Unique job identifier")
    name: str = Field(..., description="Dataset name")
    description: Optional[str] = Field(None, description="Dataset description")
    config_url: str = Field(..., description="YOLO config file URL")
    annotations_url: str = Field(..., description="Annotations archive URL")
    images_url: str = Field(..., description="Images archive URL")


class ImportResponse(BaseModel):
    """Response model for dataset import initiation."""
    job_id: str = Field(..., description="Unique job identifier for tracking")
    status: str = Field(..., description="Initial job status")
    message: str = Field(..., description="Human-readable status message")
    created_at: datetime = Field(..., description="Job creation timestamp")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "queued",
                "message": "Import job started successfully",
                "created_at": "2025-07-03T10:00:00Z",
                "estimated_completion": "2025-07-03T10:30:00Z"
            }
        }
    }


class JobStatus(str, Enum):
    """Enumeration of possible job statuses."""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobProgress(BaseModel):
    """Job progress tracking model."""
    percentage: int = Field(..., ge=0, le=100, description="Completion percentage")
    current_step: str = Field(..., description="Current processing step")
    steps_completed: List[str] = Field(default_factory=list, description="Completed steps")
    current_step_progress: Optional[str] = Field(None, description="Progress within current step")
    total_steps: int = Field(default=5, description="Total number of processing steps")


class JobStatusResponse(BaseModel):
    """Response model for job status queries."""
    job_id: str = Field(..., description="Job identifier")
    status: JobStatus = Field(..., description="Current job status")
    progress: JobProgress = Field(..., description="Job progress details")
    dataset_id: Optional[str] = Field(None, description="Created dataset ID (available when completed)")
    started_at: Optional[datetime] = Field(None, description="Job start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Job completion timestamp")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")
    error: Optional[Dict[str, Any]] = Field(None, description="Error details (if failed)")
    summary: Optional[Dict[str, Any]] = Field(None, description="Import summary (if completed)")


class PaginationInfo(BaseModel):
    """Pagination information model."""
    page: int = Field(..., ge=1, description="Current page number")
    limit: int = Field(..., ge=1, le=200, description="Items per page")
    total_pages: int = Field(..., ge=0, description="Total number of pages")
    total_items: int = Field(..., ge=0, description="Total number of items")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")


class DatasetSummary(BaseModel):
    """Summary information about a dataset."""
    id: str = Field(..., description="Dataset identifier")
    name: str = Field(..., description="Dataset name")
    description: Optional[str] = Field(None, description="Dataset description")
    status: str = Field(..., description="Dataset status")
    created_at: datetime = Field(..., description="Creation timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    stats: Dict[str, Any] = Field(..., description="Dataset statistics")
    classes: List[str] = Field(..., description="Class names")


class DatasetListResponse(BaseModel):
    """Response model for dataset listing."""
    datasets: List[DatasetSummary] = Field(..., description="List of datasets")
    pagination: PaginationInfo = Field(..., description="Pagination information")
    filters_applied: Dict[str, Any] = Field(default_factory=dict, description="Applied filters")


class ImageAnnotation(BaseModel):
    """Image annotation model."""
    class_id: int = Field(..., ge=0, description="Class identifier")
    class_name: str = Field(..., description="Class name")
    bbox: Dict[str, float] = Field(..., description="Bounding box coordinates (YOLO format)")


class ImageInfo(BaseModel):
    """Image information model."""
    id: str = Field(..., description="Image identifier")
    filename: str = Field(..., description="Image filename")
    width: int = Field(..., gt=0, description="Image width in pixels")
    height: int = Field(..., gt=0, description="Image height in pixels")
    file_size_bytes: int = Field(..., ge=0, description="File size in bytes")
    image_url: str = Field(..., description="Cloud storage URL")
    annotations: List[ImageAnnotation] = Field(..., description="YOLO annotations")
    annotation_count: int = Field(..., ge=0, description="Number of annotations")


class DatasetImagesResponse(BaseModel):
    """Response model for dataset images listing."""
    dataset_id: str = Field(..., description="Dataset identifier")
    images: List[ImageInfo] = Field(..., description="List of images with annotations")
    pagination: PaginationInfo = Field(..., description="Pagination information")
    filters_applied: Dict[str, Any] = Field(..., description="Applied filters")


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str = Field(..., description="Overall health status")
    timestamp: datetime = Field(..., description="Health check timestamp")
    version: str = Field(..., description="API version")
    dependencies: Dict[str, str] = Field(..., description="Dependency health status")
    errors: Optional[List[str]] = Field(None, description="Error messages (if unhealthy)")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "healthy",
                "timestamp": "2025-07-03T10:00:00Z",
                "version": "1.0.0",
                "dependencies": {
                    "mongodb": "connected",
                    "cloud_storage": "connected",
                    "job_queue": "operational"
                }
            }
        }
    }


class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(..., description="Error timestamp")
    request_id: Optional[str] = Field(None, description="Request identifier for tracking")
