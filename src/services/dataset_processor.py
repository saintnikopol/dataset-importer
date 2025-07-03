"""
YOLO dataset processing service.
Handles downloading, parsing, and storing YOLO format datasets.
"""

import asyncio
import zipfile
import tempfile
import yaml
import os
from pathlib import Path
from typing import Dict, Any, List, Tuple, AsyncIterator
from datetime import datetime
from PIL import Image

from src.models.yolo import YOLOConfig, YOLOAnnotation, YOLOBoundingBox
from src.services.storage import get_storage_service
from src.services.database import get_database
from src.utils.logging import logger
from src.utils.exceptions import ProcessingError, ValidationError


class DatasetProcessor:
    """Processes YOLO dataset imports with support for 100GB datasets."""
    
    def __init__(self):
        """Initialize dataset processor with required services."""
        self.storage = get_storage_service()
        self.db = get_database()
        
    async def process_dataset_import(self, job_id: str, data: Dict[str, Any]) -> None:
        """
        Main processing function for YOLO dataset import.
        Handles the complete pipeline from download to storage.
        """
        logger.info(f"Starting dataset processing for job {job_id}")
        
        try:
            # Step 1: Download and validate YOLO config
            await self._update_progress(job_id, 10, "downloading_config", "Downloading YOLO config file")
            config = await self._download_and_parse_config(data["config_url"])
            
            # Step 2: Download and extract annotations
            await self._update_progress(job_id, 30, "downloading_annotations", "Downloading annotations archive")
            annotations_data = await self._download_and_extract_archive(
                data["annotations_url"], "annotations"
            )
            
            # Step 3: Download and extract images
            await self._update_progress(job_id, 50, "downloading_images", "Downloading images archive")
            images_data = await self._download_and_extract_archive(
                data["images_url"], "images"
            )
            
            # Step 4: Parse and validate YOLO annotations
            await self._update_progress(job_id, 70, "parsing_annotations", "Parsing YOLO annotations")
            annotations = await self._parse_yolo_annotations(annotations_data, config)
            
            # Step 5: Process and validate images
            await self._update_progress(job_id, 85, "processing_images", "Processing images")
            images = await self._process_images(images_data, annotations)
            
            # Step 6: Store dataset in database and storage
            await self._update_progress(job_id, 95, "storing_data", "Storing dataset")
            dataset_id = await self._store_dataset(job_id, data, config, images, annotations)
            
            # Step 7: Complete
            await self._complete_job(job_id, dataset_id, config, images, annotations)
            
            logger.info(f"Successfully completed dataset processing for job {job_id}")
            
        except Exception as e:
            logger.error(f"Dataset processing failed for job {job_id}: {e}", exc_info=True)
            await self._fail_job(job_id, str(e))
            raise
    
    async def _download_and_parse_config(self, config_url: str) -> YOLOConfig:
        """Download and parse YOLO configuration file."""
        try:
            logger.info(f"Downloading YOLO config from: {config_url}")
            config_data = await self.storage.download_file(config_url)
            
            # Parse YAML content
            config_text = config_data.decode('utf-8')
            config = YOLOConfig.from_yaml(config_text)
            
            logger.info(f"Parsed YOLO config: {config.nc} classes - {config.names}")
            return config
            
        except Exception as e:
            raise ProcessingError(f"Failed to download/parse YOLO config: {e}")
    
    async def _download_and_extract_archive(self, url: str, content_type: str) -> Path:
        """Download and extract ZIP archive to temporary directory."""
        try:
            logger.info(f"Downloading {content_type} archive from: {url}")
            archive_data = await self.storage.download_file(url)
            
            # Create temporary directory
            temp_dir = Path(tempfile.mkdtemp(prefix=f"yolo_{content_type}_"))
            
            # Save archive to temp file
            archive_path = temp_dir / "archive.zip"
            archive_path.write_bytes(archive_data)
            
            # Extract archive
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # Remove the archive file
            archive_path.unlink()
            
            logger.info(f"Extracted {content_type} archive to: {temp_dir}")
            return temp_dir
            
        except zipfile.BadZipFile as e:
            raise ProcessingError(f"Invalid ZIP archive for {content_type}: {e}")
        except Exception as e:
            raise ProcessingError(f"Failed to download/extract {content_type} archive: {e}")
    
    async def _parse_yolo_annotations(self, annotations_dir: Path, config: YOLOConfig) -> Dict[str, List[YOLOAnnotation]]:
        """Parse YOLO annotation files from directory."""
        annotations = {}
        label_files = list(annotations_dir.rglob("*.txt"))
        
        if not label_files:
            raise ValidationError("No YOLO label files (.txt) found in annotations archive")
        
        logger.info(f"Parsing {len(label_files)} annotation files")
        
        for label_file in label_files:
            try:
                # Get base filename (without extension)
                image_name = label_file.stem
                
                # Parse annotation file
                file_annotations = []
                with open(label_file, 'r') as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if not line:
                            continue
                        
                        try:
                            annotation = YOLOAnnotation.from_yolo_line(line, config.names)
                            file_annotations.append(annotation)
                        except ValueError as e:
                            logger.warning(f"Invalid annotation in {label_file}:{line_num}: {e}")
                            continue
                
                annotations[image_name] = file_annotations
                
            except Exception as e:
                logger.warning(f"Failed to parse annotation file {label_file}: {e}")
                continue
        
        logger.info(f"Successfully parsed annotations for {len(annotations)} images")
        return annotations
    
    async def _process_images(self, images_dir: Path, annotations: Dict[str, List[YOLOAnnotation]]) -> List[Dict[str, Any]]:
        """Process image files and extract metadata."""
        images = []
        image_files = []
        
        # Find all image files
        for ext in ["*.jpg", "*.jpeg", "*.png", "*.bmp", "*.tiff"]:
            image_files.extend(list(images_dir.rglob(ext)))
            image_files.extend(list(images_dir.rglob(ext.upper())))
        
        if not image_files:
            raise ValidationError("No image files found in images archive")
        
        logger.info(f"Processing {len(image_files)} image files")
        
        for image_file in image_files:
            try:
                # Get image metadata
                with Image.open(image_file) as img:
                    width, height = img.size
                    format_name = img.format
                
                # Get file size
                file_size = image_file.stat().st_size
                
                # Get filename without extension for annotation matching
                image_name = image_file.stem
                
                # Get annotations for this image
                image_annotations = annotations.get(image_name, [])
                
                # Store image file in storage
                image_path = f"datasets/{image_name}/{image_file.name}"
                with open(image_file, 'rb') as f:
                    image_data = f.read()
                
                image_url = await self.storage.upload_file(image_data, image_path)
                
                # Create image record
                image_record = {
                    "filename": image_file.name,
                    "width": width,
                    "height": height,
                    "file_size_bytes": file_size,
                    "image_url": image_url,
                    "annotations": [
                        {
                            "class_id": ann.class_id,
                            "class_name": ann.class_name,
                            "bbox": {
                                "center_x": ann.bbox.center_x,
                                "center_y": ann.bbox.center_y,
                                "width": ann.bbox.width,
                                "height": ann.bbox.height
                            }
                        }
                        for ann in image_annotations
                    ],
                    "annotation_count": len(image_annotations),
                    "processed_at": datetime.utcnow()
                }
                
                images.append(image_record)
                
            except Exception as e:
                logger.warning(f"Failed to process image {image_file}: {e}")
                continue
        
        logger.info(f"Successfully processed {len(images)} images")
        return images
    
    async def _store_dataset(self, job_id: str, request_data: Dict[str, Any], 
                           config: YOLOConfig, images: List[Dict[str, Any]], 
                           annotations: Dict[str, List[YOLOAnnotation]]) -> str:
        """Store dataset metadata and images in database."""
        
        # Calculate dataset statistics
        total_images = len(images)
        total_annotations = sum(len(anns) for anns in annotations.values())
        total_size = sum(img["file_size_bytes"] for img in images)
        
        # Calculate class counts
        class_counts = {name: 0 for name in config.names}
        for image in images:
            for annotation in image["annotations"]:
                class_counts[annotation["class_name"]] += 1
        
        # Create dataset record
        dataset_data = {
            "name": request_data["name"],
            "description": request_data.get("description"),
            "status": "completed",
            "created_at": datetime.utcnow(),
            "completed_at": datetime.utcnow(),
            "import_job_id": job_id,
            "stats": {
                "total_images": total_images,
                "total_annotations": total_annotations,
                "classes_count": len(config.names),
                "dataset_size_bytes": total_size,
                "avg_annotations_per_image": total_annotations / total_images if total_images > 0 else 0
            },
            "classes": [
                {"id": i, "name": name, "count": class_counts[name]}
                for i, name in enumerate(config.names)
            ],
            "storage": {
                "images_path": f"datasets/{job_id}/images/",
                "labels_path": f"datasets/{job_id}/labels/",
                "config_path": f"datasets/{job_id}/dataset.yaml"
            }
        }
        
        # Create dataset in database
        dataset_id = await self.db.create_dataset(dataset_data)
        
        # Store images with dataset reference
        for image in images:
            image["dataset_id"] = dataset_id
        
        await self.db.create_images(images)
        
        logger.info(f"Stored dataset {dataset_id} with {total_images} images")
        return dataset_id
    
    async def _update_progress(self, job_id: str, percentage: int, step: str, description: str) -> None:
        """Update job progress in database."""
        try:
            await self.db.update_import_job(job_id, {
                "progress": {
                    "percentage": percentage,
                    "current_step": step,
                    "current_step_progress": description
                }
            })
        except Exception as e:
            logger.warning(f"Failed to update progress for job {job_id}: {e}")
    
    async def _complete_job(self, job_id: str, dataset_id: str, config: YOLOConfig, 
                          images: List[Dict[str, Any]], annotations: Dict[str, List[YOLOAnnotation]]) -> None:
        """Mark job as completed with summary."""
        summary = {
            "total_images": len(images),
            "total_annotations": sum(len(anns) for anns in annotations.values()),
            "classes": config.names,
            "dataset_size_bytes": sum(img["file_size_bytes"] for img in images)
        }
        
        await self.db.update_import_job(job_id, {
            "status": "completed",
            "completed_at": datetime.utcnow(),
            "dataset_id": dataset_id,
            "progress": {
                "percentage": 100,
                "current_step": "completed"
            },
            "summary": summary
        })
    
    async def _fail_job(self, job_id: str, error_message: str) -> None:
        """Mark job as failed with error details."""
        await self.db.update_import_job(job_id, {
            "status": "failed",
            "completed_at": datetime.utcnow(),
            "error": {
                "code": "processing_error",
                "message": error_message,
                "timestamp": datetime.utcnow().isoformat()
            }
        })
