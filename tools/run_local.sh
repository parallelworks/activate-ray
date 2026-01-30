#!/bin/bash
# =============================================================================
# Local Ray Workflow Runner
# =============================================================================
# Run the Ray cluster workflow locally for testing without the ACTIVATE platform.
#
# Usage:
#   ./tools/run_local.sh                    # Run with defaults (starts Ray cluster)
#   ./tools/run_local.sh --dry-run          # Show what would execute
#   ./tools/run_local.sh -v                 # Verbose output
#   ./tools/run_local.sh --keep-work-dir    # Keep temp files for inspection
#
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
WORKFLOW="${REPO_ROOT}/workflow.yaml"
RUNNER="${SCRIPT_DIR}/workflow_runner.py"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${GREEN}=============================================="
echo "  Ray Cluster Workflow - Local Runner"
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

# Function to run python
run_python() {
    if [ "$USE_UV" = true ]; then
        uv run python3 "$@"
    else
        python3 "$@"
    fi
}

# Check for PyYAML (install if using uv)
if [ "$USE_UV" = true ]; then
    # uv will handle dependencies via pyproject.toml
    :
elif ! python3 -c "import yaml" 2>/dev/null; then
    echo -e "${YELLOW}Installing PyYAML...${NC}"
    pip3 install pyyaml --quiet
fi

# Check for Ray (optional for local testing)
if ! run_python -c "import ray" 2>/dev/null; then
    echo -e "${YELLOW}Note: Ray is not installed locally.${NC}"
    echo -e "${YELLOW}The workflow will install Ray in the working directory.${NC}"
    if [ "$USE_UV" = true ]; then
        echo -e "${YELLOW}To install Ray: uv sync --extra ray${NC}"
    fi
    echo ""
fi

# Check workflow exists
if [ ! -f "${WORKFLOW}" ]; then
    echo -e "${RED}Error: workflow.yaml not found at ${WORKFLOW}${NC}"
    exit 1
fi

# Run the workflow
echo -e "${CYAN}Running: python3 ${RUNNER} ${WORKFLOW} $@${NC}"
echo ""

run_python "${RUNNER}" "${WORKFLOW}" "$@"
exit_code=$?

echo ""
if [ $exit_code -eq 0 ]; then
    echo -e "${GREEN}Workflow completed successfully!${NC}"
else
    echo -e "${RED}Workflow failed with exit code ${exit_code}${NC}"
fi

exit $exit_code
