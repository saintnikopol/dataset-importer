# Updated src/models/yolo.py - Fix YOLOConfig to handle real ultralytics format

"""
YOLO format models and validation.
Defines the structure of YOLO datasets, annotations, and configuration files.
"""

from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field, field_validator
import yaml
from io import StringIO


class YOLOBoundingBox(BaseModel):
    """YOLO bounding box with normalized coordinates."""
    
    center_x: float = Field(..., description="Normalized center X coordinate (0.0-1.0)")
    center_y: float = Field(..., description="Normalized center Y coordinate (0.0-1.0)")
    width: float = Field(..., description="Normalized width (0.0-1.0)")
    height: float = Field(..., description="Normalized height (0.0-1.0)")
    
    @field_validator('center_x', 'center_y', 'width', 'height')
    @classmethod
    def validate_normalized_coords(cls, v):
        """Validate that coordinates are normalized between 0.0 and 1.0."""
        if not isinstance(v, (int, float)):
            raise ValueError('Coordinate must be a number')
        if not 0.0 <= v <= 1.0:
            raise ValueError('YOLO coordinates must be normalized (0.0-1.0)')
        return float(v)
    
    def to_absolute(self, image_width: int, image_height: int) -> Dict[str, int]:
        """Convert normalized coordinates to absolute pixel coordinates."""
        return {
            "center_x": int(self.center_x * image_width),
            "center_y": int(self.center_y * image_height),
            "width": int(self.width * image_width),
            "height": int(self.height * image_height)
        }
    
    def to_xyxy(self, image_width: int, image_height: int) -> Dict[str, int]:
        """Convert to top-left, bottom-right coordinates."""
        abs_coords = self.to_absolute(image_width, image_height)
        half_width = abs_coords["width"] // 2
        half_height = abs_coords["height"] // 2
        
        return {
            "x1": abs_coords["center_x"] - half_width,
            "y1": abs_coords["center_y"] - half_height,
            "x2": abs_coords["center_x"] + half_width,
            "y2": abs_coords["center_y"] + half_height
        }
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "center_x": 0.5,
                "center_y": 0.6,
                "width": 0.2,
                "height": 0.3
            }
        }
    }


class YOLOAnnotation(BaseModel):
    """Single YOLO annotation (class + bounding box)."""
    
    class_id: int = Field(..., ge=0, description="Class identifier")
    class_name: str = Field(..., description="Human-readable class name")
    bbox: YOLOBoundingBox = Field(..., description="Bounding box coordinates")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Detection confidence")
    
    @field_validator('class_name')
    @classmethod
    def validate_class_name(cls, v):
        """Validate class name is not empty."""
        if not v or not v.strip():
            raise ValueError('Class name cannot be empty')
        return v.strip()
    
    @classmethod
    def from_yolo_line(cls, line: str, class_names: List[str]) -> 'YOLOAnnotation':
        """Parse YOLO annotation from text line."""
        parts = line.strip().split()
        if len(parts) < 5:
            raise ValueError(f"Invalid YOLO annotation line: {line}")
        
        try:
            class_id = int(parts[0])
            center_x = float(parts[1])
            center_y = float(parts[2])
            width = float(parts[3])
            height = float(parts[4])
            confidence = float(parts[5]) if len(parts) > 5 else None
        except (ValueError, IndexError) as e:
            raise ValueError(f"Invalid YOLO annotation format: {line}") from e
        
        if class_id >= len(class_names):
            raise ValueError(f"Class ID {class_id} exceeds available classes")
        
        return cls(
            class_id=class_id,
            class_name=class_names[class_id],
            bbox=YOLOBoundingBox(
                center_x=center_x,
                center_y=center_y,
                width=width,
                height=height
            ),
            confidence=confidence
        )
    
    def to_yolo_line(self) -> str:
        """Convert annotation to YOLO text format."""
        line = f"{self.class_id} {self.bbox.center_x} {self.bbox.center_y} {self.bbox.width} {self.bbox.height}"
        if self.confidence is not None:
            line += f" {self.confidence}"
        return line


class YOLOConfig(BaseModel):
    """YOLO dataset configuration (dataset.yaml) - Compatible with real Ultralytics format."""
    
    path: Optional[str] = Field(None, description="Dataset root path")
    train: Optional[str] = Field(None, description="Training set path")
    val: Optional[str] = Field(None, description="Validation set path")
    test: Optional[str] = Field(None, description="Test set path")
    
    # Real ultralytics format uses names as dict, not nc + names list
    names: Union[List[str], Dict[int, str]] = Field(..., description="Class names (list or dict)")
    
    # Computed property for number of classes
    @property
    def nc(self) -> int:
        """Number of classes (computed from names)."""
        if isinstance(self.names, dict):
            return len(self.names)
        return len(self.names)
    
    @property
    def class_names(self) -> List[str]:
        """Get class names as a list."""
        if isinstance(self.names, dict):
            # Convert dict to sorted list by key
            max_key = max(self.names.keys()) if self.names else -1
            result = [""] * (max_key + 1)
            for idx, name in self.names.items():
                result[idx] = name
            return result
        return self.names
    
    @field_validator('names')
    @classmethod
    def validate_names(cls, v):
        """Validate class names format."""
        if isinstance(v, dict):
            # Validate dict format (ultralytics standard)
            if not v:
                raise ValueError("Names dictionary cannot be empty")
            
            # Check all keys are integers
            for key in v.keys():
                if not isinstance(key, int):
                    raise ValueError(f"All keys in names dict must be integers, got {type(key)}")
                if key < 0:
                    raise ValueError(f"Class indices must be non-negative, got {key}")
            
            # Check all values are non-empty strings
            for key, name in v.items():
                if not isinstance(name, str) or not name.strip():
                    raise ValueError(f"Class name for index {key} must be a non-empty string")
            
            return v
            
        elif isinstance(v, list):
            # Validate list format (legacy)
            if not v:
                raise ValueError("Names list cannot be empty")
            
            for i, name in enumerate(v):
                if not isinstance(name, str) or not name.strip():
                    raise ValueError(f"Class name at index {i} must be a non-empty string")
            
            return v
        else:
            raise ValueError("Names must be either a list of strings or a dict mapping int -> str")
    
    @classmethod
    def from_yaml(cls, yaml_content: str) -> 'YOLOConfig':
        """Parse YOLO config from YAML content."""
        try:
            data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML format: {e}")
        
        if not isinstance(data, dict):
            raise ValueError("YAML content must be a dictionary")
        
        # Validate required fields
        if 'names' not in data:
            raise ValueError("Missing required field: names")
        
        return cls(**data)
    
    def to_yaml(self) -> str:
        """Convert config to YAML format."""
        data = self.model_dump(exclude_none=True)
        return yaml.dump(data, default_flow_style=False, sort_keys=False)
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "path": "/path/to/dataset",
                "train": "images/train",
                "val": "images/val",
                "test": "images/test",
                "names": {
                    0: "person",
                    1: "car", 
                    2: "bicycle"
                }
            }
        }
    }


