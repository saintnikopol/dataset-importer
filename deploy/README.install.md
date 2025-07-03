# 1. Create and activate virtual environment
cd yolo-dataset-management
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 2. Upgrade pip to latest version
pip install --upgrade pip

# 3. Install project dependencies
pip install -r deploy/requirements.txt

# 4. Install development dependencies (for testing)
pip install pytest pytest-asyncio pytest-cov httpx

# 5. Verify installation
python -c "import fastapi; print('FastAPI installed successfully')"
python -c "import motor; print('Motor (MongoDB) installed successfully')"

# 6. Set up environment variables
cp .env.example .env
# Edit .env file with your settings