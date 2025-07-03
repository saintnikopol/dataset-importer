# YOLO Dataset Management - Architecture Guide

## 🎯 System Overview

The YOLO Dataset Management system is designed to handle computer vision datasets up to 100GB in size using a microservices architecture built on Google Cloud Platform.

## 🏗️ High-Level Architecture

```
┌─────────────┐    ┌──────────────┐    ┌─────────────────┐    ┌──────────────┐
│   Client    │───▶│  Cloud Run   │───▶│  Cloud Tasks    │───▶│ Cloud Run    │
│ Application │    │   (API)      │    │  (Job Queue)    │    │  (Worker)    │
└─────────────┘    └──────────────┘    └─────────────────┘    └──────────────┘
                           │                                           │
                           ▼                                           ▼
                   ┌──────────────┐                           ┌──────────────┐
                   │   MongoDB    │◀──────────────────────────│ Cloud Storage│
                   │ (Metadata)   │                           │ (Raw Files)  │
                   └──────────────┘                           └──────────────┘
```

## 🔧 Core Components

### 1. API Layer (Cloud Run)
**Purpose**: Handle HTTP requests and provide REST API endpoints

**Key Responsibilities**:
- Validate incoming requests
- Manage dataset metadata operations
- Initiate background processing jobs
- Serve paginated data responses
- Health monitoring and status checks

**Technology**: FastAPI + Python 3.9+

**Endpoints**:
- `POST /datasets/import` - Initiate async dataset import
- `GET /datasets` - List datasets with pagination
- `GET /datasets/{id}/images` - Retrieve images with annotations
- `GET /datasets/import/{job_id}/status` - Check import progress

### 2. Background Workers (Cloud Run Jobs)
**Purpose**: Process large datasets asynchronously without blocking the API

**Key Responsibilities**:
- Download files from remote URLs
- Parse and validate YOLO format
- Extract and process image archives
- Store processed data in MongoDB and Cloud Storage
- Update job progress and handle errors

**Processing Flow**:
1. Download dataset files (config, images, annotations)
2. Validate YOLO format compliance
3. Extract image dimensions and metadata
4. Parse annotation files into structured format
5. Store metadata in MongoDB with proper indexing
6. Update job status throughout process

### 3. Database Layer (MongoDB)
**Purpose**: Store metadata, annotations, and job tracking information

**Collections Design**:
- `datasets` - Dataset metadata and statistics
- `import_jobs` - Job progress tracking and error handling
- `images` - Image metadata with embedded annotations

**Indexing Strategy**:
- `dataset_id` compound indexes for fast image queries
- Status and timestamp indexes for job tracking
- Proper pagination support for large collections

### 4. Storage Layer (Cloud Storage)
**Purpose**: Store raw files (images, labels, configs) separate from metadata

**Organization**:
```
bucket/
├── datasets/
│   ├── {dataset_id}/
│   │   ├── images/
│   │   │   ├── image1.jpg
│   │   │   └── image2.jpg
│   │   ├── labels/
│   │   │   ├── image1.txt
│   │   │   └── image2.txt
│   │   └── config/
│   │       └── dataset.yaml
│   └── temp/
│       └── {job_id}/
│           └── processing_files/
```

### 5. Job Queue (Cloud Tasks)
**Purpose**: Manage asynchronous processing with reliability and scaling

**Features**:
- Automatic retries on failure
- Dead letter queues for problematic jobs
- Rate limiting to prevent resource exhaustion
- Monitoring and alerting integration

## 🚀 Data Flow Patterns

### Dataset Import Flow
1. **Client Request**: POST to `/datasets/import` with URLs
2. **Job Creation**: API creates job record in MongoDB
3. **Queue Enqueue**: Job details sent to Cloud Tasks
4. **Background Processing**: Worker picks up job and processes
5. **Progress Updates**: Worker updates job status in MongoDB
6. **Completion**: Dataset ready for querying via API

### Query Flow
1. **Client Request**: GET to `/datasets/{id}/images`
2. **Database Query**: MongoDB query with proper indexing
3. **Pagination**: Efficient offset/limit or cursor-based pagination
4. **Response Assembly**: JSON response with image metadata and annotations
5. **Caching**: Optional Redis cache for frequently accessed data

