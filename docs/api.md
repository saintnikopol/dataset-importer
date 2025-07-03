# YOLO Dataset Management - API Reference

Base URL: `http://localhost:8000` (local) or `https://your-api.run.app` (production)

## 🔍 Overview

RESTful API for managing YOLO format datasets with support for 100GB+ scale imports and efficient querying.

**Authentication**: None required (assessment version)  
**Content-Type**: `application/json`  
**Response Format**: JSON with consistent error handling

## 📥 Import Operations

### Start Dataset Import
Initiate asynchronous import of YOLO dataset from remote URLs.

```http
POST /datasets/import
```

**Request Body**:
```json
{
  "name": "Traffic Detection Dataset",
  "description": "Urban traffic detection with 3 classes",
  "yolo_config_url": "https://storage.googleapis.com/bucket/dataset.yaml",
  "annotations_url": "https://storage.googleapis.com/bucket/labels.zip",
  "images_url": "https://storage.googleapis.com/bucket/images.zip"
}
```

**Successful Response** (202 Accepted):
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "message": "Import job started successfully",
  "created_at": "2025-07-03T10:00:00Z",
  "estimated_completion": "2025-07-03T10:30:00Z"
}
```

**Error Response** (400 Bad Request):
```json
{
  "error": "validation_error",
  "message": "Invalid YOLO config URL",
  "details": {
    "field": "yolo_config_url",
    "reason": "URL not accessible"
  },
  "timestamp": "2025-07-03T10:00:00Z"
}
```

### Check Import Status
Monitor the progress of a dataset import job.

```http
GET /datasets/import/{job_id}/status
```

**Path Parameters**:
- `job_id` (string): UUID of the import job

**Response (Processing)**:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "progress": {
    "percentage": 65,
    "current_step": "parsing_annotations",
    "steps_completed": ["download_files", "validate_format", "extract_archives"],
    "current_step_progress": "6500/10000 annotations processed"
  },
  "dataset_id": null,
  "started_at": "2025-07-03T10:00:00Z",
  "estimated_completion": "2025-07-03T10:25:00Z"
}
```

**Response (Completed)**:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "progress": {"percentage": 100},
  "dataset_id": "ds_abc123def456",
  "started_at": "2025-07-03T10:00:00Z",
  "completed_at": "2025-07-03T10:15:00Z",
  "summary": {
    "total_images": 10000,
    "total_annotations": 25000,
    "classes": ["person", "car", "bicycle"],
    "dataset_size_bytes": 2147483648
  }
}
```

**Response (Failed)**:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "failed",
  "progress": {"percentage": 30},
  "error": {
    "code": "invalid_yolo_format",
    "message": "YOLO label files contain invalid bounding box coordinates",
    "details": "Files: image_001.txt, image_045.txt have coordinates > 1.0"
  },
  "started_at": "2025-07-03T10:00:00Z",
  "failed_at": "2025-07-03T10:05:00Z"
}
```

## 📊 Dataset Operations

### List All Datasets
Retrieve paginated list of imported datasets.

```http
GET /datasets
```

**Query Parameters**:
- `page` (int, default=1): Page number for pagination
- `limit` (int, default=20, max=100): Items per page
- `sort_by` (string, default="created_at"): Sort field (created_at, name, size)
- `sort_order` (string, default="desc"): Sort order (asc, desc)
- `status` (string, optional): Filter by status (completed, processing, failed)

**Example Request**:
```http
GET /datasets?page=1&limit=20&sort_by=created_at&sort_order=desc&status=completed
```

**Response** (200 OK):
```json
{
  "datasets": [
    {
      "id": "ds_abc123def456",
      "name": "Traffic Detection Dataset",
      "description": "Urban traffic detection with 3 classes",
      "status": "completed",
      "created_at": "2025-07-03T10:00:00Z",
      "completed_at": "2025-07-03T10:15:00Z",
      "stats": {
        "total_images": 10000,
        "total_annotations": 25000,
        "classes_count": 3,
        "dataset_size_bytes": 2147483648
      },
      "classes": ["person", "car", "bicycle"]
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total_pages": 3,
    "total_items": 45,
    "has_next": true,
    "has_prev": false
  }
}
```

### Get Dataset Details
Retrieve detailed information about a specific dataset.

```http
GET /datasets/{dataset_id}
```

**Path Parameters**:
- `dataset_id` (string): Unique identifier of the dataset

**Response** (200 OK):
```json
{
  "id": "ds_abc123def456",
  "name": "Traffic Detection Dataset",
  "description": "Urban traffic detection with 3 classes",
  "status": "completed",
  "created_at": "2025-07-03T10:00:00Z",
  "completed_at": "2025-07-03T10:15:00Z",
  "import_job_id": "550e8400-e29b-41d4-a716-446655440000",
  "stats": {
    "total_images": 10000,
    "total_annotations": 25000,
    "classes_count": 3,
    "dataset_size_bytes": 2147483648,
    "avg_annotations_per_image": 2.5,
    "image_dimensions": {
      "width": {"min": 640, "max": 1920, "avg": 1280},
      "height": {"min": 480, "max": 1080, "avg": 720}
    }
  },
  "classes": [
    {"id": 0, "name": "person", "count": 15000},
    {"id": 1, "name": "car", "count": 8000},
    {"id": 2, "name": "bicycle", "count": 2000}
  ],
  "storage": {
    "images_path": "gs://bucket/datasets/ds_abc123def456/images/",
    "labels_path": "gs://bucket/datasets/ds_abc123def456/labels/"
  }
}
```

## 🖼️ Image Operations

### List Dataset Images
Get paginated list of images with their YOLO annotations.

```http
GET /datasets/{dataset_id}/images
```

**Path Parameters**:
- `dataset_id` (string): Unique identifier of the dataset

**Query Parameters**:
- `page` (int, default=1): Page number
- `limit` (int, default=50, max=200): Items per page
- `class_filter` (string, optional): Filter by class name
- `has_annotations` (boolean, optional): Filter images with/without annotations
- `sort_by` (string, default="filename"): Sort by (filename, size, annotation_count)

**Example Request**:
```http
GET /datasets/ds_abc123def456/images?page=1&limit=50&class_filter=person&has_annotations=true
```

**Response** (200 OK):
```json
{
  "dataset_id": "ds_abc123def456",
  "images": [
    {
      "id": "img_001",
      "filename": "traffic_001.jpg",
      "width": 1920,
      "height": 1080,
      "file_size_bytes": 245760,
      "image_url": "gs://bucket/datasets/ds_abc123def456/images/traffic_001.jpg",
      "annotations": [
        {
          "class_id": 0,
          "class_name": "person",
          "bbox": {
            "center_x": 0.5,
            "center_y": 0.6,
            "width": 0.1,
            "height": 0.3
          }
        },
        {
          "class_id": 1,
          "class_name": "car",
          "bbox": {
            "center_x": 0.3,
            "center_y": 0.4,
            "width": 0.2,
            "height": 0.15
          }
        }
      ],
      "annotation_count": 2
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 50,
    "total_pages": 200,
    "total_items": 10000,
    "has_next": true,
    "has_prev": false
  },
  "filters_applied": {
    "class_filter": "person",
    "has_annotations": true
  }
}
```

## 🏥 System Operations

### Health Check
Check service health and dependencies.

```http
GET /health
```

**Response** (200 OK):
```json
{
  "status": "healthy",
  "timestamp": "2025-07-03T10:00:00Z",
  "version": "1.0.0",
  "dependencies": {
    "mongodb": "connected",
    "cloud_storage": "connected",
    "job_queue": "operational"
  }
}
```

**Response** (503 Service Unavailable):
```json
{
  "status": "unhealthy",
  "timestamp": "2025-07-03T10:00:00Z",
  "version": "1.0.0",
  "dependencies": {
    "mongodb": "disconnected",
    "cloud_storage": "connected",
    "job_queue": "operational"
  },
  "errors": ["Unable to connect to MongoDB"]
}
```

### API Information
Get basic API information and documentation links.

