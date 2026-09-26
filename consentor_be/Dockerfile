# ==============================================================================
# Consentor Backend Dockerfile (InsightFace + ONNXRuntime + FastAPI)
# ==============================================================================

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system dependencies required for OpenCV, InsightFace, and ONNX Runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY app/ ./app/
COPY web/ ./web/
COPY run.py .
COPY .env.example .env

# Create persistent storage directories
RUN mkdir -p /app/enrolled_face_data /root/.insightface

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start Uvicorn server (1 worker to prevent concurrent model loading conflicts in container)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
