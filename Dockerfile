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

# Copy ONLY dependency files and source (needed for package discovery)
COPY setup.py setup.cfg pyproject.toml README.md LICENSE.txt ./
COPY src/ src/
COPY templates/ templates/

# Install Python dependencies (cached unless setup.py changes)
RUN pip install --upgrade pip setuptools wheel && \
    pip install .

# Copy tests (optional, for testing in container)
COPY tests/ tests/

# Create directories for volumes
RUN mkdir -p /app/chroma

# Expose ports
EXPOSE 8000 8888

# Default: run API server
ENTRYPOINT ["graphaide"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000"]
