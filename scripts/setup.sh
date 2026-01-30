#!/bin/bash
# setup.sh - Ray Cluster Setup Script (runs on controller node)
#
# This script runs on the controller/login node in STEP 1 of the session_runner job.
# It runs BEFORE start.sh is submitted to the compute node.
#
# Use it to:
# - Install Ray using uv (fast) or pip (fallback)
# - Download dependencies that require internet access
# - Set up shared resources accessible by compute nodes
#
# Environment variables:
#   RAY_DIR        - Shared directory for Ray installation (default: ~/pw/activate-ray)
#   RAY_VERSION    - Ray version to install (default: 2.40.0)
#   DASHBOARD_PORT - Dashboard port (default: 8265)
#   RAY_PORT       - Ray GCS port (default: 6379)
#   NUM_CPUS       - CPUs per node (default: auto)
#   NUM_GPUS       - GPUs per node (default: auto)
#
# Coordinate files written here:
#   - SETUP_COMPLETE - Signals that setup completed successfully
#
# Note: Ray venv is installed in RAY_DIR to allow reuse across runs

set -e

[[ "${DEBUG:-}" == "true" ]] && set -x

echo "=========================================="
echo "Ray Cluster Setup (Controller Node)"
echo "=========================================="

# Normalize paths (remove trailing slash, expand ~)
JOB_DIR="${PW_PARENT_JOB_DIR%/}"
RAY_DIR="${RAY_DIR:-${HOME}/pw/activate-ray}"
RAY_DIR="${RAY_DIR/#\~/$HOME}"

echo "Job directory: ${JOB_DIR}"
echo "Ray directory: ${RAY_DIR}"
echo "Working directory: $(pwd)"

# Source inputs if available
if [ -f inputs.sh ]; then
  source inputs.sh
elif [ -f "${JOB_DIR}/inputs.sh" ]; then
  source "${JOB_DIR}/inputs.sh"
fi

# Configuration - venv lives in shared RAY_DIR for reuse
RAY_VERSION="${RAY_VERSION:-2.40.0}"
VENV_DIR="${RAY_DIR}/ray_venv"
DASHBOARD_PORT="${DASHBOARD_PORT:-8265}"
RAY_PORT="${RAY_PORT:-6379}"

echo "Configuration:"
echo "  Ray Version:    ${RAY_VERSION}"
echo "  Venv Directory: ${VENV_DIR}"
echo "  Dashboard Port: ${DASHBOARD_PORT}"
echo "  Ray Port:       ${RAY_PORT}"

# =============================================================================
# Check Python version compatibility
# =============================================================================
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 not found"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

echo "Python: $(python3 --version)"

# Ray 2.40.0 requires Python 3.9-3.12
if [ "$PYTHON_MAJOR" -ne 3 ] || [ "$PYTHON_MINOR" -lt 9 ] || [ "$PYTHON_MINOR" -gt 12 ]; then
    echo "ERROR: Ray ${RAY_VERSION} requires Python 3.9-3.12, found ${PYTHON_VERSION}"
    echo "Please use a compatible Python version or set PYTHON environment variable"
    exit 1
fi

# =============================================================================
# Install Ray using uv (fast) or pip (fallback)
# =============================================================================
install_uv() {
    if command -v uv &> /dev/null; then
        echo "uv is already installed: $(uv --version)"
        return 0
    fi
    echo "Installing uv package manager..."
    if command -v curl &> /dev/null; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
    elif command -v wget &> /dev/null; then
        wget -qO- https://astral.sh/uv/install.sh | sh
    else
        echo "WARNING: Cannot install uv (no curl/wget)"
        return 1
    fi
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    command -v uv &> /dev/null
}

# =============================================================================
# Check if Ray is already installed at correct version
# =============================================================================
INSTALLED_VERSION=""
if [ -f "${VENV_DIR}/bin/python" ]; then
    INSTALLED_VERSION=$("${VENV_DIR}/bin/python" -c "import ray; print(ray.__version__)" 2>/dev/null || echo "")
fi

if [ "${INSTALLED_VERSION}" == "${RAY_VERSION}" ]; then
    echo ""
    echo "Ray ${RAY_VERSION} already installed in ${VENV_DIR}"
    echo "Skipping installation."
else
    echo ""
    if [ -n "${INSTALLED_VERSION}" ]; then
        echo "Ray ${INSTALLED_VERSION} found, upgrading to ${RAY_VERSION}..."
    else
        echo "Installing Ray ${RAY_VERSION}..."
    fi

    if install_uv; then
        echo "Using uv for fast installation..."
        if [ ! -d "${VENV_DIR}" ]; then
            uv venv "${VENV_DIR}"
        fi
        uv pip install --python "${VENV_DIR}/bin/python" "ray[default]==${RAY_VERSION}"
    else
        echo "Using pip for installation..."
        if [ ! -d "${VENV_DIR}" ]; then
            python3 -m venv "${VENV_DIR}"
        fi
        source "${VENV_DIR}/bin/activate"
        pip install --upgrade pip --quiet
        pip install "ray[default]==${RAY_VERSION}" --quiet
    fi
fi

# Verify installation
source "${VENV_DIR}/bin/activate"
ray --version
python3 -c "import ray; print(f'Ray {ray.__version__} ready')"

# =============================================================================
# Write environment config for start.sh
# =============================================================================
cat > "${JOB_DIR}/ray_config.sh" << EOF
export RAY_DIR="${RAY_DIR}"
export VENV_DIR="${VENV_DIR}"
export RAY_VERSION="${RAY_VERSION}"
export RAY_PORT="${RAY_PORT}"
export DASHBOARD_PORT="${DASHBOARD_PORT}"
export NUM_CPUS="${NUM_CPUS:-}"
export NUM_GPUS="${NUM_GPUS:-}"
EOF

echo "Config written to: ${JOB_DIR}/ray_config.sh"

# =============================================================================
# Write setup complete marker
# =============================================================================
touch "${JOB_DIR}/SETUP_COMPLETE"

echo "=========================================="
echo "Setup complete!"
echo "=========================================="
echo "  Ray Version: ${RAY_VERSION}"
echo "  Venv: ${VENV_DIR}"
echo "  SETUP_COMPLETE: ${JOB_DIR}/SETUP_COMPLETE"
echo "=========================================="