```http
GET /
```

**Response** (200 OK):
```json
{
  "service": "YOLO Dataset Management API",
  "version": "1.0.0",
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
```

## ❌ Error Handling

### Error Response Format
All endpoints use consistent error response structure:

```json
{
  "error": "error_code",
  "message": "Human readable error message",
  "details": {
    "field": "specific_field",
    "reason": "detailed_reason"
  },
  "timestamp": "2025-07-03T10:00:00Z",
  "request_id": "req_123456789"
}
```

### Common Error Codes

| Code | Description | Status |
|------|-------------|---------|
| `validation_error` | Invalid request parameters | 400 |
| `dataset_not_found` | Dataset ID doesn't exist | 404 |
| `job_not_found` | Import job ID doesn't exist | 404 |
| `rate_limit_exceeded` | Too many requests | 429 |
| `internal_server_error` | Unexpected server error | 500 |
| `service_unavailable` | Dependency unavailable | 503 |

### Status Code Summary

| Endpoint | Success | Common Errors |
|----------|---------|---------------|
| `POST /datasets/import` | 202 | 400 (invalid URLs), 422 (validation) |
| `GET /datasets/import/{job_id}/status` | 200 | 404 (job not found) |
| `GET /datasets` | 200 | 400 (invalid params) |
| `GET /datasets/{id}` | 200 | 404 (not found) |
| `GET /datasets/{id}/images` | 200 | 404 (dataset not found) |
| `GET /health` | 200 | 503 (unhealthy) |

## 🔄 Rate Limiting (Future)

When authentication is implemented:
- **Default**: 1000 requests per hour per API key
- **Import operations**: 10 concurrent imports per API key
- **Headers**: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

## 📝 YOLO Format Specification

### Supported File Types
- **Images**: `.jpg`, `.jpeg`, `.png`
- **Labels**: `.txt` files with space-separated values
- **Config**: `.yaml` files with class definitions
- **Archives**: `.zip` files containing structured dataset

### Label Format
Each `.txt` file contains one line per bounding box:
```
class_id center_x center_y width height
```
- All coordinates normalized to 0.0-1.0 range
- `center_x`, `center_y`: Bounding box center coordinates
- `width`, `height`: Bounding box dimensions

### Config Format (dataset.yaml)
```yaml
path: /path/to/dataset
train: images/train
val: images/val
test: images/test
nc: 3
names: ['person', 'car', 'bicycle']
```

## 🧪 Testing Examples

### cURL Examples
```bash
# Import dataset
curl -X POST http://localhost:8000/datasets/import \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Dataset",
    "yolo_config_url": "https://example.com/dataset.yaml",
    "annotations_url": "https://example.com/labels.zip",
    "images_url": "https://example.com/images.zip"
  }'

# Check job status
curl http://localhost:8000/datasets/import/550e8400-e29b-41d4-a716-446655440000/status

# List datasets
curl "http://localhost:8000/datasets?page=1&limit=10"

# Get dataset images
curl "http://localhost:8000/datasets/ds_abc123def456/images?limit=5"
```

### Python Examples
```python
import httpx
import asyncio

async def test_api():
    async with httpx.AsyncClient() as client:
        # Import dataset
        response = await client.post(
            "http://localhost:8000/datasets/import",
            json={
                "name": "Test Dataset",
                "yolo_config_url": "https://example.com/dataset.yaml",
                "annotations_url": "https://example.com/labels.zip",
                "images_url": "https://example.com/images.zip"
            }
        )
        job_id = response.json()["job_id"]
        
        # Check status
        status_response = await client.get(
            f"http://localhost:8000/datasets/import/{job_id}/status"
        )
        print(status_response.json())

asyncio.run(test_api())
```

## 📚 Additional Resources

- **Interactive Documentation**: Available at `/docs` when API is running
- **OpenAPI Specification**: Available at `/openapi.json`
- **Architecture Guide**: See `architecture.md` for system design details
- **Setup Instructions**: See `README.md` for development setup

For questions or support, contact the development team or create an issue in the repository.
