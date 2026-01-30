#!/bin/bash
# ==============================================================================
# Ray Head Node Startup Script
# ==============================================================================
# Starts the Ray head node (works for SSH direct mode and as the head in
# multi-node SLURM/PBS deployments)
# ==============================================================================

set -e

echo "=============================================="
echo "  Starting Ray Head Node"
echo "=============================================="
echo ""

# Configuration from environment
VENV_DIR="${VENV_DIR:-${PW_PARENT_JOB_DIR}/ray_venv}"
RAY_PORT="${RAY_PORT:-6379}"
DASHBOARD_PORT="${DASHBOARD_PORT:-8265}"
NUM_CPUS="${NUM_CPUS:-}"
NUM_GPUS="${NUM_GPUS:-}"
RAY_MEMORY="${RAY_MEMORY:-}"
OBJECT_STORE_MEMORY="${OBJECT_STORE_MEMORY:-}"

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
RAY_CMD="ray start --head"
RAY_CMD="${RAY_CMD} --port=${RAY_PORT}"
RAY_CMD="${RAY_CMD} --dashboard-host=0.0.0.0"
RAY_CMD="${RAY_CMD} --dashboard-port=${DASHBOARD_PORT}"

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

echo "Starting Ray head node..."
echo "Command: ${RAY_CMD}"
echo ""

# Start Ray head
${RAY_CMD}

# Get connection information
HEAD_IP=$(hostname -i 2>/dev/null || hostname)
HEAD_HOSTNAME=$(hostname)

echo ""
echo "=============================================="
echo "  Ray Head Node Started Successfully"
echo "=============================================="
echo ""
echo "Head Node Information:"
echo "  Hostname:       ${HEAD_HOSTNAME}"
echo "  IP Address:     ${HEAD_IP}"
echo "  Ray Port:       ${RAY_PORT}"
echo "  Dashboard Port: ${DASHBOARD_PORT}"
echo ""

# Write connection info to file
CONNECTION_FILE="${PW_PARENT_JOB_DIR}/ray_connection_info.txt"
cat > "${CONNECTION_FILE}" << EOF
RAY_HEAD_IP=${HEAD_IP}
RAY_HEAD_HOSTNAME=${HEAD_HOSTNAME}
RAY_ADDRESS=ray://${HEAD_IP}:10001
RAY_HEAD_ADDRESS=${HEAD_IP}:${RAY_PORT}
DASHBOARD_URL=http://${HEAD_IP}:${DASHBOARD_PORT}
EOF

echo "Connection info saved to: ${CONNECTION_FILE}"
cat "${CONNECTION_FILE}"
