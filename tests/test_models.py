"""
Essential model tests for YOLO Dataset Management.
Tests actual model fields and validation that exist in the codebase.
"""

import pytest
from datetime import datetime
from typing import Dict, Any
from pydantic import ValidationError
from bson import ObjectId

from src.models.api import ImportRequest, ImportResponse, DatasetListResponse
from src.models.database import Dataset, ImportJob, Image
from src.models.yolo import YOLOConfig, YOLOBoundingBox, YOLOAnnotation


class TestAPIModels:
    """Test API request/response models with actual fields."""

    def test_import_request_valid(self):
        """Test valid import request with actual fields."""
        request = ImportRequest(
            name="Test Dataset",
            description="A test dataset",
            yolo_config_url="https://example.com/config.yaml",
            dataset_url="https://example.com/dataset.zip"
        )
        
        assert request.name == "Test Dataset"
        assert request.description == "A test dataset"
        assert str(request.yolo_config_url) == "https://example.com/config.yaml"
        assert str(request.dataset_url) == "https://example.com/dataset.zip"

    def test_import_request_validation_failures(self):
        """Test import request validation with invalid data."""
        # Empty name should fail
        with pytest.raises(ValidationError):
            ImportRequest(
                name="",
                yolo_config_url="https://example.com/config.yaml", 
                dataset_url="https://example.com/dataset.zip"
            )
        
        # Invalid URL should fail
        with pytest.raises(ValidationError):
            ImportRequest(
                name="Test",
                yolo_config_url="not-a-url",
                dataset_url="https://example.com/dataset.zip"
            )

    def test_import_request_optional_description(self):
        """Test import request without description."""
        request = ImportRequest(
            name="Test Dataset",
            yolo_config_url="https://example.com/config.yaml",
            dataset_url="https://example.com/dataset.zip"
        )
        assert request.description is None

    def test_import_response_structure(self):
        """Test import response with actual fields."""
        response = ImportResponse(
            job_id="550e8400-e29b-41d4-a716-446655440000",
            status="queued",
            message="Import job started successfully",
            created_at=datetime.now(),
            estimated_completion=datetime.now()
        )
        
        assert response.job_id == "550e8400-e29b-41d4-a716-446655440000"
        assert response.status == "queued"
        assert isinstance(response.created_at, datetime)


