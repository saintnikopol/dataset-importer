"""
Job queue service with environment-specific implementations.
Handles background task processing for dataset imports.
"""

import json
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from src.config import settings, Environment, is_local_environment
from src.utils.logging import logger
from src.utils.exceptions import ProcessingError


class JobQueue(ABC):
    """Abstract base class for job queue implementations."""
    
    @abstractmethod
    async def enqueue_import_job(self, job_id: str, data: Dict[str, Any]) -> None:
        """Enqueue a dataset import job for background processing."""
        pass
    
    @abstractmethod
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics for monitoring."""
        pass


class LocalJobQueue(JobQueue):
    """Local development job queue using Celery + Redis."""
    
    def __init__(self):
        """Initialize local job queue with Celery."""
        try:
            import redis
            from celery import Celery
            
            self.redis_client = redis.from_url(settings.redis_url)
            
            # Import the Celery app from worker module
            from src.worker import celery_app, process_import_task
            self.celery_app = celery_app
            self.task = process_import_task
            
            logger.info("Initialized local job queue (Celery + Redis)")
            
        except ImportError as e:
            logger.error(f"Failed to import Celery dependencies: {e}")
            raise ProcessingError("Celery dependencies not available")
        except Exception as e:
            logger.error(f"Failed to initialize local job queue: {e}")
            raise ProcessingError(f"Job queue initialization failed: {e}")
    
    async def enqueue_import_job(self, job_id: str, data: Dict[str, Any]) -> None:
        """Enqueue import job using Celery."""
        try:
            logger.info(f"Enqueueing import job {job_id} to Celery")
            
            # Enqueue the task
            result = self.task.delay(job_id, data)
            
            logger.info(f"Successfully enqueued job {job_id} with task ID: {result.id}")
            
        except Exception as e:
            logger.error(f"Failed to enqueue job {job_id}: {e}")
            raise ProcessingError(f"Failed to enqueue import job: {e}")
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get Redis/Celery queue statistics."""
        try:
            # Get Redis info
            redis_info = self.redis_client.info()
            
            # Get queue length (approximate)
            queue_length = self.redis_client.llen("celery")
            
            return {
                "queue_type": "celery_redis",
                "queue_length": queue_length,
                "redis_connected_clients": redis_info.get("connected_clients", 0),
                "redis_used_memory": redis_info.get("used_memory_human", "0B"),
                "status": "operational"
            }
            
        except Exception as e:
            logger.error(f"Failed to get queue stats: {e}")
            return {
                "queue_type": "celery_redis",
                "status": "error",
                "error": str(e)
            }


class ProductionJobQueue(JobQueue):
    """Production job queue using Google Cloud Tasks."""
    
    def __init__(self):
        """Initialize production job queue with Cloud Tasks."""
        try:
            from google.cloud import tasks_v2
            
            self.client = tasks_v2.CloudTasksClient()
            self.project = settings.gcp_project
            self.location = "us-central1"  # Default location
            self.queue = "yolo-import-queue"
            
            # Build queue path
            self.queue_path = self.client.queue_path(
                self.project, self.location, self.queue
            )
            
            logger.info("Initialized production job queue (Cloud Tasks)")
            
        except ImportError as e:
            logger.error(f"Failed to import Cloud Tasks dependencies: {e}")
            raise ProcessingError("Cloud Tasks dependencies not available")
        except Exception as e:
            logger.error(f"Failed to initialize production job queue: {e}")
            raise ProcessingError(f"Job queue initialization failed: {e}")
    
    async def enqueue_import_job(self, job_id: str, data: Dict[str, Any]) -> None:
        """Enqueue import job using Cloud Tasks."""
        try:
            logger.info(f"Enqueueing import job {job_id} to Cloud Tasks")
            
            # Prepare task payload
            payload = {
                "job_id": job_id,
                "name": data.get("name"),
                "description": data.get("description"),
                "config_url": data.get("yolo_config_url"),
                "annotations_url": data.get("annotations_url"),
                "images_url": data.get("images_url")
            }
            
            # Create Cloud Tasks task
            task = {
                "http_request": {
                    "http_method": tasks_v2.HttpMethod.POST,
                    "url": f"{settings.worker_url}/process",
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps(payload).encode()
                },
                "schedule_time": None  # Execute immediately
            }
            
            # Add retry configuration
            task["retry_config"] = {
                "max_attempts": 3,
                "max_retry_duration": {"seconds": 3600},  # 1 hour max
                "min_backoff": {"seconds": 60},           # 1 minute min
                "max_backoff": {"seconds": 300}           # 5 minutes max
            }
            
            # Enqueue the task
            response = self.client.create_task(
                parent=self.queue_path, 
                task=task
            )
            
            logger.info(f"Successfully enqueued job {job_id} to Cloud Tasks: {response.name}")
            
        except Exception as e:
            logger.error(f"Failed to enqueue job {job_id}: {e}")
            raise ProcessingError(f"Failed to enqueue import job: {e}")
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get Cloud Tasks queue statistics."""
        try:
            # Get queue information
            queue_info = self.client.get_queue(name=self.queue_path)
            
            # Get queue stats (approximate)
            stats = self.client.get_queue_stats(name=self.queue_path)
            
            return {
                "queue_type": "cloud_tasks",
                "queue_name": queue_info.name,
                "state": queue_info.state.name,
                "tasks_dispatched_per_second": getattr(stats, "tasks_dispatched_per_second", 0),
                "outstanding_tasks": getattr(stats, "outstanding_tasks", 0),
                "status": "operational"
            }
            
        except Exception as e:
            logger.error(f"Failed to get queue stats: {e}")
            return {
                "queue_type": "cloud_tasks",
                "status": "error", 
                "error": str(e)
            }


# Global job queue instance
_job_queue: Optional[JobQueue] = None


def get_job_queue() -> JobQueue:
    """Get job queue instance based on environment."""
    global _job_queue
    
    if _job_queue is None:
        if is_local_environment():
            _job_queue = LocalJobQueue()
        else:
            _job_queue = ProductionJobQueue()
    
    return _job_queue


async def health_check_queue() -> Dict[str, Any]:
    """Check job queue health for monitoring."""
    try:
        queue = get_job_queue()
        stats = await queue.get_queue_stats()
        
        return {
            "status": "healthy" if stats.get("status") == "operational" else "unhealthy",
            "details": stats
        }
        
    except Exception as e:
        logger.error(f"Job queue health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }
