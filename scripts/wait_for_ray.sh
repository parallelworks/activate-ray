#!/bin/bash
# wait_for_ray.sh - Wait for Ray dashboard to become available
# Usage: bash scripts/wait_for_ray.sh
#
# Reads connection info from: ${PW_PARENT_JOB_DIR}/ray_connection_info.txt
# Waits for the dashboard port to respond
#
# Outputs (written to $OUTPUTS if set):
#   HOSTNAME - Dashboard host IP/hostname
#   SESSION_PORT - Dashboard port
#
# Environment variables:
#   WAIT_TIMEOUT - curl timeout in seconds (default: 5)
#   WAIT_INTERVAL - seconds between retries (default: 3)
#   MAX_ATTEMPTS - max number of attempts (default: 100)

set -e

# Configuration
TIMEOUT=${WAIT_TIMEOUT:-5}
INTERVAL=${WAIT_INTERVAL:-3}
MAX_ATTEMPTS=${MAX_ATTEMPTS:-100}

JOB_DIR="${PW_PARENT_JOB_DIR%/}"
CONNECTION_FILE="${JOB_DIR}/ray_connection_info.txt"

echo "=========================================="
echo "  Waiting for Ray Dashboard"
echo "=========================================="

# Wait for connection info file
echo "Waiting for connection info..."
attempt=1
while [ ! -f "${CONNECTION_FILE}" ]; do
    if [ ${attempt} -ge ${MAX_ATTEMPTS} ]; then
        echo "ERROR: Connection info not found after ${MAX_ATTEMPTS} attempts"
        exit 1
    fi
    echo "  [${attempt}/${MAX_ATTEMPTS}] Waiting for ${CONNECTION_FILE}..."
    sleep "${INTERVAL}"
    ((attempt++))
done

# Read connection info
source "${CONNECTION_FILE}"
DASHBOARD_HOST="${RAY_HEAD_IP:-localhost}"
DASHBOARD_PORT="${DASHBOARD_PORT:-8265}"

echo "Dashboard target: http://${DASHBOARD_HOST}:${DASHBOARD_PORT}"

# Wait for dashboard to respond
echo "Waiting for dashboard to respond..."
attempt=1
while [ ${attempt} -le ${MAX_ATTEMPTS} ]; do
    if curl -s --connect-timeout "${TIMEOUT}" --max-time "${TIMEOUT}" \
        "http://${DASHBOARD_HOST}:${DASHBOARD_PORT}" -o /dev/null 2>&1; then
        echo ""
        echo "=========================================="
        echo "  Ray Dashboard is ready!"
        echo "=========================================="
        echo "  URL: http://${DASHBOARD_HOST}:${DASHBOARD_PORT}"
        echo "=========================================="

        # Write to OUTPUTS if available
        if [ -n "${OUTPUTS:-}" ]; then
            echo "HOSTNAME=${DASHBOARD_HOST}" >> "${OUTPUTS}"
            echo "SESSION_PORT=${DASHBOARD_PORT}" >> "${OUTPUTS}"
        fi

        exit 0
    fi

    echo "  [${attempt}/${MAX_ATTEMPTS}] Dashboard not ready, retrying in ${INTERVAL}s..."
    sleep "${INTERVAL}"
    ((attempt++))
done

echo "ERROR: Dashboard did not respond after ${MAX_ATTEMPTS} attempts"
exit 1
