"""
Structured logging configuration for YOLO Dataset Management API.
Provides consistent, production-ready logging across the application.
"""

import logging
import sys
import json
from datetime import datetime
from typing import Dict, Any, Optional

from src.config import settings, is_local_environment


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured JSON logging in production."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        
        # Base log entry
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields from record
        for key, value in record.__dict__.items():
            if key not in ["name", "msg", "args", "levelname", "levelno", "pathname", 
                          "filename", "module", "lineno", "funcName", "created", "msecs",
                          "relativeCreated", "thread", "threadName", "processName", 
                          "process", "exc_info", "exc_text", "stack_info", "getMessage"]:
                log_entry[key] = value
        
        return json.dumps(log_entry, ensure_ascii=False)


class LocalFormatter(logging.Formatter):
    """Colorized formatter for local development."""
    
    # Color codes
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'       # Reset
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors for local development."""
        
        # Get color for log level
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S.%f")[:-3]
        
        # Build message
        message = f"{color}[{timestamp}] {record.levelname:8s}{reset} "
        message += f"{record.name:20s} {record.getMessage()}"
        
        # Add exception info if present
        if record.exc_info:
            message += "\n" + self.formatException(record.exc_info)
        
        return message


def setup_logging() -> None:
    """Configure logging for the application."""
    
    # Get or create root logger
    root_logger = logging.getLogger()
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Set log level based on configuration
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    root_logger.setLevel(log_level)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    
    # Set formatter based on environment
    if is_local_environment():
        formatter = LocalFormatter()
    else:
        formatter = StructuredFormatter()
    
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Configure specific loggers
    
    # Suppress noisy third-party loggers in production
    if not is_local_environment():
        logging.getLogger("uvicorn").setLevel(logging.WARNING)
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("motor").setLevel(logging.WARNING)
        logging.getLogger("google").setLevel(logging.WARNING)
        logging.getLogger("aiohttp").setLevel(logging.WARNING)
    
    # Create application logger
    app_logger = logging.getLogger("yolo_dataset_api")
    app_logger.info(f"Logging configured - Level: {settings.log_level}, Environment: {settings.environment}")


# Application logger instance
logger = logging.getLogger("yolo_dataset_api")


def log_request(method: str, path: str, status_code: int, duration_ms: float, **kwargs) -> None:
    """Log HTTP request with structured data."""
    
    log_data = {
        "request_method": method,
        "request_path": path,
        "response_status": status_code,
        "response_time_ms": duration_ms,
        **kwargs
    }
    
    if status_code >= 500:
        logger.error("HTTP request failed", extra=log_data)
    elif status_code >= 400:
        logger.warning("HTTP client error", extra=log_data)
    else:
        logger.info("HTTP request completed", extra=log_data)


def log_job_progress(job_id: str, step: str, percentage: int, **kwargs) -> None:
    """Log job progress with structured data."""
    
    log_data = {
        "job_id": job_id,
        "current_step": step,
        "progress_percentage": percentage,
        **kwargs
    }
    
    logger.info("Job progress update", extra=log_data)


def log_database_operation(operation: str, collection: str, duration_ms: float, 
                          count: Optional[int] = None, **kwargs) -> None:
    """Log database operation with structured data."""
    
    log_data = {
        "db_operation": operation,
        "db_collection": collection,
        "operation_time_ms": duration_ms,
        **kwargs
    }
    
    if count is not None:
        log_data["result_count"] = count
    
    logger.debug("Database operation", extra=log_data)


def log_storage_operation(operation: str, path: str, size_bytes: Optional[int] = None, 
                         duration_ms: Optional[float] = None, **kwargs) -> None:
    """Log storage operation with structured data."""
    
    log_data = {
        "storage_operation": operation,
        "storage_path": path,
        **kwargs
    }
    
    if size_bytes is not None:
        log_data["file_size_bytes"] = size_bytes
    
    if duration_ms is not None:
        log_data["operation_time_ms"] = duration_ms
    
    logger.debug("Storage operation", extra=log_data)