class YOLODataset(BaseModel):
    """Complete YOLO dataset with config, images, and annotations."""
    
    config: YOLOConfig = Field(..., description="Dataset configuration")
    images: List[Dict[str, Any]] = Field(default_factory=list, description="Image metadata")
    annotations: Dict[str, List[YOLOAnnotation]] = Field(
        default_factory=dict, 
        description="Annotations mapped by filename"
    )
    
    @field_validator('annotations')
    @classmethod
    def validate_annotations_format(cls, v, info):
        """Validate annotation format consistency."""
        config = info.data.get('config')
        if not config:
            return v
        
        class_names = config.class_names
        for filename, annotations in v.items():
            for annotation in annotations:
                if annotation.class_id >= len(class_names):
                    raise ValueError(
                        f"Invalid class_id {annotation.class_id} in {filename}. "
                        f"Max class_id should be {len(class_names) - 1}"
                    )
                
                expected_name = class_names[annotation.class_id]
                if annotation.class_name != expected_name:
                    raise ValueError(
                        f"Class name mismatch in {filename}: "
                        f"expected '{expected_name}', got '{annotation.class_name}'"
                    )
        
        return v
    
    def get_statistics(self) -> Dict[str, Any]:
        """Calculate dataset statistics."""
        total_images = len(self.images)
        total_annotations = sum(len(annotations) for annotations in self.annotations.values())
        
        # Class distribution
        class_names = self.config.class_names
        class_counts = {name: 0 for name in class_names}
        for annotations in self.annotations.values():
            for annotation in annotations:
                class_counts[annotation.class_name] += 1
        
        # Image dimensions statistics
        if self.images:
            widths = [img.get('width', 0) for img in self.images]
            heights = [img.get('height', 0) for img in self.images]
            
            image_stats = {
                "width": {
                    "min": min(widths) if widths else 0,
                    "max": max(widths) if widths else 0,
                    "avg": sum(widths) // len(widths) if widths else 0
                },
                "height": {
                    "min": min(heights) if heights else 0,
                    "max": max(heights) if heights else 0,
                    "avg": sum(heights) // len(heights) if heights else 0
                }
            }
        else:
            image_stats = {"width": {"min": 0, "max": 0, "avg": 0}, "height": {"min": 0, "max": 0, "avg": 0}}
        
        return {
            "total_images": total_images,
            "total_annotations": total_annotations,
            "classes_count": self.config.nc,
            "avg_annotations_per_image": total_annotations / total_images if total_images > 0 else 0,
            "class_distribution": class_counts,
            "image_dimensions": image_stats
        }
    
    def validate_dataset_integrity(self) -> List[str]:
        """Validate dataset integrity and return list of issues."""
        issues = []
        
        # Check for images without annotations
        image_filenames = {img.get('filename', '') for img in self.images}
        annotation_filenames = set(self.annotations.keys())
        
        missing_annotations = image_filenames - annotation_filenames
        if missing_annotations:
            issues.append(f"Images without annotations: {len(missing_annotations)} files")
        
        missing_images = annotation_filenames - image_filenames
        if missing_images:
            issues.append(f"Annotations without images: {len(missing_images)} files")
        
        # Check for invalid coordinates
        invalid_coords = []
        for filename, annotations in self.annotations.items():
            for i, annotation in enumerate(annotations):
                try:
                    # This will validate the coordinates
                    annotation.bbox.model_dump()
                except ValueError as e:
                    invalid_coords.append(f"{filename}[{i}]: {e}")
        
        if invalid_coords:
            issues.append(f"Invalid coordinates in {len(invalid_coords)} annotations")
        
        return issues


# Helper functions for coordinate conversion
def convert_yolo_to_absolute(bbox: YOLOBoundingBox, image_width: int, image_height: int) -> Dict[str, int]:
    """Convert YOLO normalized coordinates to absolute coordinates."""
    return bbox.to_absolute(image_width, image_height)


def convert_absolute_to_yolo(coords: Dict[str, int], image_width: int, image_height: int) -> YOLOBoundingBox:
    """Convert absolute coordinates to YOLO normalized coordinates."""
    center_x = (coords["x"] + coords["width"] / 2) / image_width
    center_y = (coords["y"] + coords["height"] / 2) / image_height
    width = coords["width"] / image_width
    height = coords["height"] / image_height
    
    return YOLOBoundingBox(
        center_x=center_x,
        center_y=center_y,
        width=width,
        height=height
    )
