"""
Background worker for processing YOLO dataset imports.
Supports both local development (Celery) and production (Cloud Run Jobs).
"""

import asyncio
import uuid
from typing import Dict, Any
from datetime import datetime

from src.config import settings, Environment
from src.models.api import ImportJobData
from src.services.dataset_processor import DatasetProcessor
from src.services.database import init_database, get_database
from src.utils.logging import setup_logging, logger
from src.utils.exceptions import ProcessingError


# Initialize logging
setup_logging()


if settings.environment == Environment.LOCAL:
    # Local development: Celery + Redis
    from celery import Celery
    
    celery_app = Celery(
        "yolo_worker",
        broker=settings.redis_url,
        backend=settings.redis_url,
        include=["src.worker"]
    )
    
    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_routes={
            "src.worker.process_import_task": {"queue": "yolo_import"}
        }
    )
    
    @celery_app.task(bind=True, name="src.worker.process_import_task")
    def process_import_task(self, job_id: str, data: Dict[str, Any]):
        """Celery task for processing dataset import."""
        try:
            logger.info(f"Starting import task {job_id}")
            asyncio.run(process_dataset_import(job_id, data))
            logger.info(f"Completed import task {job_id}")
        except Exception as e:
            logger.error(f"Import task {job_id} failed: {e}", exc_info=True)
            # Update job status to failed
            asyncio.run(mark_job_failed(job_id, str(e)))
            raise

else:
    # Production: FastAPI app for Cloud Run Jobs
    from fastapi import FastAPI, HTTPException
    
    worker_app = FastAPI(
        title="YOLO Dataset Import Worker",
        description="Background processor for YOLO dataset imports",
        version=settings.api_version
    )
    
    @worker_app.on_event("startup")
    async def startup_event():
        """Initialize database connection."""
        await init_database()
        logger.info("Worker database initialized")
    
    @worker_app.post("/process")
    async def process_import(data: ImportJobData):
        """Cloud Run Jobs endpoint for processing dataset import."""
        try:
            logger.info(f"Starting import job {data.job_id}")
            await process_dataset_import(data.job_id, data.dict())
            logger.info(f"Completed import job {data.job_id}")
            return {"status": "completed", "job_id": data.job_id}
        except Exception as e:
            logger.error(f"Import job {data.job_id} failed: {e}", exc_info=True)
            await mark_job_failed(data.job_id, str(e))
            raise HTTPException(status_code=500, detail=str(e))


async def process_dataset_import(job_id: str, data: Dict[str, Any]) -> None:
    """
    Main function for processing YOLO dataset import.
    Works for both local and production environments.
    """
    processor = DatasetProcessor()
    db = get_database()
    
    try:
        # Update job status to processing
        await db.update_import_job(job_id, {
            "status": "processing",
            "started_at": datetime.utcnow(),
            "progress": {
                "percentage": 0,
                "current_step": "downloading_files",
                "steps_completed": [],
                "total_steps": 5
            }
        })
        
        # Process the dataset import
        await processor.process_dataset_import(job_id, data)
        
        # Mark job as completed
        await db.update_import_job(job_id, {
            "status": "completed",
            "completed_at": datetime.utcnow(),
            "progress": {
                "percentage": 100,
                "current_step": "completed",
                "steps_completed": [
                    "downloading_files",
                    "validating_format", 
                    "parsing_annotations",
                    "processing_images",
                    "storing_data"
                ],
                "total_steps": 5
            }
        })
        
        logger.info(f"Successfully completed dataset import {job_id}")
        
    except Exception as e:
        logger.error(f"Dataset import {job_id} failed: {e}", exc_info=True)
        await mark_job_failed(job_id, str(e))
        raise


async def mark_job_failed(job_id: str, error_message: str) -> None:
    """Mark import job as failed with error details."""
    try:
        db = get_database()
        await db.update_import_job(job_id, {
            "status": "failed",
            "completed_at": datetime.utcnow(),
            "error": {
                "code": "processing_error",
                "message": error_message,
                "timestamp": datetime.utcnow().isoformat()
            }
        })
    except Exception as e:
        logger.error(f"Failed to update job status for {job_id}: {e}")


# For direct execution (production worker)
if __name__ == "__main__":
    if settings.environment == Environment.PRODUCTION:
        import uvicorn
        uvicorn.run(
            "src.worker:worker_app",
            host="0.0.0.0",
            port=8080,
            log_level=settings.log_level.lower()
        )
    else:
        print("Use 'celery -A src.worker worker' for local development")
