"""
Dataset API endpoints.
Handles dataset listing and detailed dataset operations.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional, Dict, Any

from src.services.database import get_database, DatabaseService
from src.models.api import DatasetListResponse, DatasetImagesResponse
from src.utils.logging import logger
from src.utils.exceptions import DatabaseError


router = APIRouter()


@router.get("", response_model=DatasetListResponse)
async def list_datasets(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: DatabaseService = Depends(get_database)
) -> Dict[str, Any]:
    """
    List all datasets with pagination and filtering.
    
    Returns paginated list of datasets with metadata and statistics.
    """
    try:
        logger.info(f"Listing datasets: page={page}, limit={limit}, status={status}")
        
        # Build filters
        filters = {
            "sort_by": sort_by,
            "sort_order": sort_order
        }
        if status:
            filters["status"] = status
        
        # Get datasets from database
        result = await db.list_datasets(page=page, limit=limit, **filters)
        
        # Add filters applied info
        result["filters_applied"] = {
            "status": status,
            "sort_by": sort_by,
            "sort_order": sort_order
        }
        
        logger.info(f"Retrieved {len(result['datasets'])} datasets")
        return result
        
    except DatabaseError as e:
        logger.error(f"Database error listing datasets: {e}")
        raise HTTPException(status_code=500, detail="Database error occurred")
    except Exception as e:
        logger.error(f"Unexpected error listing datasets: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{dataset_id}")
async def get_dataset(
    dataset_id: str,
    db: DatabaseService = Depends(get_database)
) -> Dict[str, Any]:
    """
    Get detailed information about a specific dataset.
    
    Returns complete dataset metadata including statistics and class information.
    """
    try:
        logger.info(f"Getting dataset details: {dataset_id}")
        
        dataset = await db.get_dataset(dataset_id)
        
        if not dataset:
            logger.warning(f"Dataset not found: {dataset_id}")
            raise HTTPException(
                status_code=404, 
                detail=f"Dataset with ID '{dataset_id}' not found"
            )
        
        logger.info(f"Retrieved dataset: {dataset['name']}")
        return dataset
        
    except HTTPException:
        raise
    except DatabaseError as e:
        logger.error(f"Database error getting dataset {dataset_id}: {e}")
        raise HTTPException(status_code=500, detail="Database error occurred")
    except Exception as e:
        logger.error(f"Unexpected error getting dataset {dataset_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{dataset_id}/images", response_model=DatasetImagesResponse)
async def list_dataset_images(
    dataset_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=200, description="Items per page"),
    class_filter: Optional[str] = Query(None, description="Filter by class name"),
    has_annotations: Optional[bool] = Query(None, description="Filter by annotation presence"),
    sort_by: str = Query("filename", description="Sort field"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$", description="Sort order"),
    db: DatabaseService = Depends(get_database)
) -> Dict[str, Any]:
    """
    List images with annotations for a specific dataset.
    
    Returns paginated list of images with their YOLO annotations and metadata.
    Supports filtering by class and annotation presence.
    """
    try:
        logger.info(f"Listing images for dataset {dataset_id}: page={page}, limit={limit}")
        
        # Verify dataset exists
        dataset = await db.get_dataset(dataset_id)
        if not dataset:
            logger.warning(f"Dataset not found: {dataset_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Dataset with ID '{dataset_id}' not found"
            )
        
        # Build filters
        filters = {
            "sort_by": sort_by,
            "sort_order": sort_order
        }
        if class_filter:
            filters["class_filter"] = class_filter
        if has_annotations is not None:
            filters["has_annotations"] = has_annotations
        
        # Get images from database
        result = await db.list_dataset_images(
            dataset_id=dataset_id,
            page=page,
            limit=limit,
            **filters
        )
        
        logger.info(f"Retrieved {len(result['images'])} images for dataset {dataset_id}")
        return result
        
    except HTTPException:
        raise
    except DatabaseError as e:
        logger.error(f"Database error listing images for dataset {dataset_id}: {e}")
        raise HTTPException(status_code=500, detail="Database error occurred")
    except Exception as e:
        logger.error(f"Unexpected error listing images for dataset {dataset_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
