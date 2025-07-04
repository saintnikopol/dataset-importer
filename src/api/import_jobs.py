"""
Import job API endpoints.
Handles dataset import initiation and job status tracking.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
import uuid
from datetime import datetime, timedelta

from src.models.api import ImportRequest, ImportResponse, JobStatusResponse
from src.services.job_queue import get_job_queue
from src.services.database import get_database, DatabaseService
from src.utils.logging import logger
from src.utils.exceptions import DatabaseError, ProcessingError


router = APIRouter()


@router.post("/import", response_model=ImportResponse, status_code=202)
async def import_dataset(
    request: ImportRequest,
    db: DatabaseService = Depends(get_database)
) -> Dict[str, Any]:
    """
    Start asynchronous YOLO dataset import.
    
    Initiates background processing of YOLO dataset from provided URLs.
    Returns job ID for tracking progress.
    """
    try:
        # Generate unique job ID
        job_id = str(uuid.uuid4())
        
        logger.info(f"Starting dataset import: {request.name} (job: {job_id})")
        
        # Create job record in database
        job_data = {
            "job_id": job_id,
            "status": "queued",
            "progress": {
                "percentage": 0,
                "current_step": "queued",
                "steps_completed": [],
                "total_steps": 6
            },
            "request": request.model_dump(mode="json"),
            "created_at": datetime.utcnow(),
            "estimated_completion": datetime.utcnow() + timedelta(minutes=20)
        }
        
        await db.create_import_job(job_data)
        
        # Enqueue background processing job
        job_queue = get_job_queue()
        await job_queue.enqueue_import_job(job_id, request.model_dump(mode="json"))
        
        # Return response
        response = {
            "job_id": job_id,
            "status": "queued",
            "message": "Import job started successfully",
            "created_at": job_data["created_at"],
            "estimated_completion": job_data["estimated_completion"]
        }
        
        logger.info(f"Successfully queued import job: {job_id}")
        return response
        
    except ProcessingError as e:
        logger.error(f"Processing error starting import: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start import: {e}")
    except DatabaseError as e:
        logger.error(f"Database error starting import: {e}")
        raise HTTPException(status_code=500, detail="Database error occurred")
    except Exception as e:
        logger.error(f"Unexpected error starting import: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/import/{job_id}/status", response_model=JobStatusResponse)
async def get_import_status(
    job_id: str,
    db: DatabaseService = Depends(get_database)
) -> Dict[str, Any]:
    """
    Get the status and progress of a dataset import job.
    
    Returns detailed progress information including current step,
    completion percentage, and any errors.
    """
    try:
        logger.debug(f"Getting status for import job: {job_id}")
        
        # Get job from database
        job = await db.get_import_job(job_id)
        
        if not job:
            logger.warning(f"Import job not found: {job_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Import job with ID '{job_id}' not found"
            )
        
        # Build response based on job status
        response = {
            "job_id": job_id,
            "status": job["status"],
            "progress": job.get("progress", {}),
            "started_at": job.get("started_at"),
            "completed_at": job.get("completed_at"),
            "estimated_completion": job.get("estimated_completion")
        }
        
        # Add dataset_id if completed
        if job["status"] == "completed" and job.get("dataset_id"):
            response["dataset_id"] = job["dataset_id"]
        
        # Add summary if completed
        if job.get("summary"):
            response["summary"] = job["summary"]
        
        # Add error details if failed
        if job["status"] == "failed" and job.get("error"):
            response["error"] = job["error"]
        
        logger.debug(f"Retrieved status for job {job_id}: {job['status']}")
        return response
        
    except HTTPException:
        raise
    except DatabaseError as e:
        logger.error(f"Database error getting job status {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Database error occurred")
    except Exception as e:
        logger.error(f"Unexpected error getting job status {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
