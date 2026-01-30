#!/bin/bash
# =============================================================================
# Test Runner for Ray Cluster Workflow
# =============================================================================
# Run unit and integration tests for the workflow.
#
# Usage:
#   ./tools/run_tests.sh              # Run all tests
#   ./tools/run_tests.sh -v           # Verbose output
#   ./tools/run_tests.sh --unit       # Unit tests only
#   ./tools/run_tests.sh --integration # Integration tests only
#   ./tools/run_tests.sh --coverage   # With coverage report
#
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${GREEN}=============================================="
echo "  Ray Cluster Workflow - Test Runner"
echo -e "==============================================${NC}"
echo ""

# Check for uv or python3
USE_UV=false
if command -v uv &> /dev/null; then
    USE_UV=true
    echo -e "${CYAN}Using uv for package management${NC}"
elif ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Neither uv nor Python 3 found${NC}"
    echo "Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Function to run python/pytest
run_pytest() {
    if [ "$USE_UV" = true ]; then
        uv run pytest "$@"
    else
        python3 -m pytest "$@"
    fi
}

# Check/install dependencies (only needed if not using uv)
if [ "$USE_UV" = false ]; then
    echo "Checking dependencies..."
    if ! python3 -c "import yaml" 2>/dev/null; then
        echo -e "${YELLOW}Installing PyYAML...${NC}"
        pip3 install pyyaml --quiet
    fi

    if ! python3 -c "import pytest" 2>/dev/null; then
        echo -e "${YELLOW}Installing pytest...${NC}"
        pip3 install pytest pytest-cov --quiet
    fi
fi

# Parse arguments
PYTEST_ARGS="-v"
TEST_PATH="${REPO_ROOT}/tests"

while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            PYTEST_ARGS="-vv"
            shift
            ;;
        --unit)
            TEST_PATH="${REPO_ROOT}/tests/test_workflow_runner.py"
            shift
            ;;
        --integration)
            TEST_PATH="${REPO_ROOT}/tests/test_integration.py"
            shift
            ;;
        --coverage)
            PYTEST_ARGS="${PYTEST_ARGS} --cov=${REPO_ROOT}/tools --cov-report=term-missing"
            shift
            ;;
        -k)
            PYTEST_ARGS="${PYTEST_ARGS} -k $2"
            shift 2
            ;;
        *)
            PYTEST_ARGS="${PYTEST_ARGS} $1"
            shift
            ;;
    esac
done

# Run tests
echo ""
echo "Running: pytest ${TEST_PATH} ${PYTEST_ARGS}"
echo ""

cd "${REPO_ROOT}"
run_pytest "${TEST_PATH}" ${PYTEST_ARGS}
exit_code=$?

echo ""
if [ $exit_code -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
else
    echo -e "${RED}Some tests failed.${NC}"
fi

exit $exit_code
