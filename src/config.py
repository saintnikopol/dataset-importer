"""
Configuration management for YOLO Dataset Management API.
Handles environment-specific settings and dependency injection.
"""

import os
from enum import Enum
from typing import Optional
from pydantic import BaseSettings, validator


class Environment(str, Enum):
    """Environment types for the application."""
    LOCAL = "local"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Application settings with environment-specific configuration."""
    
    # Environment Configuration
    environment: Environment = Environment.LOCAL
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_version: str = "1.0.0"
    log_level: str = "INFO"
    
    # Database Configuration
    mongodb_url: str = "mongodb://localhost:27017/yolo_datasets"
    
    # Local Development (Celery + Redis)
    redis_url: Optional[str] = None
    
    # Production (GCP)
    gcp_project: Optional[str] = None
    storage_bucket: Optional[str] = None
    cloud_tasks_queue: Optional[str] = None
    worker_url: Optional[str] = None
    
    @validator('environment', pre=True)
    def validate_environment(cls, v):
        """Validate environment value."""
        if isinstance(v, str):
            return Environment(v.lower())
        return v
    
    @validator('redis_url')
    def validate_redis_url_for_local(cls, v, values):
        """Ensure Redis URL is provided for local environment."""
        if values.get('environment') == Environment.LOCAL and not v:
            return "redis://localhost:6379/0"
        return v
    
    @validator('gcp_project')
    def validate_gcp_project_for_production(cls, v, values):
        """Ensure GCP project is provided for production environment."""
        if values.get('environment') == Environment.PRODUCTION and not v:
            raise ValueError("GCP_PROJECT is required for production environment")
        return v
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()


def is_local_environment() -> bool:
    """Check if running in local development environment."""
    return settings.environment == Environment.LOCAL


def is_production_environment() -> bool:
    """Check if running in production environment."""
    return settings.environment == Environment.PRODUCTION
