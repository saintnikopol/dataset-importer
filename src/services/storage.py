"""
Storage service with environment-specific implementations.
Handles file operations for both local development and Cloud Storage.
"""

import os
import shutil
import aiofiles
import aiohttp
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union, Optional, AsyncIterator
from urllib.parse import urlparse

from src.config import settings, is_local_environment
from src.utils.logging import logger
from src.utils.exceptions import StorageError


class StorageService(ABC):
    """Abstract base class for storage implementations."""
    
    @abstractmethod
    async def upload_file(self, data: bytes, path: str) -> str:
        """Upload file data and return URL."""
        pass
    
    @abstractmethod
    async def download_file(self, url: str) -> bytes:
        """Download file from URL and return data."""
        pass
    
    @abstractmethod
    async def upload_stream(self, stream: AsyncIterator[bytes], path: str) -> str:
        """Upload file from async stream."""
        pass
    
    @abstractmethod
    async def delete_file(self, path: str) -> bool:
        """Delete file and return success status."""
        pass
    
    @abstractmethod
    async def file_exists(self, path: str) -> bool:
        """Check if file exists."""
        pass
    
    @abstractmethod
    async def get_file_size(self, path: str) -> int:
        """Get file size in bytes."""
        pass


class LocalStorageService(StorageService):
    """Local filesystem storage for development."""
    
    def __init__(self, base_path: str = "./fake-gcs"):
        """Initialize local storage with base directory."""
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized local storage at: {self.base_path.absolute()}")
    
    def _get_file_path(self, path: str) -> Path:
        """Convert storage path to local file path."""
        # Remove leading slashes and ensure relative path
        clean_path = path.lstrip("/")
        return self.base_path / clean_path
    
    async def upload_file(self, data: bytes, path: str) -> str:
        """Upload file to local filesystem."""
        try:
            file_path = self._get_file_path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(data)
            
            # Return file:// URL for consistency
            url = f"file://{file_path.absolute()}"
            logger.debug(f"Uploaded file to local storage: {url}")
            return url
            
        except Exception as e:
            logger.error(f"Failed to upload file to {path}: {e}")
            raise StorageError(f"Upload failed: {e}")
    
    async def download_file(self, url: str) -> bytes:
        """Download file from URL (local file or HTTP)."""
        try:
            if url.startswith("file://"):
                # Local file URL
                file_path = Path(url[7:])  # Remove file:// prefix
                async with aiofiles.open(file_path, "rb") as f:
                    data = await f.read()
                
                logger.debug(f"Downloaded local file: {file_path}")
                return data
                
            elif url.startswith(("http://", "https://")):
                # HTTP URL - download from remote
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status != 200:
                            raise StorageError(f"HTTP {response.status}: {response.reason}")
                        
                        data = await response.read()
                        logger.debug(f"Downloaded remote file: {url}")
                        return data
            else:
                raise StorageError(f"Unsupported URL scheme: {url}")
                
        except Exception as e:
            logger.error(f"Failed to download file from {url}: {e}")
            raise StorageError(f"Download failed: {e}")
    
    async def upload_stream(self, stream: AsyncIterator[bytes], path: str) -> str:
        """Upload file from async stream."""
        try:
            file_path = self._get_file_path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            async with aiofiles.open(file_path, "wb") as f:
                async for chunk in stream:
                    await f.write(chunk)
            
            url = f"file://{file_path.absolute()}"
            logger.debug(f"Uploaded stream to local storage: {url}")
            return url
            
        except Exception as e:
            logger.error(f"Failed to upload stream to {path}: {e}")
            raise StorageError(f"Stream upload failed: {e}")
    
    async def delete_file(self, path: str) -> bool:
        """Delete file from local filesystem."""
        try:
            file_path = self._get_file_path(path)
            if file_path.exists():
                file_path.unlink()
                logger.debug(f"Deleted local file: {file_path}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to delete file {path}: {e}")
            return False
    
    async def file_exists(self, path: str) -> bool:
        """Check if file exists in local filesystem."""
        try:
            file_path = self._get_file_path(path)
            return file_path.exists()
        except Exception:
            return False
    
    async def get_file_size(self, path: str) -> int:
        """Get file size from local filesystem."""
        try:
            file_path = self._get_file_path(path)
            return file_path.stat().st_size if file_path.exists() else 0
        except Exception:
            return 0


