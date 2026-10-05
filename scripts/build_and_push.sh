#!/bin/bash

# Build and push GraphAide to PyPI
# Usage: ./build_and_push.sh <version> [testpypi|pypi]
# Example: ./build_and_push.sh 0.4.32 testpypi
# Example: ./build_and_push.sh 0.4.32 pypi

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check arguments
if [ $# -lt 1 ]; then
    echo -e "${RED}Usage: $0 <version> [testpypi|pypi]${NC}"
    echo "  version: e.g., 0.4.32"
    echo "  target:  testpypi (default) or pypi"
    exit 1
fi

VERSION=$1
TARGET=${2:-testpypi}

# Validate target
if [ "$TARGET" != "testpypi" ] && [ "$TARGET" != "pypi" ]; then
    echo -e "${RED}Error: target must be 'testpypi' or 'pypi'${NC}"
    exit 1
fi

# Set PyPI URL
if [ "$TARGET" = "testpypi" ]; then
    REPO_URL="https://test.pypi.org/legacy/"
    REPO_FLAG="testpypi"
else
    REPO_URL="https://upload.pypi.org/legacy/"
    REPO_FLAG="pypi"
fi

echo -e "${YELLOW}================================${NC}"
echo -e "${YELLOW}GraphAide Build & Push${NC}"
echo -e "${YELLOW}================================${NC}"
echo "Version: $VERSION"
echo "Target:  $TARGET ($REPO_URL)"
echo

# Check if tag already exists
if git rev-parse "v$VERSION" >/dev/null 2>&1; then
    echo -e "${YELLOW}Tag v$VERSION already exists, skipping tag creation${NC}"
    TAG_EXISTS=1
else
    TAG_EXISTS=0
fi

# Check git status (only tracked files, ignore untracked)
echo -e "${YELLOW}[1/5] Checking git status...${NC}"
if ! git diff --quiet || ! git diff --quiet --staged; then
    echo -e "${RED}Error: Uncommitted changes to tracked files detected${NC}"
    git status
    exit 1
fi
echo -e "${GREEN}OK - no uncommitted changes${NC}"
echo

# Create tag (if not already exists)
echo -e "${YELLOW}[2/5] Git tag v$VERSION...${NC}"
if [ $TAG_EXISTS -eq 0 ]; then
    git tag "v$VERSION"
    git push origin "v$VERSION"
    echo -e "${GREEN}OK - tag created and pushed${NC}"
else
    echo -e "${GREEN}OK - tag already exists (skipped creation)${NC}"
fi
echo

# Clean and build (force setuptools_scm recalculation)
echo -e "${YELLOW}[3/5] Building wheel...${NC}"
rm -rf build dist src/graphgen.egg-info .git/index.lock
# Force setuptools_scm to refresh by using --no-cache
python -m build --wheel 2>&1 | grep -E "(Successfully|ERROR)" || true

# Find the actual wheel file (setuptools_scm might use a different version)
WHEEL_FILE=$(ls dist/graphaide-*.whl 2>/dev/null | head -1)
if [ ! -f "$WHEEL_FILE" ]; then
    echo -e "${RED}Error: No wheel file found in dist/${NC}"
    exit 1
fi
ACTUAL_VERSION=$(basename "$WHEEL_FILE" | sed 's/graphaide-\(.*\)-py3.*/\1/')
echo -e "${GREEN}OK - wheel built: $WHEEL_FILE (version: $ACTUAL_VERSION)${NC}"
echo

# Verify templates
echo -e "${YELLOW}[4/5] Verifying templates in wheel...${NC}"
TEMPLATE_COUNT=$(unzip -l "$WHEEL_FILE" | grep -i template | wc -l)
if [ "$TEMPLATE_COUNT" -eq 0 ]; then
    echo -e "${RED}Error: No templates found in wheel${NC}"
    exit 1
fi
echo -e "${GREEN}OK - found $TEMPLATE_COUNT template files${NC}"
echo

# Upload
echo -e "${YELLOW}[5/5] Uploading to $TARGET...${NC}"
python -m twine upload --repository "$REPO_FLAG" "$WHEEL_FILE" 2>&1 | tail -20

echo
echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}SUCCESS${NC}"
echo -e "${GREEN}================================${NC}"
echo "Version: v$VERSION"
echo "Target:  $TARGET"
if [ "$TARGET" = "testpypi" ]; then
    echo "URL:     https://test.pypi.org/project/graphaide/$VERSION/"
else
    echo "URL:     https://pypi.org/project/graphaide/$VERSION/"
fi
echo
