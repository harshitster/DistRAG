#!/bin/bash

set -e

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <worker_number1> [worker_number2 ...]"
    echo "Example: $0 3 4 5"
    exit 1
fi

# Update docker-compose.override.yml using Python script
python3 scale/add-worker-node.py "$@"

# Start new workers
for WORKER_NUM in "$@"; do
    WORKER_NAME="pg_worker_${WORKER_NUM}"
    
    # Check if worker already exists in Docker
    if docker ps -a --format '{{.Names}}' | grep -q "^${WORKER_NAME}$"; then
        echo "Error: Worker ${WORKER_NAME} already exists in Docker"
        continue
    fi

    echo "Starting new worker node ${WORKER_NAME}..."
    docker compose up -d "${WORKER_NAME}"

    # Wait for PostgreSQL to be ready
    echo "Waiting for PostgreSQL to be ready on ${WORKER_NAME}..."
    until docker exec "${WORKER_NAME}" pg_isready -h localhost -p 5432; do
        echo "Waiting for PostgreSQL to start..."
        sleep 2
    done

    # Initialize Citus extension
    echo "Initializing Citus extension on ${WORKER_NAME}..."
    docker exec "${WORKER_NAME}" psql -U postgres -d citus -c "CREATE EXTENSION IF NOT EXISTS citus;"
done

# Update backup and recovery services
echo "Updating backup and recovery services..."
docker compose up -d backup_service recovery_service

# Restart cluster manager to pick up new workers
echo "Restarting cluster manager..."
docker compose restart cluster_manager

# Wait for cluster manager to initialize
echo "Waiting for cluster manager to initialize..."
sleep 10

# Check if workers were added successfully
echo "Verifying worker node connections..."
for WORKER_NUM in "$@"; do
    WORKER_NAME="pg_worker_${WORKER_NUM}"
    if docker exec pg_master psql -U postgres -d citus -tAc "SELECT nodename FROM pg_dist_node WHERE nodename = '${WORKER_NAME}';" | grep -q "${WORKER_NAME}"; then
        echo "Worker node ${WORKER_NAME} successfully added to the cluster"
    else
        echo "Warning: Worker node ${WORKER_NAME} may not have been added properly. Please check the cluster manager logs."
    fi
done

# Rebalance shards
echo "Starting shard rebalancing..."
docker exec pg_master psql -U postgres -d citus -c "SELECT rebalance_table_shards();"

# Verify rebalancing
echo "Verifying shard distribution..."
docker exec pg_master psql -U postgres -d citus -c "\
SELECT nodename, count(*) as shard_count \
FROM pg_dist_shard_placement \
GROUP BY nodename \
ORDER BY nodename;"

echo "Worker nodes have been successfully added to the cluster!"
echo "To verify the cluster status, run:"
echo "docker exec pg_master psql -U postgres -d citus -c '\dx'"
echo "docker exec pg_master psql -U postgres -d citus -c 'SELECT * FROM pg_dist_node;'"

echo "Adding worker node to pgadmin service..."
scale/add-worker-pgadmin.sh "$@"
echo "Worker node added to pgadmin service."