## 🏭 Environment Strategies

### Local Development
- **Queue**: Celery + Redis (simulates Cloud Tasks)
- **Storage**: Local filesystem (simulates Cloud Storage)
- **Database**: Local MongoDB via Docker
- **Worker**: Celery worker processes

### Production
- **Queue**: Google Cloud Tasks
- **Storage**: Google Cloud Storage
- **Database**: MongoDB Atlas or self-hosted
- **Worker**: Cloud Run Jobs

### Environment Abstraction
```python
# Dependency injection pattern
class JobQueue(ABC):
    @abstractmethod
    async def enqueue_job(self, job_data): pass

class LocalJobQueue(JobQueue):      # Celery implementation
class ProductionJobQueue(JobQueue):  # Cloud Tasks implementation

def get_job_queue() -> JobQueue:
    return LocalJobQueue() if settings.environment == "local" else ProductionJobQueue()
```

## 📊 Scalability Design

### 100GB Dataset Constraints
- **Memory Management**: Streaming file processing, no full-file loading
- **Timeout Handling**: Async processing prevents API timeouts
- **Progress Tracking**: Real-time status updates for long operations
- **Error Recovery**: Partial failure handling and resumable processing

### Horizontal Scaling
- **API Scaling**: Cloud Run auto-scaling based on request volume
- **Worker Scaling**: Cloud Run Jobs can process multiple datasets concurrently
- **Database Scaling**: MongoDB sharding for large collections
- **Storage Scaling**: Cloud Storage handles unlimited file storage

### Performance Optimizations
- **Database Indexing**: Compound indexes for common query patterns
- **Caching**: Redis for frequently accessed metadata
- **Compression**: Gzip responses for large JSON payloads
- **Connection Pooling**: Efficient database connection management

## 🔒 Security & Reliability

### Data Security
- **Input Validation**: Pydantic models for request validation
- **Error Sanitization**: Safe error messages without sensitive data
- **Access Control**: Future: API key authentication and rate limiting

### Reliability Patterns
- **Circuit Breakers**: Protect against cascading failures
- **Retry Logic**: Exponential backoff for transient failures
- **Health Checks**: Comprehensive service health monitoring
- **Graceful Degradation**: Partial functionality during outages

### Monitoring & Observability
- **Structured Logging**: JSON logs with correlation IDs
- **Metrics Collection**: Response times, error rates, queue depths
- **Alerting**: Proactive monitoring for service health
- **Distributed Tracing**: Request flow tracking across services

## 🔄 Future Enhancements

### Short Term (Next 3 months)
- API authentication and authorization
- Enhanced error handling and recovery
- Performance optimization and caching
- Comprehensive monitoring dashboard

### Medium Term (3-6 months)
- Multi-tenant support with data isolation
- Advanced YOLO format validation
- Real-time WebSocket progress updates
- Automated dataset quality assessment

### Long Term (6+ months)
- Machine learning pipeline integration
- Advanced dataset analytics and insights
- Multi-region deployment for global scale
- Integration with popular ML training frameworks

## 🎯 Design Decisions & Trade-offs

### Async Processing vs Synchronous
**Decision**: Async background processing for imports
**Rationale**: 100GB datasets require hours to process, can't block API
**Trade-off**: Added complexity vs. better user experience

### MongoDB vs Relational Database
**Decision**: MongoDB for metadata storage
**Rationale**: Flexible schema for varying annotation formats, JSON-native
**Trade-off**: Less strict consistency vs. better development velocity

### Cloud Run vs Kubernetes
**Decision**: Cloud Run for both API and workers
**Rationale**: Serverless simplicity, automatic scaling, reduced operational overhead
**Trade-off**: Less control vs. easier management

### Embedded vs Separate Annotations
**Decision**: Embed YOLO annotations in image documents
**Rationale**: Single query for image + annotations, better performance
**Trade-off**: Document size vs. query efficiency

This architecture provides a solid foundation for handling large-scale YOLO datasets while maintaining development velocity and operational simplicity.
