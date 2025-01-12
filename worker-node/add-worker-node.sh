#!/bin/bash

set -e

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <worker_number>"
    echo "Example: $0 3"
    exit 1
fi

WORKER_NUM=$1
WORKER_NAME="pg_worker_${WORKER_NUM}"

# Check if worker number already exists
if docker ps -a --format '{{.Names}}' | grep -q "^${WORKER_NAME}$"; then
    echo "Error: Worker ${WORKER_NAME} already exists"
    exit 1
fi

# Get existing worker names from backup service
EXISTING_WORKERS=$(docker inspect pg_backup_service | jq -r '.[0].Config.Env[] | select(startswith("WORKER_NAMES=")) | split("=")[1]')
NEW_WORKER_LIST="${EXISTING_WORKERS},${WORKER_NAME}"

# Create docker-compose.override.yml
cat > docker-compose.override.yml << EOF
services:
  ${WORKER_NAME}:
    container_name: "${WORKER_NAME}"
    build:
      context: .
      dockerfile: worker-node/Dockerfile
    platform: linux/amd64
    labels:
      - "com.citusdata.role=Worker"
    depends_on:
      - cluster_manager
    environment:
      POSTGRES_USER: "postgres"
      POSTGRES_PASSWORD: "postgres"
      PGUSER: "postgres"
      PGPASSWORD: "postgres"
      POSTGRES_HOST_AUTH_METHOD: "trust"
      POSTGRES_DB: "citus" 
      POSTGRES_INITDB_ARGS: "-c wal_level=logical"
    volumes:
      - healthcheck-volume:/healthcheck
      - citus-worker${WORKER_NUM}-data:/var/lib/postgresql/data
      - db-init-signal:/db-init-signal
      - worker-signal:/worker-signal
      - worker-backups:/backups
    networks:
      - citus-network

  backup_service:
    environment:
      - WORKER_NAMES=${NEW_WORKER_LIST}

  recovery_service:
    environment:
      - WORKER_NAMES=${NEW_WORKER_LIST}

volumes:
  citus-worker${WORKER_NUM}-data:
EOF

# Start the new worker
echo "Starting new worker node ${WORKER_NAME}..."
docker compose up -d ${WORKER_NAME}

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
until docker exec "${WORKER_NAME}" pg_isready -h localhost -p 5432; do
    echo "Waiting for PostgreSQL to start..."
    sleep 2
done

# Initialize Citus extension
echo "Initializing Citus extension..."
docker exec "${WORKER_NAME}" psql -U postgres -d citus -c "CREATE EXTENSION IF NOT EXISTS citus;"

# Update backup and recovery services
echo "Updating backup and recovery services..."
docker compose up -d backup_service recovery_service

# Restart cluster manager to pick up the new worker
echo "Restarting cluster manager..."
docker compose restart cluster_manager

# Wait for cluster manager to initialize
echo "Waiting for cluster manager to initialize..."
sleep 10

# Check if worker was added successfully
echo "Verifying worker node connection..."
if docker exec pg_master psql -U postgres -d citus -tAc "SELECT nodename FROM pg_dist_node WHERE nodename = '${WORKER_NAME}';" | grep -q "${WORKER_NAME}"; then
    echo "Worker node ${WORKER_NAME} successfully added to the cluster"
else
    echo "Warning: Worker node may not have been added properly. Please check the cluster manager logs."
fi

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

echo "New worker node ${WORKER_NAME} has been successfully added to the cluster!"
echo "The configuration has been saved to docker-compose.override.yml"
echo "To verify the cluster status, run:"
echo "docker exec pg_master psql -U postgres -d citus -c '\dx'"
echo "docker exec pg_master psql -U postgres -d citus -c 'SELECT * FROM pg_dist_node;'"