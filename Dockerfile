# Dockerfile for ExtrarrFin
# Based on Debian slim for better compatibility with Deno (required by yt-dlp)

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
# ffmpeg is required for yt-dlp
# curl and unzip are required for Deno installation
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    unzip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Deno (required by yt-dlp for certain extractors)
RUN curl -fsSL https://deno.land/install.sh | sh \
    && mv /root/.deno/bin/deno /usr/local/bin/deno \
    && deno --version

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
