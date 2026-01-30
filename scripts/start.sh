#!/bin/bash
# start.sh - Ray Cluster Startup Script (runs on compute node)
#
# This script runs on the compute node in STEP 2 of the session_runner job.
# It is submitted via marketplace/job_runner/v4.0 (SLURM/PBS) or runs directly
# on the controller if no scheduler is configured.
#
# It uses resources prepared by setup.sh which runs in STEP 1 on the controller.
#
# Creates coordination files:
#   - HOSTNAME     - Target hostname for dashboard
#   - SESSION_PORT - Dashboard port
#   - job.started  - Signals job has started

set -e

[[ "${DEBUG:-}" == "true" ]] && set -x

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Normalize paths (remove trailing slash, expand ~)
JOB_DIR="${PW_PARENT_JOB_DIR%/}"
RAY_DIR="${RAY_DIR:-${HOME}/pw/activate-ray}"
RAY_DIR="${RAY_DIR/#\~/$HOME}"

echo "=========================================="
echo "Ray Cluster Starting (Compute Node)"
echo "=========================================="
echo "Script directory: ${SCRIPT_DIR}"
echo "Ray directory: ${RAY_DIR}"
echo "Job directory: ${JOB_DIR}"
echo "Working directory: $(pwd)"

# Ensure we're working from the job directory for coordination files
cd "${JOB_DIR}"

# Source inputs if available
if [ -f inputs.sh ]; then
  source inputs.sh
fi

# Source config from setup.sh
if [ -f "${JOB_DIR}/ray_config.sh" ]; then
  source "${JOB_DIR}/ray_config.sh"
  echo "Loaded ray_config.sh"
fi

# Verify setup completed successfully
if [ -f "${JOB_DIR}/SETUP_COMPLETE" ]; then
  echo "Setup phase completed successfully"
else
  echo "Warning: SETUP_COMPLETE marker not found in ${JOB_DIR}"
fi

# Configuration defaults - venv is in shared RAY_DIR
VENV_DIR="${VENV_DIR:-${RAY_DIR}/ray_venv}"
RAY_PORT="${RAY_PORT:-6379}"
DASHBOARD_PORT="${DASHBOARD_PORT:-8265}"
NUM_CPUS="${NUM_CPUS:-}"
NUM_GPUS="${NUM_GPUS:-}"

# Activate virtual environment
source "${VENV_DIR}/bin/activate"

# Build resource args
RESOURCE_ARGS=""
[ -n "${NUM_CPUS}" ] && [ "${NUM_CPUS}" != "0" ] && RESOURCE_ARGS="${RESOURCE_ARGS} --num-cpus=${NUM_CPUS}"
[ -n "${NUM_GPUS}" ] && [ "${NUM_GPUS}" != "0" ] && RESOURCE_ARGS="${RESOURCE_ARGS} --num-gpus=${NUM_GPUS}"

# =============================================================================
# Detect execution mode and get node information
# =============================================================================
if [ -n "${SLURM_JOB_NODELIST}" ]; then
    echo "Detected SLURM environment"
    NODELIST=$(scontrol show hostnames ${SLURM_JOB_NODELIST})
    HEAD_NODE=$(echo "${NODELIST}" | head -n 1)
    HEAD_NODE_IP=$(getent hosts ${HEAD_NODE} | awk '{ print $1 }' | head -n 1)
    [ -z "${HEAD_NODE_IP}" ] && HEAD_NODE_IP=${HEAD_NODE}
    NUM_NODES=${SLURM_JOB_NUM_NODES}

elif [ -n "${PBS_NODEFILE}" ]; then
    echo "Detected PBS environment"
    NODELIST=$(cat ${PBS_NODEFILE} | sort -u)
    HEAD_NODE=$(echo "${NODELIST}" | head -n 1)
    HEAD_NODE_IP=$(getent hosts ${HEAD_NODE} | awk '{ print $1 }' | head -n 1)
    [ -z "${HEAD_NODE_IP}" ] && HEAD_NODE_IP=${HEAD_NODE}
    NUM_NODES=$(echo "${NODELIST}" | wc -l)

else
    echo "Running in SSH direct mode (single node)"
    HEAD_NODE=$(hostname)
    HEAD_NODE_IP=$(hostname -i 2>/dev/null | awk '{print $1}' || echo "127.0.0.1")
    NODELIST=${HEAD_NODE}
    NUM_NODES=1
fi

echo "=============================================="
echo "  Starting Ray Cluster"
echo "=============================================="
echo "Head Node:    ${HEAD_NODE}"
echo "Head Node IP: ${HEAD_NODE_IP}"
echo "Total Nodes:  ${NUM_NODES}"
echo ""

# =============================================================================
# Write coordination files BEFORE starting Ray
# =============================================================================
echo "${HEAD_NODE_IP}" > HOSTNAME
echo "${DASHBOARD_PORT}" > SESSION_PORT
touch job.started

echo "Coordination files written:"
echo "  - HOSTNAME: $(cat HOSTNAME)"
echo "  - SESSION_PORT: $(cat SESSION_PORT)"

# =============================================================================
# Stop any existing Ray processes
# =============================================================================
ray stop --force 2>/dev/null || true

# =============================================================================
# Start Ray cluster
# =============================================================================
if [[ "$(hostname)" == "${HEAD_NODE}"* ]] || [[ "$(hostname -s)" == "${HEAD_NODE}"* ]]; then
    echo "Starting Ray HEAD on $(hostname)..."
    ray start --head \
        --port=${RAY_PORT} \
        --dashboard-host=0.0.0.0 \
        --dashboard-port=${DASHBOARD_PORT} \
        ${RESOURCE_ARGS}

    sleep 5

    # Start workers on other nodes if multi-node
    if [ ${NUM_NODES} -gt 1 ]; then
        WORKER_NODES=$(echo "${NODELIST}" | tail -n +2)
        for node in ${WORKER_NODES}; do
            echo "Starting Ray WORKER on ${node}..."
            if [ -n "${SLURM_JOB_ID}" ]; then
                srun --nodes=1 --ntasks=1 -w ${node} \
                    bash -c "source ${VENV_DIR}/bin/activate && ray stop --force 2>/dev/null; ray start --address=${HEAD_NODE_IP}:${RAY_PORT} ${RESOURCE_ARGS}" &
            else
                ssh ${node} "source ${VENV_DIR}/bin/activate && ray stop --force 2>/dev/null; ray start --address=${HEAD_NODE_IP}:${RAY_PORT} ${RESOURCE_ARGS}" &
            fi
        done
        wait
    fi

    sleep 5
    echo ""
    echo "Cluster Status:"
    ray status || true

else
    echo "This node ($(hostname)) is a worker, waiting for head..."
    sleep 10
    echo "Starting Ray WORKER on $(hostname)..."
    ray start --address=${HEAD_NODE_IP}:${RAY_PORT} ${RESOURCE_ARGS}
fi

echo ""
echo "=============================================="
echo "  Ray Cluster Ready"
echo "=============================================="
echo "Dashboard: http://${HEAD_NODE_IP}:${DASHBOARD_PORT}"
echo "Ray Address: ray://${HEAD_NODE_IP}:10001"
echo "=============================================="

# =============================================================================
# Keep the script alive while Ray runs
# =============================================================================
echo ""
echo "Cluster running. Cancel workflow to shut down."

while true; do
    sleep 60
    ray status 2>/dev/null || echo "Health check: $(date)"
done
