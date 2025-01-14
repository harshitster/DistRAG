#!/bin/bash

set -e

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <worker_number1> [worker_number2 ...]"
    echo "Example: $0 3 4 5"
    exit 1
fi

# Function to remove a single worker
remove_worker() {
    local WORKER_NUM=$1
    local WORKER_NAME="pg_worker_${WORKER_NUM}"

    # Check if worker exists
    if ! docker ps --format '{{.Names}}' | grep -q "^${WORKER_NAME}$"; then
        echo "Error: Worker ${WORKER_NAME} does not exist or is not running"
        return 1
    fi

    echo "Starting worker node removal process for ${WORKER_NAME}..."

    # Drain the node first to safely move data
    echo "Draining node ${WORKER_NAME}..."
    docker exec pg_master psql -U postgres -d citus -c "SELECT citus_drain_node('${WORKER_NAME}', 5432);"

    # Wait for draining to complete
    echo "Waiting for node draining to complete..."
    while true; do
        DRAIN_COMPLETE=$(docker exec pg_master psql -U postgres -d citus -tAc "
            SELECT COUNT(*) 
            FROM pg_dist_shard_placement 
            WHERE nodename = '${WORKER_NAME}';")
        if [ "$DRAIN_COMPLETE" -eq "0" ]; then
            break
        fi
        echo "Still draining... ($DRAIN_COMPLETE shards remaining)"
        sleep 5
    done

    # Remove the node from the cluster
    echo "Removing node from cluster..."
    docker exec pg_master psql -U postgres -d citus -c "SELECT citus_remove_node('${WORKER_NAME}', 5432);"

    # Stop and remove the container
    echo "Stopping worker container..."
    docker compose down "${WORKER_NAME}"
    docker rm -f "${WORKER_NAME}" || true

    # Clean up the worker's volume
    echo "Cleaning up worker volume..."
    docker volume rm "club-management-system_citus-worker${WORKER_NUM}-data" || true

    echo "Worker node ${WORKER_NAME} removed successfully"
}

# Remove each specified worker
for WORKER_NUM in "$@"; do
    remove_worker "$WORKER_NUM"
done

# Update docker-compose.override.yml using Python script
echo "Updating docker-compose configuration..."
python3 scale/remove-worker-node.py "$@"

# Start rebalancing to redistribute shards
echo "Starting shard rebalancing..."
docker exec pg_master psql -U postgres -d citus -c "SELECT citus_rebalance_start();"

# Update services if there are any workers left
if [ -f docker-compose.override.yml ] && [ -s docker-compose.override.yml ]; then
    echo "Updating backup and recovery services..."
    docker compose up -d backup_service recovery_service
fi

# Restart cluster manager to apply changes
echo "Restarting cluster manager..."
docker compose restart cluster_manager

# Wait for cluster manager to initialize
echo "Waiting for cluster manager to initialize..."
sleep 10

# Verify removal for each worker
for WORKER_NUM in "$@"; do
    WORKER_NAME="pg_worker_${WORKER_NUM}"
    if ! docker exec pg_master psql -U postgres -d citus -tAc "SELECT nodename FROM pg_dist_node WHERE nodename = '${WORKER_NAME}';" | grep -q "${WORKER_NAME}"; then
        echo "Worker node ${WORKER_NAME} successfully removed from the cluster"
    else
        echo "Warning: Worker node ${WORKER_NAME} may not have been removed properly. Please check the cluster manager logs."
    fi
done

# Display current shard distribution
echo "Current shard distribution:"
docker exec pg_master psql -U postgres -d citus -c "\
SELECT nodename, count(*) as shard_count \
FROM pg_dist_shard_placement \
GROUP BY nodename \
ORDER BY nodename;"

echo "Worker node removal complete!"
echo "To verify the cluster status, run:"
echo "docker exec pg_master psql -U postgres -d citus -c '\dx'"
echo "docker exec pg_master psql -U postgres -d citus -c 'SELECT * FROM pg_dist_node;'"