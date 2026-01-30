#!/bin/bash
# ==============================================================================
# Ray Cluster Shutdown Script
# ==============================================================================
# Stops Ray on all nodes and cleans up
# ==============================================================================

echo "=============================================="
echo "  Shutting Down Ray Cluster"
echo "=============================================="
echo ""

VENV_DIR="${VENV_DIR:-${PW_PARENT_JOB_DIR}/ray_venv}"

# Activate virtual environment if available
if [ -f "${VENV_DIR}/bin/activate" ]; then
    source "${VENV_DIR}/bin/activate"
fi

# Stop Ray on current node
echo "Stopping Ray on $(hostname)..."
ray stop --force 2>/dev/null || true

# Clean up temporary Ray files
echo "Cleaning up temporary files..."
rm -rf /tmp/ray/* 2>/dev/null || true

# If we have node list information, stop on all nodes
if [ -n "${SLURM_JOB_NODELIST}" ]; then
    echo "Stopping Ray on all SLURM nodes..."
    NODELIST=$(scontrol show hostnames ${SLURM_JOB_NODELIST} 2>/dev/null)
    for node in ${NODELIST}; do
        echo "  Stopping on ${node}..."
        srun --nodes=1 --ntasks=1 -w ${node} \
            bash -c "ray stop --force 2>/dev/null; rm -rf /tmp/ray/* 2>/dev/null" || true
    done
elif [ -n "${PBS_NODEFILE}" ]; then
    echo "Stopping Ray on all PBS nodes..."
    NODELIST=$(cat ${PBS_NODEFILE} | sort -u)
    for node in ${NODELIST}; do
        echo "  Stopping on ${node}..."
        ssh ${node} "ray stop --force 2>/dev/null; rm -rf /tmp/ray/* 2>/dev/null" || true
    done
fi

echo ""
echo "=============================================="
echo "  Ray Cluster Shutdown Complete"
echo "=============================================="
