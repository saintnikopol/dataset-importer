"""
Custom exception classes for YOLO Dataset Management API.
Provides structured error handling across the application.
"""

from typing import Optional, Dict, Any


class YOLODatasetError(Exception):
    """Base exception class for YOLO dataset management errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        """Initialize exception with message and optional details."""
        super().__init__(message)
        self.message = message
        self.details = details or {}
    
    def __str__(self) -> str:
        """String representation of the exception."""
        return self.message
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error": self.__class__.__name__.lower().replace("error", "_error"),
            "message": self.message,
            "details": self.details
        }


class ProcessingError(YOLODatasetError):
    """Raised when dataset processing fails."""
    
    def __init__(self, message: str, step: Optional[str] = None, 
                 details: Optional[Dict[str, Any]] = None):
        """Initialize processing error with optional step information."""
        super().__init__(message, details)
        self.step = step
        
        if step:
            self.details["processing_step"] = step


class ValidationError(YOLODatasetError):
    """Raised when data validation fails."""
    
    def __init__(self, message: str, field: Optional[str] = None, 
                 value: Optional[Any] = None, details: Optional[Dict[str, Any]] = None):
        """Initialize validation error with optional field information."""
        super().__init__(message, details)
        self.field = field
        self.value = value
        
        if field:
            self.details["invalid_field"] = field
        if value is not None:
            self.details["invalid_value"] = str(value)


class StorageError(YOLODatasetError):
    """Raised when storage operations fail."""
    
    def __init__(self, message: str, operation: Optional[str] = None, 
                 path: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """Initialize storage error with optional operation details."""
        super().__init__(message, details)
        self.operation = operation
        self.path = path
        
        if operation:
            self.details["storage_operation"] = operation
        if path:
            self.details["storage_path"] = path


class DatabaseError(YOLODatasetError):
    """Raised when database operations fail."""
    
    def __init__(self, message: str, operation: Optional[str] = None, 
                 collection: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """Initialize database error with optional operation details."""
        super().__init__(message, details)
        self.operation = operation
        self.collection = collection
        
        if operation:
            self.details["db_operation"] = operation
        if collection:
            self.details["db_collection"] = collection


class AuthenticationError(YOLODatasetError):
    """Raised when authentication fails (future use)."""
    pass


class AuthorizationError(YOLODatasetError):
    """Raised when authorization fails (future use)."""
    pass


class RateLimitError(YOLODatasetError):
    """Raised when rate limits are exceeded (future use)."""
    
    def __init__(self, message: str, retry_after: Optional[int] = None, 
                 details: Optional[Dict[str, Any]] = None):
        """Initialize rate limit error with retry information."""
        super().__init__(message, details)
        self.retry_after = retry_after
        
        if retry_after:
            self.details["retry_after_seconds"] = retry_after


class ExternalServiceError(YOLODatasetError):
    """Raised when external service calls fail."""
    
    def __init__(self, message: str, service: Optional[str] = None, 
                 status_code: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        """Initialize external service error with service details."""
        super().__init__(message, details)
        self.service = service
        self.status_code = status_code
        
        if service:
            self.details["external_service"] = service
        if status_code:
            self.details["http_status_code"] = status_code


# Exception mapping for HTTP status codes
EXCEPTION_STATUS_MAP = {
    ValidationError: 400,
    AuthenticationError: 401,
    AuthorizationError: 403,
    RateLimitError: 429,
    ProcessingError: 500,
    StorageError: 500,
    DatabaseError: 500,
    ExternalServiceError: 502,
    YOLODatasetError: 500
}


def get_http_status_code(exception: Exception) -> int:
    """Get appropriate HTTP status code for exception."""
    for exc_type, status_code in EXCEPTION_STATUS_MAP.items():
        if isinstance(exception, exc_type):
            return status_code
    return 500  # Default to internal server error


def format_exception_response(exception: YOLODatasetError, request_id: Optional[str] = None) -> Dict[str, Any]:
    """Format exception as standardized API error response."""
    from datetime import datetime
    
    response = exception.to_dict()
    response["timestamp"] = datetime.utcnow().isoformat() + "Z"
    
    if request_id:
        response["request_id"] = request_id
    
    return response
