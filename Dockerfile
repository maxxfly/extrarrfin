# Dockerfile for ExtrarrFin
# Based on Alpine Linux for minimal image size

FROM python:3.11-alpine

# Set working directory
WORKDIR /app

# Install system dependencies
# ffmpeg is required for yt-dlp
RUN apk add --no-cache \
    ffmpeg \
    gcc \
    musl-dev \
    python3-dev \
    libffi-dev \
    openssl-dev \
    cargo \
    && rm -rf /var/cache/apk/*

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY extrarrfin/ ./extrarrfin/
COPY extrarrfin.py .

# Create directory for config
RUN mkdir -p /config

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Volume for configuration
VOLUME ["/config", "/media"]

# Default command (can be overridden)
ENTRYPOINT ["python", "extrarrfin.py"]
CMD ["--help"]
