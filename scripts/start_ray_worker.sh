#!/bin/bash
# ==============================================================================
# Ray Worker Node Startup Script
# ==============================================================================
# Starts a Ray worker node and connects it to the head node
# ==============================================================================

set -e

echo "=============================================="
echo "  Starting Ray Worker Node"
echo "=============================================="
echo ""

# Configuration from environment
VENV_DIR="${VENV_DIR:-${PW_PARENT_JOB_DIR}/ray_venv}"
RAY_HEAD_ADDRESS="${RAY_HEAD_ADDRESS}"
NUM_CPUS="${NUM_CPUS:-}"
NUM_GPUS="${NUM_GPUS:-}"
RAY_MEMORY="${RAY_MEMORY:-}"
OBJECT_STORE_MEMORY="${OBJECT_STORE_MEMORY:-}"

# Validate required parameters
if [ -z "${RAY_HEAD_ADDRESS}" ]; then
    echo "ERROR: RAY_HEAD_ADDRESS is required"
    exit 1
fi

echo "Configuration:"
echo "  Head Address: ${RAY_HEAD_ADDRESS}"
echo "  Worker Host:  $(hostname)"
echo ""

# Activate virtual environment
if [ -f "${VENV_DIR}/bin/activate" ]; then
    source "${VENV_DIR}/bin/activate"
else
    echo "WARNING: Virtual environment not found at ${VENV_DIR}"
    echo "Assuming Ray is available in system PATH"
fi

# Stop any existing Ray processes
echo "Stopping any existing Ray processes..."
ray stop --force 2>/dev/null || true

# Build ray start command
RAY_CMD="ray start --address=${RAY_HEAD_ADDRESS}"

# Add optional resource limits
if [ -n "${NUM_CPUS}" ]; then
    RAY_CMD="${RAY_CMD} --num-cpus=${NUM_CPUS}"
fi

if [ -n "${NUM_GPUS}" ]; then
    RAY_CMD="${RAY_CMD} --num-gpus=${NUM_GPUS}"
fi

if [ -n "${RAY_MEMORY}" ]; then
    RAY_CMD="${RAY_CMD} --memory=${RAY_MEMORY}"
fi

if [ -n "${OBJECT_STORE_MEMORY}" ]; then
    RAY_CMD="${RAY_CMD} --object-store-memory=${OBJECT_STORE_MEMORY}"
fi

echo "Starting Ray worker node..."
echo "Command: ${RAY_CMD}"
echo ""

# Start Ray worker
${RAY_CMD}

echo ""
echo "=============================================="
echo "  Ray Worker Node Started Successfully"
echo "=============================================="
echo ""
echo "Worker Node: $(hostname)"
echo "Connected to: ${RAY_HEAD_ADDRESS}"
