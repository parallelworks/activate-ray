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
#   RAY_VERSION    - Ray version to install (default: 2.40.0)
#   DASHBOARD_PORT - Dashboard port (default: 8265)
#   RAY_PORT       - Ray GCS port (default: 6379)
#   NUM_CPUS       - CPUs per node (default: auto)
#   NUM_GPUS       - GPUs per node (default: auto)
#
# Coordinate files written here:
#   - SETUP_COMPLETE - Signals that setup completed successfully

set -e

[[ "${DEBUG:-}" == "true" ]] && set -x

echo "=========================================="
echo "Ray Cluster Setup (Controller Node)"
echo "=========================================="

# Normalize job directory path (remove trailing slash if present)
JOB_DIR="${PW_PARENT_JOB_DIR%/}"
echo "Job directory: ${JOB_DIR}"
echo "Working directory: $(pwd)"

# Source inputs if available
if [ -f inputs.sh ]; then
  source inputs.sh
elif [ -f "${JOB_DIR}/inputs.sh" ]; then
  source "${JOB_DIR}/inputs.sh"
fi

# Configuration
RAY_VERSION="${RAY_VERSION:-2.40.0}"
VENV_DIR="${JOB_DIR}/ray_venv"
DASHBOARD_PORT="${DASHBOARD_PORT:-8265}"
RAY_PORT="${RAY_PORT:-6379}"

echo "Configuration:"
echo "  Ray Version:    ${RAY_VERSION}"
echo "  Venv Directory: ${VENV_DIR}"
echo "  Dashboard Port: ${DASHBOARD_PORT}"
echo "  Ray Port:       ${RAY_PORT}"

# =============================================================================
# Check Python
# =============================================================================
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 not found"
    exit 1
fi
echo "Python: $(python3 --version)"

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

echo ""
echo "Installing Ray ${RAY_VERSION}..."

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

# Verify installation
source "${VENV_DIR}/bin/activate"
ray --version
python3 -c "import ray; print(f'Ray {ray.__version__} ready')"

# =============================================================================
# Write environment config for start.sh
# =============================================================================
cat > "${JOB_DIR}/ray_config.sh" << EOF
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