class TestDatabaseModels:
    """Test database models with actual MongoDB structure."""

    def test_dataset_model_creation(self):
        """Test dataset model with actual fields."""
        dataset = Dataset(
            name="Test Dataset",
            description="A test dataset",
            status="completed",
            import_job_id="job-123",
            stats={
                "total_images": 100,
                "total_annotations": 250,
                "classes_count": 3
            },
            classes=[
                {"id": 0, "name": "car", "count": 100},
                {"id": 1, "name": "truck", "count": 80},
                {"id": 2, "name": "bus", "count": 70}
            ]
        )
        
        assert dataset.name == "Test Dataset"
        assert dataset.status == "completed"
        assert dataset.stats["total_images"] == 100
        assert len(dataset.classes) == 3

    def test_dataset_with_object_id(self):
        """Test dataset with MongoDB ObjectId."""
        object_id = ObjectId()
        dataset = Dataset(
            id=object_id,
            name="Test Dataset",
            status="completed",
            import_job_id="job-123"
        )
        
        assert dataset.id == object_id
        
        # Test serialization with alias
        serialized = dataset.model_dump(by_alias=True)
        assert "_id" in serialized
        assert serialized["_id"] == object_id

    def test_import_job_model(self):
        """Test import job model with actual fields."""
        job = ImportJob(
            job_id="test-job-123",
            status="processing",
            progress={
                "percentage": 50,
                "current_step": "parsing_annotations"
            },
            request={
                "name": "Test Dataset",
                "config_url": "https://test.com/config.yaml"
            }
        )
        
        assert job.job_id == "test-job-123"
        assert job.status == "processing"
        assert job.progress["percentage"] == 50

    def test_image_model_creation(self):
        """Test image model with actual annotation structure."""
        image = Image(
            dataset_id=ObjectId(),
            filename="image_001.jpg",
            width=640,
            height=480,
            file_size_bytes=245760,
            image_url="gs://bucket/images/image_001.jpg",
            annotations=[
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
            annotation_count=1
        )
        
        assert image.filename == "image_001.jpg"
        assert image.width == 640
        assert image.annotation_count == 1
        assert len(image.annotations) == 1

    def test_image_annotation_validation(self):
        """Test image annotation validation logic."""
        # Test with invalid bbox coordinates
        with pytest.raises(ValidationError):
            Image(
                dataset_id=ObjectId(),
                filename="test.jpg",
                width=640,
                height=480,
                file_size_bytes=1000,
                image_url="test.jpg",
                annotations=[
                    {
                        "class_id": 0,
                        "class_name": "car",
                        "bbox": {
                            "center_x": 1.5,  # Invalid: > 1.0
                            "center_y": 0.5,
                            "width": 0.3,
                            "height": 0.4
                        }
                    }
                ],
                annotation_count=1
            )


class TestYOLOModels:
    """Test YOLO format models with actual ultralytics structure."""

    def test_yolo_bounding_box_valid(self):
        """Test valid YOLO bounding box coordinates."""
        bbox = YOLOBoundingBox(
            center_x=0.5,
            center_y=0.6,
            width=0.3,
            height=0.4
        )
        
        assert bbox.center_x == 0.5
        assert bbox.center_y == 0.6
        assert bbox.width == 0.3
        assert bbox.height == 0.4

    def test_yolo_bounding_box_validation(self):
        """Test YOLO bounding box coordinate validation."""
        # Test out of range coordinates
        with pytest.raises(ValidationError):
            YOLOBoundingBox(
                center_x=1.5,  # Must be 0.0-1.0
                center_y=0.5,
                width=0.3,
                height=0.4
            )
        
        with pytest.raises(ValidationError):
            YOLOBoundingBox(
                center_x=0.5,
                center_y=-0.1,  # Must be 0.0-1.0
                width=0.3,
                height=0.4
            )

    def test_yolo_config_ultralytics_format(self):
        """Test YOLOConfig with real ultralytics format."""
        # Test with dict format (real ultralytics)
        config = YOLOConfig(
            path="/datasets/traffic",
            train="images/train",
            val="images/val",
            names={
                0: "car",
                1: "truck", 
                2: "bus"
            }
        )
        
        assert config.nc == 3
        assert config.class_names == ["car", "truck", "bus"]
        assert config.train == "images/train"

    def test_yolo_config_from_yaml(self):
        """Test parsing YOLO config from YAML."""
        yaml_content = """
path: /datasets/traffic
train: images/train
val: images/val
names:
  0: car
  1: truck
  2: bus
"""
        config = YOLOConfig.from_yaml(yaml_content)
        
        assert config.nc == 3
        assert config.class_names == ["car", "truck", "bus"]
        assert config.path == "/datasets/traffic"

    def test_yolo_config_validation_errors(self):
        """Test YOLOConfig validation failures."""
        # Empty names should fail
        with pytest.raises(ValidationError):
            YOLOConfig(names={})
        
        # Invalid names format should fail
        with pytest.raises(ValidationError):
            YOLOConfig(names={"invalid": "key"})  # Keys must be integers

    def test_yolo_annotation_from_line(self):
        """Test parsing YOLO annotation from text line."""
        class_names = ["car", "truck", "bus"]
        line = "0 0.5 0.6 0.3 0.4"
        
        annotation = YOLOAnnotation.from_yolo_line(line, class_names)
        
        assert annotation.class_id == 0
        assert annotation.class_name == "car"
        assert annotation.bbox.center_x == 0.5
        assert annotation.bbox.center_y == 0.6
        assert annotation.bbox.width == 0.3
        assert annotation.bbox.height == 0.4

    def test_yolo_annotation_parsing_errors(self):
        """Test YOLO annotation parsing error cases."""
        class_names = ["car", "truck"]
        
        # Invalid class ID
        with pytest.raises(ValueError):
            YOLOAnnotation.from_yolo_line("5 0.5 0.5 0.3 0.4", class_names)
        # with pytest.raises(ValidationError):
        #     YOLOAnnotation.from_yolo_line("5 0.5 0.5 0.3 0.4", class_names)
        
        # Invalid coordinate format
        with pytest.raises(ValueError):
            YOLOAnnotation.from_yolo_line("0 invalid 0.5 0.3 0.4", class_names)
        
        # Insufficient values
        with pytest.raises(ValueError):
            YOLOAnnotation.from_yolo_line("0 0.5", class_names)

    def test_coordinate_conversion_methods(self):
        """Test bounding box coordinate conversion."""
        bbox = YOLOBoundingBox(
            center_x=0.5,
            center_y=0.5,
            width=0.3,
            height=0.4
        )
        
        # Convert to absolute coordinates
        absolute = bbox.to_absolute(640, 480)
        assert absolute["center_x"] == 320  # 0.5 * 640
        assert absolute["center_y"] == 240  # 0.5 * 480
        assert absolute["width"] == 192     # 0.3 * 640
        assert absolute["height"] == 192    # 0.4 * 480
        
        # Convert to xyxy format
        xyxy = bbox.to_xyxy(640, 480)
        assert xyxy["x1"] == 224  # 320 - 96
        assert xyxy["y1"] == 144  # 240 - 96
        assert xyxy["x2"] == 416  # 320 + 96
        assert xyxy["y2"] == 336  # 240 + 96


class TestCriticalEdgeCases:
    """Test only essential edge cases that could break the system."""

    def test_boundary_coordinates(self):
        """Test coordinates at exact boundaries."""
        # Test minimum values
        bbox = YOLOBoundingBox(center_x=0.0, center_y=0.0, width=0.0, height=0.0)
        assert bbox.center_x == 0.0
        
        # Test maximum values  
        bbox = YOLOBoundingBox(center_x=1.0, center_y=1.0, width=1.0, height=1.0)
        assert bbox.center_x == 1.0

    def test_large_dataset_stats(self):
        """Test handling of large dataset statistics."""
        dataset = Dataset(
            name="Large Dataset",
            status="completed", 
            import_job_id="job-123",
            stats={
                "total_images": 1000000,
                "total_annotations": 5000000,
                "dataset_size_bytes": 100 * 1024**3  # 100GB
            }
        )
        
        assert dataset.stats["total_images"] == 1000000
        assert dataset.stats["dataset_size_bytes"] == 100 * 1024**3

    def test_mongodb_objectid_serialization(self):
        """Test ObjectId serialization for API responses."""
        object_id = ObjectId()
        dataset = Dataset(
            id=object_id,
            name="Test",
            status="completed",
            import_job_id="job-123"
        )
        
        # JSON serialization should convert ObjectId to string
        json_data = dataset.model_dump(mode="json")
        assert isinstance(json_data["id"], str)
        assert json_data["id"] == str(object_id)