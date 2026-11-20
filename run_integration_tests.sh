#!/bin/bash
# Quick script to run GraphAide integration tests
# Usage: ./run_integration_tests.sh [options]

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  GraphAide Integration Test Suite          ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"
echo ""

# Activate virtual environment if it exists
VENV_PATH="./uvpylatest"
if [ -d "$VENV_PATH" ]; then
    echo -e "${BLUE}Activating venv: $VENV_PATH${NC}"
    source "$VENV_PATH/bin/activate" 2>/dev/null || source "$VENV_PATH/Scripts/activate" 2>/dev/null || true
fi

# Check if pytest is installed, install with uv if not
if ! command -v pytest &> /dev/null; then
    echo -e "${YELLOW}⚠ pytest not found. Installing with uv...${NC}"
    uv pip install pytest pytest-timeout
fi

# Parse arguments
RUN_TYPE=${1:-"all"}
TIMEOUT=${2:-"300"}  # 5 minutes per test by default

case $RUN_TYPE in
    "all")
        echo -e "${GREEN}Running all integration tests (timeout: ${TIMEOUT}s per test)${NC}"
        pytest tests/integration/ -v --timeout=$TIMEOUT --tb=short
        ;;
    "quick")
        echo -e "${GREEN}Running quick tests (no slow tests)${NC}"
        pytest tests/integration/ -v -m "not slow" --timeout=$TIMEOUT --tb=short
        ;;
    "slow")
        echo -e "${GREEN}Running only slow tests${NC}"
        pytest tests/integration/ -v -m slow --timeout=$TIMEOUT --tb=short
        ;;
    "vector")
        echo -e "${GREEN}Running vector store tests${NC}"
        pytest tests/integration/test_graphaide_features.py::test_1_ingest_vectors_to_store -v --timeout=$TIMEOUT --tb=short
        pytest tests/integration/test_graphaide_features.py::test_2_get_vector_store_doc_count -v --timeout=$TIMEOUT --tb=short
        ;;
    "extract")
        echo -e "${GREEN}Running extraction tests${NC}"
        pytest tests/integration/test_graphaide_features.py::test_3_extract_without_merge -v --timeout=$TIMEOUT --tb=short
        pytest tests/integration/test_graphaide_features.py::test_4_extract_with_merge -v --timeout=$TIMEOUT --tb=short
        ;;
    "ingest")
        echo -e "${GREEN}Running ingest tests${NC}"
        pytest tests/integration/test_graphaide_features.py::test_5_ingest_file_to_neo4j -v --timeout=$TIMEOUT --tb=short
        pytest tests/integration/test_graphaide_features.py::test_6_ingest_jsonl_with_abstract -v --timeout=$TIMEOUT --tb=short
        ;;
    "query")
        echo -e "${GREEN}Running query test${NC}"
        pytest tests/integration/test_graphaide_features.py::test_7_query_graphaide -v --timeout=$TIMEOUT --tb=short
        ;;
    "perf")
        echo -e "${GREEN}Running performance benchmarks${NC}"
        pytest tests/integration/ -v -k "performance" --timeout=$TIMEOUT --tb=short
        ;;
    *)
        echo -e "${YELLOW}Unknown run type: $RUN_TYPE${NC}"
        echo ""
        echo "Usage: ./run_integration_tests.sh [type] [timeout]"
        echo ""
        echo "Types:"
        echo "  all       - Run all integration tests (default)"
        echo "  quick     - Run fast tests only (no slow tests)"
        echo "  slow      - Run slow tests only"
        echo "  vector    - Run vector store tests (1-2)"
        echo "  extract   - Run extraction tests (3-4)"
        echo "  ingest    - Run ingest tests (5-6)"
        echo "  query     - Run query test (7)"
        echo "  perf      - Run performance benchmarks"
        echo ""
        echo "Timeout: Seconds per test (default: 300)"
        echo ""
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}✓ Test run complete${NC}"
