#!/bin/bash
# ==============================================================================
# Ray Job Submission Script
# ==============================================================================
# Submits a job to a running Ray cluster
# ==============================================================================

set -e

echo "=============================================="
echo "  Submitting Ray Job"
echo "=============================================="
echo ""

# Configuration from environment
VENV_DIR="${VENV_DIR:-${PW_PARENT_JOB_DIR}/ray_venv}"
RAY_ADDRESS="${RAY_ADDRESS:-}"
JOB_SCRIPT="${JOB_SCRIPT:-}"
WORKING_DIR="${WORKING_DIR:-${PW_PARENT_JOB_DIR}}"
ENTRYPOINT="${ENTRYPOINT:-}"

# Try to load connection info if RAY_ADDRESS not set
if [ -z "${RAY_ADDRESS}" ]; then
    CONNECTION_FILE="${PW_PARENT_JOB_DIR}/ray_connection_info.txt"
    if [ -f "${CONNECTION_FILE}" ]; then
        source "${CONNECTION_FILE}"
        echo "Loaded connection info from ${CONNECTION_FILE}"
    fi
fi

# Validate required parameters
if [ -z "${RAY_ADDRESS}" ]; then
    echo "ERROR: RAY_ADDRESS is required"
    echo "Set RAY_ADDRESS environment variable or ensure ray_connection_info.txt exists"
    exit 1
fi

# Activate virtual environment
if [ -f "${VENV_DIR}/bin/activate" ]; then
    source "${VENV_DIR}/bin/activate"
fi

echo "Configuration:"
echo "  Ray Address:   ${RAY_ADDRESS}"
echo "  Working Dir:   ${WORKING_DIR}"
echo "  Job Script:    ${JOB_SCRIPT:-<inline>}"
echo "  Entrypoint:    ${ENTRYPOINT:-python ${JOB_SCRIPT}}"
echo ""

# Convert ray:// to http:// for job submission API
JOB_ADDRESS="${RAY_ADDRESS}"
if [[ "${RAY_ADDRESS}" == ray://* ]]; then
    # Extract host from ray://host:port and use dashboard port
    RAY_HOST=$(echo "${RAY_ADDRESS}" | sed 's|ray://||' | cut -d: -f1)
    JOB_ADDRESS="http://${RAY_HOST}:8265"
fi

# Submit the job
if [ -n "${ENTRYPOINT}" ]; then
    echo "Submitting job with custom entrypoint..."
    ray job submit \
        --address="${JOB_ADDRESS}" \
        --working-dir="${WORKING_DIR}" \
        -- ${ENTRYPOINT}
elif [ -n "${JOB_SCRIPT}" ]; then
    echo "Submitting job script: ${JOB_SCRIPT}..."
    ray job submit \
        --address="${JOB_ADDRESS}" \
        --working-dir="${WORKING_DIR}" \
        -- python "${JOB_SCRIPT}"
else
    echo "ERROR: Either JOB_SCRIPT or ENTRYPOINT must be specified"
    exit 1
fi

echo ""
echo "=============================================="
echo "  Job Submitted Successfully"
echo "=============================================="
