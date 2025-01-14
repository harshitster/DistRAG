#!/bin/bash

set -e

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <worker_number>"
    echo "Example: $0 3"
    exit 1
fi

WORKER_NUM=$1
WORKER_NAME="pg_worker_${WORKER_NUM}"

# Update configuration using Python script
echo "Removing ${WORKER_NAME} from pgAdmin configuration..."
if ! python3 scale/remove-worker-pgadmin.py "$WORKER_NUM"; then
    echo "Failed to remove worker from configuration"
    exit 1
fi

# Restart pgAdmin container
echo "Recreating pgAdmin container with updated configuration..."
docker stop pg_admin || true
docker rm -f pg_admin || true
docker volume rm -f club-management-system_pgadmin-data || true
docker compose up -d pg_admin

echo "Successfully updated pgAdmin configuration"
echo "Worker node ${WORKER_NAME} has been removed from pgAdmin"