#!/bin/bash
# ==============================================================================
# Ray Environment Setup Script
# ==============================================================================
# Installs Ray using uv package manager (fast) or pip (fallback)
# ==============================================================================

set -e

echo "=============================================="
echo "  Setting up Ray Environment"
echo "=============================================="
echo ""

# Configuration from environment
RAY_VERSION="${RAY_VERSION:-2.9.0}"
VENV_DIR="${VENV_DIR:-${PW_PARENT_JOB_DIR}/ray_venv}"
EXTRA_PACKAGES="${EXTRA_PACKAGES:-}"
USE_UV="${USE_UV:-true}"

echo "Configuration:"
echo "  Ray Version:    ${RAY_VERSION}"
echo "  Venv Directory: ${VENV_DIR}"
echo "  Extra Packages: ${EXTRA_PACKAGES:-none}"
echo "  Use UV:         ${USE_UV}"
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 not found. Please ensure Python 3.7+ is available."
    exit 1
fi

PYTHON_VERSION=$(python3 --version)
echo "Python version: ${PYTHON_VERSION}"

# Function to install uv if not present
install_uv() {
    if command -v uv &> /dev/null; then
        echo "uv is already installed: $(uv --version)"
        return 0
    fi

    echo "Installing uv package manager..."

    # Try curl first, then wget
    if command -v curl &> /dev/null; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
    elif command -v wget &> /dev/null; then
        wget -qO- https://astral.sh/uv/install.sh | sh
    else
        echo "WARNING: Neither curl nor wget available, cannot install uv"
        return 1
    fi

    # Add to PATH for this session
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

    if command -v uv &> /dev/null; then
        echo "uv installed successfully: $(uv --version)"
        return 0
    else
        echo "WARNING: uv installation failed"
        return 1
    fi
}

# Function to setup with uv
setup_with_uv() {
    echo ""
    echo "Setting up environment with uv (fast mode)..."

    # Create virtual environment with uv
    if [ ! -d "${VENV_DIR}" ]; then
        echo "Creating virtual environment with uv..."
        uv venv "${VENV_DIR}"
    fi

    # Install Ray with uv
    echo ""
    echo "Installing Ray ${RAY_VERSION} with uv..."
    uv pip install --python "${VENV_DIR}/bin/python" "ray[default]==${RAY_VERSION}"

    # Install extra packages if specified
    if [ -n "${EXTRA_PACKAGES}" ]; then
        echo ""
        echo "Installing extra packages: ${EXTRA_PACKAGES}"
        uv pip install --python "${VENV_DIR}/bin/python" ${EXTRA_PACKAGES}
    fi

    # Install from requirements.txt if it exists
    if [ -f "${PW_PARENT_JOB_DIR}/requirements.txt" ]; then
        echo ""
        echo "Installing from requirements.txt..."
        uv pip install --python "${VENV_DIR}/bin/python" -r "${PW_PARENT_JOB_DIR}/requirements.txt"
    fi
}

# Function to setup with pip (fallback)
setup_with_pip() {
    echo ""
    echo "Setting up environment with pip (standard mode)..."

    # Create virtual environment
    if [ ! -d "${VENV_DIR}" ]; then
        echo "Creating virtual environment..."
        python3 -m venv "${VENV_DIR}"
    fi

    # Activate virtual environment
    source "${VENV_DIR}/bin/activate"

    # Upgrade pip
    echo ""
    echo "Upgrading pip..."
    pip install --upgrade pip --quiet

    # Install Ray
    echo ""
    echo "Installing Ray ${RAY_VERSION}..."
    pip install "ray[default]==${RAY_VERSION}" --quiet

    # Install extra packages if specified
    if [ -n "${EXTRA_PACKAGES}" ]; then
        echo ""
        echo "Installing extra packages: ${EXTRA_PACKAGES}"
        pip install ${EXTRA_PACKAGES} --quiet
    fi

    # Install from requirements.txt if it exists
    if [ -f "${PW_PARENT_JOB_DIR}/requirements.txt" ]; then
        echo ""
        echo "Installing from requirements.txt..."
        pip install -r "${PW_PARENT_JOB_DIR}/requirements.txt" --quiet
    fi
}

# Main installation logic
if [ "${USE_UV}" = "true" ] || [ "${USE_UV}" = "1" ]; then
    if install_uv; then
        setup_with_uv
    else
        echo "Falling back to pip..."
        setup_with_pip
    fi
else
    setup_with_pip
fi

# Activate environment for verification
source "${VENV_DIR}/bin/activate"

# Verify installation
echo ""
echo "Verifying Ray installation..."
ray --version
python3 -c "import ray; print(f'Ray {ray.__version__} installed successfully')"

echo ""
echo "=============================================="
echo "  Ray Environment Setup Complete"
echo "=============================================="
echo ""
echo "VENV_PATH=${VENV_DIR}"
