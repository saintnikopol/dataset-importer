"""
Database service for MongoDB operations.
Handles all database interactions with proper indexing and error handling.
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from typing import Optional, Dict, Any, List
from datetime import datetime
from bson import ObjectId
import math

from src.config import settings
from src.models.database import Dataset, ImportJob, Image, DATASETS_COLLECTION, IMPORT_JOBS_COLLECTION, IMAGES_COLLECTION
from src.utils.logging import logger
from src.utils.exceptions import DatabaseError


class DatabaseService:
    """MongoDB database service with async operations."""
    
    def __init__(self, client: AsyncIOMotorClient):
        """Initialize database service with MongoDB client."""
        self.client = client
        self.db: AsyncIOMotorDatabase = client.get_database()
        
        # Collections
        self.datasets: AsyncIOMotorCollection = self.db[DATASETS_COLLECTION]
        self.import_jobs: AsyncIOMotorCollection = self.db[IMPORT_JOBS_COLLECTION]
        self.images: AsyncIOMotorCollection = self.db[IMAGES_COLLECTION]
        
        logger.info("Database service initialized")
    
    async def ensure_indexes(self) -> None:
        """Create database indexes for optimal performance."""
        try:
            # Datasets collection indexes
            await self.datasets.create_index([("status", 1), ("created_at", -1)])
            await self.datasets.create_index([("created_at", -1)])
            await self.datasets.create_index([("import_job_id", 1)])
            
            # Import jobs collection indexes
            await self.datasets.create_index([("job_id", 1)], unique=True)
            await self.import_jobs.create_index([("status", 1), ("created_at", -1)])
            await self.import_jobs.create_index([("dataset_id", 1)])
            
            # Images collection indexes (critical for 100GB datasets)
            await self.images.create_index([("dataset_id", 1), ("filename", 1)])
            await self.images.create_index([("dataset_id", 1), ("annotation_count", 1)])
            await self.images.create_index([("dataset_id", 1), ("processed_at", -1)])
            
            logger.info("Database indexes created successfully")
            
        except Exception as e:
            logger.warning(f"Failed to create some indexes: {e}")
    
    # Dataset operations
    async def create_dataset(self, dataset_data: Dict[str, Any]) -> str:
        """Create a new dataset and return its ID."""
        try:
            result = await self.datasets.insert_one(dataset_data)
            dataset_id = str(result.inserted_id)
            logger.info(f"Created dataset: {dataset_id}")
            return dataset_id
            
        except Exception as e:
            logger.error(f"Failed to create dataset: {e}")
            raise DatabaseError(f"Dataset creation failed: {e}")
    
    async def get_dataset(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """Get dataset by ID."""
        try:
            if not ObjectId.is_valid(dataset_id):
                return None
                
            dataset = await self.datasets.find_one({"_id": ObjectId(dataset_id)})
            if dataset:
                dataset["id"] = str(dataset["_id"])
                del dataset["_id"]
            
            return dataset
            
        except Exception as e:
            logger.error(f"Failed to get dataset {dataset_id}: {e}")
            raise DatabaseError(f"Dataset retrieval failed: {e}")
    
    async def list_datasets(self, page: int = 1, limit: int = 20, **filters) -> Dict[str, Any]:
        """List datasets with pagination and filtering."""
        try:
            # Build query from filters
            query = {}
            if filters.get("status"):
                query["status"] = filters["status"]
            
            # Calculate pagination
            skip = (page - 1) * limit
            
            # Build sort criteria
            sort_by = filters.get("sort_by", "created_at")
            sort_order = -1 if filters.get("sort_order", "desc") == "desc" else 1
            sort_criteria = [(sort_by, sort_order)]
            
            # Execute queries
            cursor = self.datasets.find(query).sort(sort_criteria).skip(skip).limit(limit)
            datasets = await cursor.to_list(length=limit)
            
            # Count total items
            total_items = await self.datasets.count_documents(query)
            total_pages = math.ceil(total_items / limit)
            
            # Format datasets
            formatted_datasets = []
            for dataset in datasets:
                dataset["id"] = str(dataset["_id"])
                del dataset["_id"]
                formatted_datasets.append(dataset)
            
            return {
                "datasets": formatted_datasets,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total_pages": total_pages,
                    "total_items": total_items,
                    "has_next": page < total_pages,
                    "has_prev": page > 1
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to list datasets: {e}")
            raise DatabaseError(f"Dataset listing failed: {e}")
    
    # Import job operations
    async def create_import_job(self, job_data: Dict[str, Any]) -> str:
        """Create a new import job and return its ID."""
        try:
            result = await self.import_jobs.insert_one(job_data)
            job_id = str(result.inserted_id)
            logger.info(f"Created import job: {job_data['job_id']}")
            return job_id
            
        except Exception as e:
            logger.error(f"Failed to create import job: {e}")
            raise DatabaseError(f"Import job creation failed: {e}")
    
    async def update_import_job(self, job_id: str, updates: Dict[str, Any]) -> None:
        """Update import job with new data."""
        try:
            result = await self.import_jobs.update_one(
                {"job_id": job_id},
                {"$set": updates}
            )
            
            if result.matched_count == 0:
                raise DatabaseError(f"Import job {job_id} not found")
                
            logger.debug(f"Updated import job: {job_id}")
            
        except Exception as e:
            logger.error(f"Failed to update import job {job_id}: {e}")
            raise DatabaseError(f"Import job update failed: {e}")
    
    async def get_import_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get import job by job ID."""
        try:
            job = await self.import_jobs.find_one({"job_id": job_id})
            if job:
                job["id"] = str(job["_id"])
                del job["_id"]
                
                # Convert dataset_id to string if present
                if job.get("dataset_id"):
                    job["dataset_id"] = str(job["dataset_id"])
            
            return job
            
        except Exception as e:
            logger.error(f"Failed to get import job {job_id}: {e}")
            raise DatabaseError(f"Import job retrieval failed: {e}")
    
    # Image operations
    async def create_images(self, images_data: List[Dict[str, Any]]) -> List[str]:
        """Create multiple images and return their IDs."""
        try:
            if not images_data:
                return []
            
            # Convert dataset_id strings to ObjectId
            for image in images_data:
                if isinstance(image.get("dataset_id"), str):
                    image["dataset_id"] = ObjectId(image["dataset_id"])
            
            result = await self.images.insert_many(images_data)
            image_ids = [str(oid) for oid in result.inserted_ids]
            
            logger.info(f"Created {len(image_ids)} images")
            return image_ids
            
        except Exception as e:
            logger.error(f"Failed to create images: {e}")
            raise DatabaseError(f"Image creation failed: {e}")
    
    async def list_dataset_images(self, dataset_id: str, page: int = 1, limit: int = 50, **filters) -> Dict[str, Any]:
        """List images for a dataset with pagination and filtering."""
        try:
            if not ObjectId.is_valid(dataset_id):
                raise DatabaseError(f"Invalid dataset ID: {dataset_id}")
            
            # Build query
            query = {"dataset_id": ObjectId(dataset_id)}
            
            # Apply filters
            if filters.get("class_filter"):
                query["annotations.class_name"] = filters["class_filter"]
            
            if filters.get("has_annotations") is not None:
                if filters["has_annotations"]:
                    query["annotation_count"] = {"$gt": 0}
                else:
                    query["annotation_count"] = 0
            
            # Calculate pagination
            skip = (page - 1) * limit
            
            # Build sort criteria
            sort_by = filters.get("sort_by", "filename")
            sort_order = 1 if filters.get("sort_order", "asc") == "asc" else -1
            sort_criteria = [(sort_by, sort_order)]
            
            # Execute queries
            cursor = self.images.find(query).sort(sort_criteria).skip(skip).limit(limit)
            images = await cursor.to_list(length=limit)
            
            # Count total items
            total_items = await self.images.count_documents(query)
            total_pages = math.ceil(total_items / limit)
            
            # Format images
            formatted_images = []
            for image in images:
                image["id"] = str(image["_id"])
                image["dataset_id"] = str(image["dataset_id"])
                del image["_id"]
                formatted_images.append(image)
            
            return {
                "dataset_id": dataset_id,
                "images": formatted_images,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total_pages": total_pages,
                    "total_items": total_items,
                    "has_next": page < total_pages,
                    "has_prev": page > 1
                },
                "filters_applied": {
                    "class_filter": filters.get("class_filter"),
                    "has_annotations": filters.get("has_annotations")
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to list images for dataset {dataset_id}: {e}")
            raise DatabaseError(f"Image listing failed: {e}")


# Global database service instance
_database_service: Optional[DatabaseService] = None
_client: Optional[AsyncIOMotorClient] = None


async def init_database() -> None:
    """Initialize database connection and service."""
    global _database_service, _client
    
    try:
        logger.info(f"Connecting to MongoDB: {settings.mongodb_url}")
        
        # Create MongoDB client
        _client = AsyncIOMotorClient(settings.mongodb_url)
        
        # Test connection
        await _client.admin.command('ping')
        
        # Create database service
        _database_service = DatabaseService(_client)
        
        # Ensure indexes
        await _database_service.ensure_indexes()
        
        logger.info("Database initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise DatabaseError(f"Database initialization failed: {e}")


async def close_database() -> None:
    """Close database connection."""
    global _client
    
    if _client:
        _client.close()
        logger.info("Database connection closed")


def get_database() -> DatabaseService:
    """Get database service instance."""
    if _database_service is None:
        raise DatabaseError("Database not initialized. Call init_database() first.")
    return _database_service


async def health_check_database() -> Dict[str, Any]:
    """Check database health for monitoring."""
    try:
        if _client is None:
            return {"status": "unhealthy", "error": "Database not initialized"}
        
        # Test connection with ping
        await _client.admin.command('ping')
        
        # Get server info
        server_info = await _client.admin.command('serverStatus')
        
        return {
            "status": "healthy",
            "mongodb_version": server_info.get("version", "unknown"),
            "connections": server_info.get("connections", {}).get("current", 0)
        }
        
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }
