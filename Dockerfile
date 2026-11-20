# GraphAide Dockerfile (Production)
# Multi-agentic query and reasoning system with knowledge graphs
# Optimized for layer caching with BuildKit

FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies (rarely changes)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    build-essential \
    vim \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only what the package build needs (no tests, notebooks, or secrets)
COPY pyproject.toml MANIFEST.in README.md LICENSE.txt ./
COPY src/ src/

# Install Python dependencies (cached unless pyproject.toml changes)
RUN pip install --upgrade pip setuptools wheel && \
    pip install . && \
    rm -rf /app/build /app/src/*.egg-info

# Create directories for volumes
RUN mkdir -p /app/chroma

# Expose ports
EXPOSE 8000 8888

# Default: run API server
ENTRYPOINT ["graphaide"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000"]
