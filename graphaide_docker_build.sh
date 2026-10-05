#!/bin/bash

# GraphAide Docker Build and Push Script
# Rebuilds both production and development images with version tagging
# Optimized with BuildKit for faster builds and better caching
# Optionally pushes to DockerHub
#
# Usage:
#   ./graphaide_docker_build.sh 2.0.1              # Build only
#   ./graphaide_docker_build.sh 2.0.1 push         # Build and push
#   ./graphaide_docker_build.sh 2.0.1 push --clean # Build, push, and prune images

set -e  # Exit on error

# Enable BuildKit for better caching and parallel builds
export DOCKER_BUILDKIT=1

# Parameters
VERSION="${1:-latest}"
PUSH_FLAG="${2:-}"
CLEAN_FLAG="${3:-}"
PROD_ONLY_FLAG=""

# Parse flags (handle --prod-only in any position)
for arg in "$@"; do
    if [[ "$arg" == "--prod-only" ]]; then
        PROD_ONLY_FLAG="--prod-only"
    elif [[ "$arg" == "--clean" ]]; then
        CLEAN_FLAG="--clean"
    fi
done

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "=================================================="
echo "GraphAide Docker Build and Push Script"
echo "=================================================="
echo "Version: $VERSION"
echo "BuildKit: Enabled (for faster builds)"
if [[ "$PUSH_FLAG" == "push" || "$PUSH_FLAG" == "--push" ]]; then
    echo "Mode: BUILD + PUSH"
else
    echo "Mode: BUILD ONLY"
fi
if [[ "$CLEAN_FLAG" == "--clean" ]]; then
    echo "Cleanup: Will prune images after push"
fi
if [[ "$PROD_ONLY_FLAG" == "--prod-only" ]]; then
    echo "Images: Production only (skipping dev)"
fi
echo ""

# Check if Docker is running
echo -e "${BLUE}[*] Checking Docker...${NC}"
if ! docker ps > /dev/null 2>&1; then
    echo -e "${RED}✗ Error: Docker is not running${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker is running${NC}"
echo ""

# Build production image
echo -e "${BLUE}[*] Building production image (pnnl/graphaide:prod-${VERSION})...${NC}"
docker build \
    -t pnnl/graphaide:prod-${VERSION} \
    -t pnnl/graphaide:prod \
    -t pnnl/graphaide:latest \
    .
echo -e "${GREEN}✓ Production image built${NC}"
echo ""

# Build development image (skip if --prod-only)
if [[ "$PROD_ONLY_FLAG" != "--prod-only" ]]; then
    echo -e "${BLUE}[*] Building development image (pnnl/graphaide:dev-${VERSION})...${NC}"
    docker build \
        -f Dockerfile.dev \
        -t pnnl/graphaide:dev-${VERSION} \
        -t pnnl/graphaide:dev \
        .
    echo -e "${GREEN}✓ Development image built${NC}"
    echo ""
fi

# Display built images
echo -e "${BLUE}[*] Built images:${NC}"
docker images | grep pnnl/graphaide | head -5
echo ""

# Push to DockerHub if requested
if [[ "$PUSH_FLAG" == "push" || "$PUSH_FLAG" == "--push" ]]; then
    echo "=================================================="
    echo -e "${BLUE}PUSH MODE: Pushing to DockerHub${NC}"
    echo "=================================================="
    echo ""

    # Check DockerHub login
    echo -e "${BLUE}[*] Checking DockerHub authentication...${NC}"
    if ! docker info 2>&1 | grep -q "Username:"; then
        echo -e "${YELLOW}[!] Not logged in to DockerHub. Please login.${NC}"
        echo ""
        docker login
    fi
    echo -e "${GREEN}✓ DockerHub authentication confirmed${NC}"
    echo ""

    # Push production images
    echo -e "${BLUE}[*] Pushing production images to DockerHub...${NC}"
    echo "  - Pushing pnnl/graphaide:prod-${VERSION}..."
    docker push pnnl/graphaide:prod-${VERSION}
    echo -e "${GREEN}  ✓ Pushed${NC}"

    echo "  - Pushing pnnl/graphaide:prod..."
    docker push pnnl/graphaide:prod
    echo -e "${GREEN}  ✓ Pushed${NC}"

    echo "  - Pushing pnnl/graphaide:latest..."
    docker push pnnl/graphaide:latest
    echo -e "${GREEN}  ✓ Pushed${NC}"
    echo ""

    # Push development images (skip if --prod-only)
    if [[ "$PROD_ONLY_FLAG" != "--prod-only" ]]; then
        echo -e "${BLUE}[*] Pushing development images to DockerHub...${NC}"
        echo "  - Pushing pnnl/graphaide:dev-${VERSION}..."
        docker push pnnl/graphaide:dev-${VERSION}
        echo -e "${GREEN}  ✓ Pushed${NC}"

        echo "  - Pushing pnnl/graphaide:dev..."
        docker push pnnl/graphaide:dev
        echo -e "${GREEN}  ✓ Pushed${NC}"
        echo ""
    fi

    # Logout
    echo -e "${BLUE}[*] Logging out from DockerHub...${NC}"
    docker logout > /dev/null 2>&1
    echo -e "${GREEN}✓ Logged out${NC}"
    echo ""

    # Clean up old images if requested
    if [[ "$CLEAN_FLAG" == "--clean" ]]; then
        echo -e "${BLUE}[*] Cleaning up unused images...${NC}"
        docker image prune -f > /dev/null 2>&1
        echo -e "${GREEN}✓ Cleanup complete${NC}"
        echo ""
    fi

    # Final summary for push
    echo "=================================================="
    echo -e "${GREEN}Build and Push Complete!${NC}"
    echo "=================================================="
    echo ""
    echo "Successfully pushed to DockerHub:"
    echo "  - pnnl/graphaide:prod-${VERSION}"
    echo "  - pnnl/graphaide:prod"
    echo "  - pnnl/graphaide:latest"
    echo "  - pnnl/graphaide:dev-${VERSION}"
    echo "  - pnnl/graphaide:dev"
    echo ""
    echo "Available at: https://hub.docker.com/r/pnnl/graphaide"
    echo ""

else
    # Summary for build only
    echo "=================================================="
    echo -e "${GREEN}Build Complete!${NC}"
    echo "=================================================="
    echo ""
    echo "Production images:"
    echo "  - pnnl/graphaide:prod-${VERSION}"
    echo "  - pnnl/graphaide:prod"
    echo "  - pnnl/graphaide:latest"
    echo ""
    echo "Development images:"
    echo "  - pnnl/graphaide:dev-${VERSION}"
    echo "  - pnnl/graphaide:dev"
    echo ""
    echo "To push to DockerHub, run:"
    echo "  ./graphaide_docker_build.sh ${VERSION} push"
    echo ""
    echo "Or push manually:"
    echo "  docker login"
    echo "  docker push pnnl/graphaide:prod-${VERSION}"
    echo "  docker push pnnl/graphaide:prod"
    echo "  docker push pnnl/graphaide:latest"
    echo "  docker push pnnl/graphaide:dev-${VERSION}"
    echo "  docker push pnnl/graphaide:dev"
    echo "  docker logout"
    echo ""
fi
