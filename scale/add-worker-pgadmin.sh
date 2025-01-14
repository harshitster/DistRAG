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
python3 scale/add-worker-pgadmin.py "$WORKER_NUM"

# Restart pgAdmin container
echo "Recreating pgAdmin container with new configuration..."
docker stop pg_admin || true
docker rm -f pg_admin || true
docker volume rm -f club-management-system_pgadmin-data || true
docker compose up -d pg_admin

echo "Successfully updated docker-compose.override.yml and citus-servers configuration"
echo "New worker node ${WORKER_NAME} has been added to pgAdmin"