class ProductionStorageService(StorageService):
    """Google Cloud Storage implementation for production."""
    
    def __init__(self):
        """Initialize Cloud Storage client."""
        try:
            from google.cloud import storage
            
            self.client = storage.Client(project=settings.gcp_project)
            self.bucket_name = settings.storage_bucket
            self.bucket = self.client.bucket(self.bucket_name)
            
            logger.info(f"Initialized Cloud Storage bucket: {self.bucket_name}")
            
        except ImportError as e:
            logger.error(f"Failed to import Cloud Storage dependencies: {e}")
            raise StorageError("Cloud Storage dependencies not available")
        except Exception as e:
            logger.error(f"Failed to initialize Cloud Storage: {e}")
            raise StorageError(f"Storage initialization failed: {e}")
    
    async def upload_file(self, data: bytes, path: str) -> str:
        """Upload file to Cloud Storage."""
        try:
            blob = self.bucket.blob(path)
            
            # Upload data
            blob.upload_from_string(data)
            
            # Return gs:// URL
            url = f"gs://{self.bucket_name}/{path}"
            logger.debug(f"Uploaded file to Cloud Storage: {url}")
            return url
            
        except Exception as e:
            logger.error(f"Failed to upload file to {path}: {e}")
            raise StorageError(f"Upload failed: {e}")
    
    async def download_file(self, url: str) -> bytes:
        """Download file from URL (Cloud Storage or HTTP)."""
        try:
            if url.startswith("gs://"):
                # Cloud Storage URL
                # Parse gs://bucket/path format
                parsed = urlparse(url)
                bucket_name = parsed.netloc
                blob_path = parsed.path.lstrip("/")
                
                # Get blob and download
                bucket = self.client.bucket(bucket_name)
                blob = bucket.blob(blob_path)
                
                data = blob.download_as_bytes()
                logger.debug(f"Downloaded from Cloud Storage: {url}")
                return data
                
            elif url.startswith(("http://", "https://")):
                # HTTP URL - download from remote
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status != 200:
                            raise StorageError(f"HTTP {response.status}: {response.reason}")
                        
                        data = await response.read()
                        logger.debug(f"Downloaded remote file: {url}")
                        return data
            else:
                raise StorageError(f"Unsupported URL scheme: {url}")
                
        except Exception as e:
            logger.error(f"Failed to download file from {url}: {e}")
            raise StorageError(f"Download failed: {e}")
    
    async def upload_stream(self, stream: AsyncIterator[bytes], path: str) -> str:
        """Upload file from async stream to Cloud Storage."""
        try:
            blob = self.bucket.blob(path)
            
            # Collect stream data (for now - could be optimized with resumable uploads)
            chunks = []
            async for chunk in stream:
                chunks.append(chunk)
            
            data = b"".join(chunks)
            blob.upload_from_string(data)
            
            url = f"gs://{self.bucket_name}/{path}"
            logger.debug(f"Uploaded stream to Cloud Storage: {url}")
            return url
            
        except Exception as e:
            logger.error(f"Failed to upload stream to {path}: {e}")
            raise StorageError(f"Stream upload failed: {e}")
    
    async def delete_file(self, path: str) -> bool:
        """Delete file from Cloud Storage."""
        try:
            blob = self.bucket.blob(path)
            blob.delete()
            logger.debug(f"Deleted from Cloud Storage: {path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete file {path}: {e}")
            return False
    
    async def file_exists(self, path: str) -> bool:
        """Check if file exists in Cloud Storage."""
        try:
            blob = self.bucket.blob(path)
            return blob.exists()
        except Exception:
            return False
    
    async def get_file_size(self, path: str) -> int:
        """Get file size from Cloud Storage."""
        try:
            blob = self.bucket.blob(path)
            blob.reload()
            return blob.size or 0
        except Exception:
            return 0


# Global storage service instance
_storage_service: Optional[StorageService] = None


def get_storage_service() -> StorageService:
    """Get storage service instance based on environment."""
    global _storage_service
    
    if _storage_service is None:
        if is_local_environment():
            _storage_service = LocalStorageService()
        else:
            _storage_service = ProductionStorageService()
    
    return _storage_service


async def health_check_storage() -> Dict[str, Any]:
    """Check storage service health for monitoring."""
    try:
        storage = get_storage_service()
        
        # Test basic operations
        test_data = b"health_check"
        test_path = "health_check/test.txt"
        
        # Upload test file
        await storage.upload_file(test_data, test_path)
        
        # Check if file exists
        exists = await storage.file_exists(test_path)
        
        # Clean up
        await storage.delete_file(test_path)
        
        return {
            "status": "healthy" if exists else "unhealthy",
            "storage_type": "local" if is_local_environment() else "cloud_storage"
        }
        
    except Exception as e:
        logger.error(f"Storage health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }
