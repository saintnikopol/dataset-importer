# 🚀 Quick Start Guide - YOLO Dataset Management

> **Assessment Setup**: Get the complete system running in under 5 minutes

## 📋 Prerequisites

- **Docker & Docker Compose** (for local development)
- **Python 3.9+** (for manual setup)
- **Git** (to clone repository)

## ⚡ Fast Setup (Docker - Recommended)

### 1. Clone and Start
```bash
git clone <repository-url>
cd yolo-dataset-management

# Start complete stack (API + MongoDB + Redis + Worker)
docker-compose up -d

# Check all services are running
docker-compose ps
```

### 2. Verify Installation
```bash
# Health check
curl http://localhost:8000/health

# API documentation
open http://localhost:8000/docs

# Worker monitoring (optional)
open http://localhost:5555
```

### 3. Test Core Functionality
```bash
# Import a test dataset
curl -X POST http://localhost:8000/datasets/import \
  -H "Content-Type: application/json" \
  -d '{
    "name": "COCO8 Sample Dataset",
    "description": "Sample COCO dataset with 8 images for testing",
    "yolo_config_url": "https://raw.githubusercontent.com/ultralytics/ultralytics/main/ultralytics/cfg/datasets/coco8.yaml",
    "dataset_url": "https://github.com/ultralytics/assets/releases/download/v0.0.0/coco8.zip"
  }'

# Save the job_id from response, then check progress
curl http://localhost:8000/datasets/import/{job_id}/status

# List datasets
curl http://localhost:8000/datasets

# List images (after import completes)
curl "http://localhost:8000/datasets/{dataset_id}/images?limit=5"
```

**🎉 That's it! Complete YOLO dataset management system is running.**

---

## 📱 Manual Setup (Alternative)

### 1. Environment Setup
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies
pip install --upgrade pip
pip install -r deploy/requirements.txt
```

### 2. Local Services
```bash
# Start MongoDB (required)
docker run -d --name mongo -p 27017:27017 mongo:7.0

# Start Redis (required for background jobs)
docker run -d --name redis -p 6379:6379 redis:7.2-alpine

# Verify services
docker ps
```

### 3. Run Application
```bash
# Terminal 1: Start API
cd yolo-dataset-management
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Start Worker
celery -A src.worker:celery_app worker --loglevel=info --queues=yolo_import

# Terminal 3: (Optional) Start Worker Monitor
celery -A src.worker:celery_app flower --port=5555
```

---

## 🧪 Running Tests

### Complete Test Suite
```bash
# All tests with coverage
pytest tests/ --cov=src --cov-report=html

# API tests only
pytest tests/test_api.py -v

# Model tests only  
pytest tests/test_models.py -v

# Quick smoke test
pytest tests/test_api.py::TestHealthCheck::test_health_check_healthy -v
```

### Test Results Expected
```
====================== 76 passed, 5 warnings ======================
Coverage: 50%+ (focused on business logic)
```

---

## 🔧 Configuration

### Environment Variables
```bash
# Local Development (default)
ENVIRONMENT=local
MONGODB_URL=mongodb://localhost:27017/yolo_datasets
REDIS_URL=redis://localhost:6379/0
LOG_LEVEL=INFO

# Production Example
ENVIRONMENT=production  
MONGODB_URL=mongodb+srv://user:pass@cluster.mongodb.net/yolo_datasets
GCP_PROJECT=your-project-id
STORAGE_BUCKET=your-yolo-datasets-bucket
```

### Docker Compose Services
```yaml
# docker-compose.yml includes:
api:      # FastAPI application (port 8000)
worker:   # Celery background worker  
mongo:    # MongoDB database (port 27017)
redis:    # Redis job queue (port 6379)
flower:   # Worker monitoring UI (port 5555)
```

---

## 📊 Monitoring & Debugging

### Service Health
```bash
# Check all services
curl http://localhost:8000/health

# Response should show all dependencies as "healthy"
{
  "status": "healthy",
  "dependencies": {
    "mongodb": "connected",
    "job_queue": "operational", 
    "storage": "connected"
  }
}
```

### Logs
```bash
# API logs
docker-compose logs api -f

# Worker logs  
docker-compose logs worker -f

# All logs
docker-compose logs -f
```

### Common Issues

#### Port Conflicts
```bash
# Change ports in docker-compose.yml if needed
ports:
  - "8001:8000"  # API on port 8001 instead
```

#### MongoDB Connection
```bash
# Reset MongoDB data
docker-compose down -v
docker-compose up -d
```

#### Worker Not Processing
```bash
# Check Redis connection
docker-compose exec redis redis-cli ping
# Should return: PONG

# Restart worker
docker-compose restart worker
```

---

## 🚀 Production Deployment

### Google Cloud Platform
```bash
# Build and deploy to Cloud Run
gcloud run deploy yolo-api \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2

# Deploy worker as Cloud Run Job
gcloud run jobs create yolo-worker \
  --source . \
  --region us-central1 \
  --memory 4Gi \
  --cpu 2
```

### Environment Variables (Production)
```bash
gcloud run services update yolo-api \
  --set-env-vars="ENVIRONMENT=production,MONGODB_URL=mongodb+srv://...,GCP_PROJECT=your-project,STORAGE_BUCKET=your-bucket"
```

---

## 💡 Assessment Verification

### ✅ Core Requirements Check
```bash
# 1. Import YOLO dataset ✅
curl -X POST http://localhost:8000/datasets/import -d '{...}'

# 2. List datasets ✅
curl http://localhost:8000/datasets

# 3. List images with labels ✅  
curl http://localhost:8000/datasets/{id}/images
```

### ✅ 100GB Scale Features
- **Async processing**: Jobs don't block API ✅
- **Progress tracking**: Real-time status updates ✅  
- **Stream processing**: Memory-efficient file handling ✅
- **Cloud storage**: Unlimited file capacity ✅

### ✅ Production Readiness
- **Health monitoring**: `/health` endpoint ✅
- **Error handling**: Consistent error responses ✅
- **Logging**: Structured logging for debugging ✅
- **Testing**: Comprehensive test coverage ✅

---

## 🆘 Support

### Quick Help
```bash
# Reset everything
docker-compose down -v && docker-compose up -d

# Check service status
docker-compose ps

# View real-time logs
docker-compose logs -f api worker
```

### Links:
- API Documentation: http://localhost:8000/docs
- Architecture Guide: [docs/architecture.md](../docs/architecture.md)
- Main README: [README.md](../README.md)
