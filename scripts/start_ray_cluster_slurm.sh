#!/bin/bash
# ==============================================================================
# Ray Cluster Startup Script for SLURM
# ==============================================================================
# Starts a Ray cluster across SLURM-allocated nodes.
# - First node becomes the head node
# - Remaining nodes become worker nodes
# ==============================================================================

set -e

echo "=============================================="
echo "  Starting Ray Cluster on SLURM"
echo "=============================================="
echo ""

# Configuration from environment
VENV_DIR="${VENV_DIR:-${PW_PARENT_JOB_DIR}/ray_venv}"
RAY_PORT="${RAY_PORT:-6379}"
DASHBOARD_PORT="${DASHBOARD_PORT:-8265}"
NUM_CPUS="${NUM_CPUS:-}"
NUM_GPUS="${NUM_GPUS:-}"
RAY_MEMORY="${RAY_MEMORY:-}"

# Activate virtual environment
if [ -f "${VENV_DIR}/bin/activate" ]; then
    source "${VENV_DIR}/bin/activate"
else
    echo "WARNING: Virtual environment not found at ${VENV_DIR}"
fi

# Get SLURM node information
if [ -z "${SLURM_JOB_NODELIST}" ]; then
    echo "ERROR: SLURM_JOB_NODELIST not set. This script must run within a SLURM job."
    exit 1
fi

echo "SLURM Job Information:"
echo "  Job ID:    ${SLURM_JOB_ID}"
echo "  Node List: ${SLURM_JOB_NODELIST}"
echo "  Num Nodes: ${SLURM_JOB_NUM_NODES}"
echo ""

# Expand node list to individual hostnames
NODELIST=$(scontrol show hostnames ${SLURM_JOB_NODELIST})
HEAD_NODE=$(echo "${NODELIST}" | head -n 1)
HEAD_NODE_IP=$(getent hosts ${HEAD_NODE} | awk '{ print $1 }' | head -n 1)

# If getent fails, try hostname -i
if [ -z "${HEAD_NODE_IP}" ]; then
    HEAD_NODE_IP=$(ssh ${HEAD_NODE} "hostname -i" 2>/dev/null | awk '{print $1}')
fi

# Fallback to the hostname itself
if [ -z "${HEAD_NODE_IP}" ]; then
    HEAD_NODE_IP=${HEAD_NODE}
fi

echo "Cluster Configuration:"
echo "  Head Node:     ${HEAD_NODE}"
echo "  Head Node IP:  ${HEAD_NODE_IP}"
echo "  Total Nodes:   $(echo "${NODELIST}" | wc -l)"
echo ""

# Build resource arguments
RESOURCE_ARGS=""
if [ -n "${NUM_CPUS}" ]; then
    RESOURCE_ARGS="${RESOURCE_ARGS} --num-cpus=${NUM_CPUS}"
fi
if [ -n "${NUM_GPUS}" ]; then
    RESOURCE_ARGS="${RESOURCE_ARGS} --num-gpus=${NUM_GPUS}"
fi
if [ -n "${RAY_MEMORY}" ]; then
    RESOURCE_ARGS="${RESOURCE_ARGS} --memory=${RAY_MEMORY}"
fi

# Start Ray head on first node
echo "Starting Ray head node on ${HEAD_NODE}..."
srun --nodes=1 --ntasks=1 -w ${HEAD_NODE} \
    bash -c "source ${VENV_DIR}/bin/activate && ray stop --force 2>/dev/null; ray start --head --port=${RAY_PORT} --dashboard-host=0.0.0.0 --dashboard-port=${DASHBOARD_PORT} ${RESOURCE_ARGS}" &

# Wait for head node to start
echo "Waiting for head node to initialize..."
sleep 10

# Start Ray workers on remaining nodes
WORKER_NODES=$(echo "${NODELIST}" | tail -n +2)
if [ -n "${WORKER_NODES}" ]; then
    echo ""
    echo "Starting Ray workers on remaining nodes..."
    for node in ${WORKER_NODES}; do
        echo "  Starting worker on ${node}..."
        srun --nodes=1 --ntasks=1 -w ${node} \
            bash -c "source ${VENV_DIR}/bin/activate && ray stop --force 2>/dev/null; ray start --address=${HEAD_NODE_IP}:${RAY_PORT} ${RESOURCE_ARGS}" &
    done
fi

# Wait for workers to connect
echo ""
echo "Waiting for workers to connect..."
sleep 10

# Verify cluster status
echo ""
echo "Verifying cluster status..."
srun --nodes=1 --ntasks=1 -w ${HEAD_NODE} \
    bash -c "source ${VENV_DIR}/bin/activate && ray status" || true

# Write connection info
CONNECTION_FILE="${PW_PARENT_JOB_DIR}/ray_connection_info.txt"
cat > "${CONNECTION_FILE}" << EOF
RAY_HEAD_IP=${HEAD_NODE_IP}
RAY_HEAD_HOSTNAME=${HEAD_NODE}
RAY_ADDRESS=ray://${HEAD_NODE_IP}:10001
RAY_HEAD_ADDRESS=${HEAD_NODE_IP}:${RAY_PORT}
DASHBOARD_URL=http://${HEAD_NODE_IP}:${DASHBOARD_PORT}
SLURM_JOB_ID=${SLURM_JOB_ID}
NUM_NODES=${SLURM_JOB_NUM_NODES}
EOF

echo ""
echo "=============================================="
echo "  Ray Cluster Started Successfully"
echo "=============================================="
echo ""
cat "${CONNECTION_FILE}"
echo ""
echo "=============================================="

# Keep the job running to maintain the cluster
echo ""
echo "Ray cluster is running. Press Ctrl+C or cancel the job to shut down."
echo "Cluster will remain active until the SLURM job ends."
echo ""

# Wait indefinitely (or until job is cancelled)
while true; do
    sleep 60
    # Periodic health check
    srun --nodes=1 --ntasks=1 -w ${HEAD_NODE} \
        bash -c "source ${VENV_DIR}/bin/activate && ray status" 2>/dev/null || {
        echo "WARNING: Ray cluster health check failed"
    }
done
