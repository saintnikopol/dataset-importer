"""
Database models for MongoDB collections.
Defines the structure of documents stored in the database.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from bson import ObjectId
from pydantic import BaseModel, Field, field_validator


class PyObjectId(ObjectId):
    """Custom ObjectId type for Pydantic models."""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)
    
    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")


class Dataset(BaseModel):
    """Database model for datasets collection."""
    
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    name: str = Field(..., description="Dataset name")
    description: Optional[str] = Field(None, description="Dataset description")
    status: str = Field(..., description="Dataset status")
    created_at: datetime = Field(..., description="Creation timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    import_job_id: str = Field(..., description="Reference to import job")
    
    # Dataset statistics
    stats: Dict[str, Any] = Field(default_factory=dict, description="Dataset statistics")
    
    # YOLO classes (from dataset.yaml)
    classes: List[Dict[str, Any]] = Field(default_factory=list, description="Class definitions")
    
    # Cloud Storage paths (NO file data in MongoDB)
    storage: Dict[str, str] = Field(default_factory=dict, description="Storage paths")
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str},
        "json_schema_extra": {
            "example": {
                "name": "Traffic Detection Dataset",
                "description": "Urban traffic detection with 3 classes",
                "status": "completed",
                "created_at": "2025-07-03T10:00:00Z",
                "completed_at": "2025-07-03T10:15:00Z",
                "import_job_id": "550e8400-e29b-41d4-a716-446655440000",
                "stats": {
                    "total_images": 10000,
                    "total_annotations": 25000,
                    "classes_count": 3,
                    "dataset_size_bytes": 2147483648
                },
                "classes": [
                    {"id": 0, "name": "person", "count": 15000},
                    {"id": 1, "name": "car", "count": 8000},
                    {"id": 2, "name": "bicycle", "count": 2000}
                ],
                "storage": {
                    "images_path": "gs://bucket/datasets/ds_abc123def456/images/",
                    "labels_path": "gs://bucket/datasets/ds_abc123def456/labels/"
                }
            }
        }
    }


class ImportJob(BaseModel):
    """Database model for import_jobs collection."""
    
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    job_id: str = Field(..., description="External job ID (UUID)")
    status: str = Field(..., description="Job status")
    
    # Progress tracking
    progress: Dict[str, Any] = Field(default_factory=dict, description="Job progress")
    
    # Original request data
    request: Dict[str, Any] = Field(..., description="Original import request")
    
    # Timestamps
    created_at: datetime = Field(..., description="Job creation timestamp")
    started_at: Optional[datetime] = Field(None, description="Job start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Job completion timestamp")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion")
    
    # Result (populated on completion)
    dataset_id: Optional[PyObjectId] = Field(None, description="Created dataset ID")
    
    # Error info (populated on failure)
    error: Optional[Dict[str, Any]] = Field(None, description="Error details")
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    }


class Image(BaseModel):
    """Database model for images collection."""
    
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    dataset_id: PyObjectId = Field(..., description="Parent dataset reference")
    
    # Image file info
    filename: str = Field(..., description="Image filename")
    width: int = Field(..., gt=0, description="Image width in pixels")
    height: int = Field(..., gt=0, description="Image height in pixels")
    file_size_bytes: int = Field(..., ge=0, description="File size in bytes")
    
    # Cloud Storage URL (NO binary data in MongoDB)
    image_url: str = Field(..., description="Cloud storage URL")
    
    # YOLO annotations (embedded for fast access)
    annotations: List[Dict[str, Any]] = Field(default_factory=list, description="YOLO annotations")
    
    # Quick stats
    annotation_count: int = Field(..., ge=0, description="Number of annotations")
    
    # Processing metadata
    processed_at: datetime = Field(..., description="Processing timestamp")
    
    @field_validator('annotations')
    @classmethod
    def validate_annotations(cls, v):
        """Validate annotation format."""
        for annotation in v:
            required_fields = ['class_id', 'class_name', 'bbox']
            for field in required_fields:
                if field not in annotation:
                    raise ValueError(f"Missing required field: {field}")
            
            # Validate bounding box format
            bbox = annotation['bbox']
            required_bbox_fields = ['center_x', 'center_y', 'width', 'height']
            for field in required_bbox_fields:
                if field not in bbox:
                    raise ValueError(f"Missing bbox field: {field}")
                
                # Validate normalized coordinates (0.0 to 1.0)
                value = bbox[field]
                if not isinstance(value, (int, float)) or not 0.0 <= value <= 1.0:
                    raise ValueError(f"Invalid bbox coordinate: {field}={value}")
        
        return v
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str},
        "json_schema_extra": {
            "example": {
                "dataset_id": "507f1f77bcf86cd799439011",
                "filename": "traffic_001.jpg",
                "width": 1920,
                "height": 1080,
                "file_size_bytes": 245760,
                "image_url": "gs://bucket/datasets/ds_abc123def456/images/traffic_001.jpg",
                "annotations": [
                    {
                        "class_id": 0,
                        "class_name": "person",
                        "bbox": {
                            "center_x": 0.5,
                            "center_y": 0.6,
                            "width": 0.1,
                            "height": 0.3
                        }
                    }
                ],
                "annotation_count": 1,
                "processed_at": "2025-07-03T10:10:00Z"
            }
        }
    }


# Collection names for database operations
DATASETS_COLLECTION = "datasets"
IMPORT_JOBS_COLLECTION = "import_jobs"
IMAGES_COLLECTION = "images"
