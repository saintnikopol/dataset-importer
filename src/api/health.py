"""
Health check API endpoints.
Provides service health monitoring and dependency status.
"""

from fastapi import APIRouter
from datetime import datetime
from typing import Dict, Any

from src.models.api import HealthResponse
from src.config import settings
from src.services.database import health_check_database
from src.services.job_queue import health_check_queue
from src.services.storage import health_check_storage
from src.utils.logging import logger


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> Dict[str, Any]:
    """
    Comprehensive health check for the service and its dependencies.
    
    Checks connectivity and status of:
    - MongoDB database
    - Job queue (Redis/Cloud Tasks)
    - Storage service (Local/Cloud Storage)
    
    Returns overall health status and individual dependency statuses.
    """
    try:
        logger.debug("Performing health check")
        
        # Check all dependencies
        db_health = await health_check_database()
        queue_health = await health_check_queue()
        storage_health = await health_check_storage()
        
        # Determine overall health
        dependencies = {
            "mongodb": db_health.get("status", "unknown"),
            "job_queue": queue_health.get("status", "unknown"),
            "storage": storage_health.get("status", "unknown")
        }
        
        # Collect any errors
        errors = []
        overall_healthy = True
        
        for service, status in dependencies.items():
            if status != "healthy":
                overall_healthy = False
                if service == "mongodb" and db_health.get("error"):
                    errors.append(f"MongoDB: {db_health['error']}")
                elif service == "job_queue" and queue_health.get("error"):
                    errors.append(f"Job Queue: {queue_health['error']}")
                elif service == "storage" and storage_health.get("error"):
                    errors.append(f"Storage: {storage_health['error']}")
        
        # Build response
        response = {
            "status": "healthy" if overall_healthy else "unhealthy",
            "timestamp": datetime.utcnow(),
            "version": settings.api_version,
            "dependencies": dependencies
        }
        
        if errors:
            response["errors"] = errors
        
        # Log health check result
        if overall_healthy:
            logger.debug("Health check passed")
        else:
            logger.warning(f"Health check failed: {errors}")
        
        return response
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow(),
            "version": settings.api_version,
            "dependencies": {
                "mongodb": "unknown",
                "job_queue": "unknown", 
                "storage": "unknown"
            },
            "errors": [f"Health check failed: {str(e)}"]
        }
