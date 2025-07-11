"""
YOLO dataset processing service - FIXED VERSION
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
        Main processing function for YOLO dataset import with single archive.
        Processes complete YOLO dataset from single ZIP archive.
        """
        logger.info(f"Starting dataset processing for job {job_id}")
        
        try:
            # Step 1: Download and validate YOLO config
            await self._update_progress(job_id, 10, "downloading_config", "Downloading YOLO config file")
            config = await self._download_and_parse_config(data["config_url"])
            
            # Step 2: Download and extract complete dataset
            await self._update_progress(job_id, 30, "downloading_dataset", "Downloading YOLO dataset archive")
            dataset_dir = await self._download_and_extract_dataset(data["dataset_url"], job_id)
            
            # Step 3: Find and parse YOLO annotations
            await self._update_progress(job_id, 60, "parsing_annotations", "Parsing YOLO annotations")
            annotations = await self._find_and_parse_annotations(dataset_dir, config)
            
            # Step 4: Process and validate images
            await self._update_progress(job_id, 80, "processing_images", "Processing images")
            images = await self._find_and_process_images(dataset_dir, annotations)
            
            # Step 5: Store dataset in database and storage
            await self._update_progress(job_id, 90, "storing_data", "Storing dataset")
            dataset_id = await self._store_dataset(job_id, data, config, images, annotations)
            
            # Step 6: Complete
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
            
            logger.info(f"Parsed YOLO config: {config.nc} classes - {config.class_names}")
            return config
            
        except Exception as e:
            raise ProcessingError(f"Failed to download/parse YOLO config: {e}")
    
    async def _download_and_extract_dataset(self, dataset_url: str, job_id: str) -> Path:
        """Download and extract complete YOLO dataset archive."""
        try:
            logger.info(f"Downloading YOLO dataset archive from: {dataset_url}")
            archive_data = await self.storage.download_file(dataset_url)
            
            # Create job-specific temporary directory
            temp_dir = Path(tempfile.mkdtemp(prefix=f"yolo_dataset_{job_id}_"))
            
            # Save archive to temp file
            archive_path = temp_dir / "archive.zip"
            archive_path.write_bytes(archive_data)
            
            # Extract archive
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # Remove the archive file
            archive_path.unlink()
            
            logger.info(f"Extracted YOLO dataset archive to: {temp_dir}")
            return temp_dir
            
        except zipfile.BadZipFile as e:
            raise ProcessingError(f"Invalid ZIP archive for dataset: {e}")
        except Exception as e:
            raise ProcessingError(f"Failed to download/extract dataset archive: {e}")
    
    def _find_dataset_root(self, extracted_dir: Path) -> Path:
        """
        Find the actual dataset root directory within the extracted archive.
        Handles various archive structures automatically.
        """
        # List all directories in the extracted path
        subdirs = [d for d in extracted_dir.iterdir() if d.is_dir()]
        
        # Check if labels/ and images/ are directly in extracted_dir
        if (extracted_dir / "labels").exists() and (extracted_dir / "images").exists():
            logger.info(f"Dataset root found at: {extracted_dir}")
            return extracted_dir
        
        # Look for labels/ and images/ in subdirectories (common case)
        for subdir in subdirs:
            if (subdir / "labels").exists() and (subdir / "images").exists():
                logger.info(f"Dataset root found at: {subdir}")
                return subdir
        
        # Look for any directory that has labels/ subdirectory
        for subdir in subdirs:
            labels_dirs = list(subdir.rglob("labels"))
            if labels_dirs:
                potential_root = labels_dirs[0].parent
                if (potential_root / "images").exists() or list(potential_root.rglob("images")):
                    logger.info(f"Dataset root found at: {potential_root}")
                    return potential_root
        
        # Fallback: look deeper for any labels directory
        all_labels_dirs = list(extracted_dir.rglob("labels"))
        if all_labels_dirs:
            # Take the first labels directory and assume its parent is the dataset root
            potential_root = all_labels_dirs[0].parent
            logger.info(f"Dataset root found at: {potential_root} (fallback)")
            return potential_root
        
        # If we still can't find it, return the extracted directory and let the error handling deal with it
        logger.warning(f"Could not find dataset root structure in {extracted_dir}")
        return extracted_dir
    
    async def _find_and_parse_annotations(self, extracted_dir: Path, config: YOLOConfig) -> Dict[str, List[YOLOAnnotation]]:
        """Find and parse YOLO annotation files from the dataset."""
        # Find the actual dataset root
        dataset_root = self._find_dataset_root(extracted_dir)
        
        # Try multiple possible labels directory locations
        possible_labels_dirs = [
            dataset_root / "labels",
            dataset_root / "train" / "labels",
            dataset_root / "val" / "labels",
        ]
        
        # Also search recursively for labels directories
        possible_labels_dirs.extend(list(dataset_root.rglob("labels")))
        
        annotations = {}
        
        for labels_dir in possible_labels_dirs:
            if labels_dir.exists() and labels_dir.is_dir():
                logger.info(f"Processing labels from: {labels_dir}")
                dir_annotations = await self._parse_yolo_annotations(labels_dir, config)
                annotations.update(dir_annotations)
        
        if not annotations:
            # List directory structure for debugging
            logger.error(f"Directory structure of {dataset_root}:")
            for root, dirs, files in os.walk(dataset_root):
                level = root.replace(str(dataset_root), '').count(os.sep)
                indent = ' ' * 2 * level
                logger.error(f"{indent}{os.path.basename(root)}/")
                subindent = ' ' * 2 * (level + 1)
                for file in files[:10]:  # Show only first 10 files
                    logger.error(f"{subindent}{file}")
                if len(files) > 10:
                    logger.error(f"{subindent}... and {len(files) - 10} more files")
            
            raise ValidationError(f"No YOLO annotation files found in dataset. Searched directories: {[str(d) for d in possible_labels_dirs]}")
        
        logger.info(f"Successfully parsed annotations for {len(annotations)} images")
        return annotations
    
    async def _parse_yolo_annotations(self, labels_dir: Path, config: YOLOConfig) -> Dict[str, List[YOLOAnnotation]]:
        """Parse YOLO annotation files from a specific labels directory."""
        annotations = {}
        
        # Find all .txt files in labels directory and subdirectories
        label_files = list(labels_dir.rglob("*.txt"))
        
        if not label_files:
            logger.warning(f"No .txt annotation files found in {labels_dir}")
            return annotations
        
        logger.info(f"Parsing {len(label_files)} annotation files from {labels_dir}")
        
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
                            annotation = YOLOAnnotation.from_yolo_line(line, config.class_names)
                            file_annotations.append(annotation)
                        except ValueError as e:
                            logger.warning(f"Invalid annotation in {label_file}:{line_num}: {e}")
                            continue
                
                annotations[image_name] = file_annotations
                
            except Exception as e:
                logger.warning(f"Failed to parse annotation file {label_file}: {e}")
                continue
        
        return annotations
    
    async def _find_and_process_images(self, extracted_dir: Path, annotations: Dict[str, List[YOLOAnnotation]]) -> List[Dict[str, Any]]:
        """Find and process image files from the dataset."""
        # Find the actual dataset root
        dataset_root = self._find_dataset_root(extracted_dir)
        
        # Try multiple possible images directory locations
        possible_images_dirs = [
            dataset_root / "images",
            dataset_root / "train" / "images",
            dataset_root / "val" / "images",
        ]
        
        # Also search recursively for images directories
        possible_images_dirs.extend(list(dataset_root.rglob("images")))
        
        images = []
        image_extensions = ["*.jpg", "*.jpeg", "*.png", "*.bmp", "*.tiff"]
        
        for images_dir in possible_images_dirs:
            if images_dir.exists() and images_dir.is_dir():
                logger.info(f"Processing images from: {images_dir}")
                
                # Find all image files
                image_files = []
                for ext in image_extensions:
                    image_files.extend(list(images_dir.rglob(ext)))
                    image_files.extend(list(images_dir.rglob(ext.upper())))
                
                if image_files:
                    dir_images = await self._process_images_from_directory(images_dir, image_files, annotations)
                    images.extend(dir_images)
        
        if not images:
            raise ValidationError(f"No image files found in dataset. Searched directories: {[str(d) for d in possible_images_dirs]}")
        
        logger.info(f"Successfully processed {len(images)} images")
        return images
    
    async def _process_images_from_directory(self, images_dir: Path, image_files: List[Path], 
                                           annotations: Dict[str, List[YOLOAnnotation]]) -> List[Dict[str, Any]]:
        """Process image files from a specific directory."""
        images = []
        
        logger.info(f"Processing {len(image_files)} image files from {images_dir}")
        
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
                relative_path = image_file.relative_to(images_dir)
                image_path = f"datasets/{image_name}/{relative_path}"
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
                logger.warning(f"Failed to process image {image_file.name}: {e}")
                continue
        
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
        class_counts = {name: 0 for name in config.class_names}
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
                "classes_count": len(config.class_names),
                "dataset_size_bytes": total_size,
                "avg_annotations_per_image": total_annotations / total_images if total_images > 0 else 0
            },
            "classes": [
                {"id": i, "name": name, "count": class_counts.get(name, 0)}
                for i, name in enumerate(config.class_names)
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
            "classes": config.class_names,
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
