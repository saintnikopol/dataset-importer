# YOLO Dataset Management API

A scalable backend API system for importing, processing, and serving YOLO format datasets up to 100GB in size.

## 🎯 Core Features

- **Async YOLO Dataset Import** - Handle massive datasets without timeouts
- **Fast Dataset Listing** - Paginated APIs with efficient querying
- **Image & Annotation Serving** - Access images with their YOLO labels
- **Progress Tracking** - Real-time import job status monitoring
- **Scale Ready** - Built for 100GB+ datasets using GCP infrastructure

## 🏗️ Architecture

### Technology Stack
- **Backend**: Python + FastAPI
- **Database**: MongoDB (metadata & annotations)
- **Storage**: Google Cloud Storage (raw files)
- **Queue**: Cloud Tasks (production) / Celery + Redis (local)
- **Hosting**: Cloud Run (serverless containers)

### Key Components
- **Main API** - REST endpoints for dataset operations
- **Background Workers** - Async processing of large imports
- **Storage Service** - Abstracted file operations (local/cloud)
- **Database Service** - MongoDB operations with proper indexing

## 🚀 Quick Start

### Local Development
```bash
# Clone and setup
git clone <repository-url>
cd yolo-dataset-management
cp .env.example .env

# Start with Docker Compose
docker-compose up -d

# Check API health
curl http://localhost:8000/health

# View API documentation
open http://localhost:8000/docs
```

### Testing Import
```bash
# Import a dataset
curl -X POST http://localhost:8000/datasets/import \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Dataset",
    "yolo_config_url": "https://example.com/dataset.yaml",
    "annotations_url": "https://example.com/labels.zip",
    "images_url": "https://example.com/images.zip"
  }'

# Check import status
curl http://localhost:8000/datasets/import/{job_id}/status

# List datasets
curl http://localhost:8000/datasets

# Get images for dataset
curl http://localhost:8000/datasets/{dataset_id}/images
```

## 📋 API Endpoints

### Core Operations
- `POST /datasets/import` - Start async dataset import
- `GET /datasets/import/{job_id}/status` - Check import progress
- `GET /datasets` - List all datasets (paginated)
- `GET /datasets/{id}` - Get dataset details
- `GET /datasets/{id}/images` - List images with annotations
- `GET /health` - Service health check

### YOLO Format Support
- **Images**: .jpg, .png files
- **Labels**: .txt files with normalized coordinates
- **Config**: .yaml files with class definitions
- **Archive**: .zip files for batch uploads

## 🔧 Development

### Project Structure
```
src/
├── main.py              # FastAPI application
├── worker.py            # Background job processing
├── config.py            # Environment configuration
├── models/              # Pydantic data models
├── services/            # Business logic services
├── api/                 # API route handlers
└── utils/               # Shared utilities

tests/                   # Test suite
deploy/                  # Docker & deployment configs
docs/                    # Documentation
```

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Run specific test file
pytest tests/test_api.py
```

### Code Quality
```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Type checking
mypy src/

# Linting
flake8 src/
```

## 🌐 Production Deployment

### Prerequisites
- Google Cloud Project with APIs enabled:
  - Cloud Run
  - Cloud Storage
  - Cloud Tasks
  - MongoDB Atlas or Cloud-hosted MongoDB

### Deploy to GCP
```bash
# Build and deploy main API
gcloud run deploy yolo-api \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated

# Deploy background worker
gcloud run jobs create yolo-worker \
  --source . \
  --region us-central1
```

### Environment Variables (Production)
```bash
ENVIRONMENT=production
MONGODB_URL=mongodb+srv://user:pass@cluster.mongodb.net/yolo_datasets
GCP_PROJECT=your-project-id
STORAGE_BUCKET=your-yolo-datasets-bucket
CLOUD_TASKS_QUEUE=projects/your-project/locations/us-central1/queues/yolo-import
WORKER_URL=https://yolo-worker-xxx.run.app
```

## 📊 Monitoring & Observability

### Health Checks
- API health endpoint: `GET /health`
- Database connectivity monitoring
- Storage service availability

### Logging
- Structured JSON logging
- Request/response tracking
- Error monitoring with stack traces
- Performance metrics

### Metrics
- API response times
- Import job success/failure rates
- Dataset storage utilization
- Queue depth monitoring

## 🔒 Security Considerations

### Current State (Assessment)
- No authentication required
- Basic input validation
- Error message sanitization

### Production Recommendations
- API key authentication
- Rate limiting per client
- Input sanitization for file uploads
- Audit logging for data operations

## 📈 Performance & Scale

### 100GB Dataset Handling
- **Streaming uploads** - Chunked file processing
- **Async processing** - Background job queues
- **Progress tracking** - Real-time status updates
- **Efficient storage** - Cloud Storage for files, MongoDB for metadata

### Database Optimization
- Proper indexing for fast queries
- Pagination for large result sets
- Embedded annotations for single-query access
- Connection pooling and caching

## 🤝 Contributing

### Development Workflow
1. Fork the repository
2. Create feature branch
3. Implement changes with tests
4. Run quality checks
5. Submit pull request

### Code Standards
- Type hints throughout
- Comprehensive error handling
- Unit tests for all business logic
- Integration tests for APIs
- Clear documentation

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For questions or issues:
- Check the [API Documentation](api.md)
- Review [Architecture Guide](architecture.md)
- Create an issue in the repository
- Contact the development team
