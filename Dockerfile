# ---------------------------
# Base Image
# ---------------------------
FROM python:3.11-slim

# ---------------------------
# Set working directory
# ---------------------------
WORKDIR /app

# ---------------------------
# Install system dependencies for OpenCV
# ---------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \

        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender-dev \
        libgomp1 \
        git \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip

# ---------------------------
# Copy requirements and install
# ---------------------------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------------------------
# Copy app code
# ---------------------------
COPY . .

# ---------------------------
# Expose port
# ---------------------------
EXPOSE 8000

# ---------------------------
# Use non-root user (optional, more secure)
# ---------------------------
RUN useradd -m appuser
USER appuser

# ---------------------------
# Run FastAPI app (production ready)
# ---------------------------
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
