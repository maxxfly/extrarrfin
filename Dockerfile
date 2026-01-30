# Dockerfile for ExtrarrFin
# Multi-stage build for optimized image size and faster builds

FROM python:3.11-slim as base

# Set working directory
WORKDIR /app

# Install system dependencies in one layer with cleanup
# Use --no-install-recommends to minimize package installation
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    unzip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install Deno (required by yt-dlp for certain extractors)
# Cache this layer separately as it changes rarely
RUN curl -fsSL https://deno.land/install.sh | sh \
    && mv /root/.deno/bin/deno /usr/local/bin/deno

# Copy requirements first for better layer caching
# This layer only rebuilds when requirements.txt changes
COPY requirements.txt .

# Install Python dependencies with pip cache
# Use --no-cache-dir to reduce image size but allow pip to use HTTP cache
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (this changes most often, so it's last)
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
