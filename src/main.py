"""
FastAPI main application for YOLO Dataset Management API.
Handles HTTP requests and coordinates with background processing.
"""

import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import settings, is_local_environment
from src.api.datasets import router as datasets_router
from src.api.import_jobs import router as import_jobs_router
from src.api.health import router as health_router
from src.services.database import init_database, close_database
from src.utils.logging import setup_logging, logger
from src.utils.exceptions import YOLODatasetError


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown."""
    # Startup
    setup_logging()
    logger.info("Starting YOLO Dataset Management API")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"MongoDB URL: {settings.mongodb_url}")
    
    try:
        await init_database()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down YOLO Dataset Management API")
    await close_database()


# Create FastAPI application
app = FastAPI(
    title="YOLO Dataset Management API",
    description="Backend API for importing and managing YOLO format datasets up to 100GB",
    version=settings.api_version,
    docs_url="/docs" if is_local_environment() else None,
    redoc_url="/redoc" if is_local_environment() else None,
    lifespan=lifespan
)

# Add CORS middleware for local development
if is_local_environment():
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# Global exception handler
@app.exception_handler(YOLODatasetError)
async def yolo_dataset_exception_handler(request, exc: YOLODatasetError):
    """Handle custom YOLO dataset exceptions."""
    logger.error(f"YOLO Dataset Error: {exc}")
    return JSONResponse(
        status_code=400,
        content={
            "error": exc.__class__.__name__.lower(),
            "message": str(exc),
            "timestamp": "2025-07-03T10:00:00Z"
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred",
            "timestamp": "2025-07-03T10:00:00Z"
        }
    )


# Root endpoint
@app.get("/")
async def root():
    """API information endpoint."""
    return {
        "service": "YOLO Dataset Management API",
        "version": settings.api_version,
        "description": "Backend API for importing and managing YOLO format datasets",
        "documentation": {
            "interactive": "/docs",
            "redoc": "/redoc",
            "openapi": "/openapi.json"
        },
        "health": "/health",
        "contact": {
            "support": "support@example.com",
            "repository": "https://github.com/your-org/yolo-dataset-management"
        }
    }


# Include API routers
app.include_router(health_router, tags=["Health"])
app.include_router(import_jobs_router, prefix="/datasets", tags=["Import Jobs"])
app.include_router(datasets_router, prefix="/datasets", tags=["Datasets"])


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.log_level.lower(),
        reload=is_local_environment()
    )
