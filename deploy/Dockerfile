# Multi-stage Dockerfile for YOLO Dataset Management API
FROM python:3.11-slim as base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY deploy/requirements.txt requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ src/
COPY pyproject.toml .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash yolo && \
    chown -R yolo:yolo /app
USER yolo

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command for API
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Worker variant (override CMD for worker deployments)
# CMD ["celery", "-A", "src.worker", "worker", "--loglevel=info"]
