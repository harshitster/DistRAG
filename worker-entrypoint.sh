#!/bin/bash

echo "Starting worker initialization sequence..."

# Step 1: Run wait-for-manager.sh
echo "Running wait-for-manager.sh..."
/wait-for-manager.sh &
POSTGRES_PID=$!

# Wait for PostgreSQL to be ready
until pg_isready -h localhost -p 5432; do
    echo "Waiting for PostgreSQL to start..."
    sleep 1
done
echo "PostgreSQL is ready"

# Step 2: Run wait-for-db-init.sh
echo "Running wait-for-db-init.sh..."
/wait-for-db-init.sh 
echo "DB init check completed"

# Step 3: Wait for table propagation
echo "Waiting for table propagation..."
sleep 10

# Step 4: Run pg_hba update script
echo "Running update-pg-hba.sh..."
/update-pg-hba.sh

# Step 5: Ensure correct permissions on data directory
echo "Setting correct permissions on data directory..."
chown -R postgres:postgres /var/lib/postgresql/data
chmod 700 /var/lib/postgresql/data

# Create worker-signal directory with correct permissions
mkdir -p /worker-signal
chown -R postgres:postgres /worker-signal

echo "Worker initialization sequence completed"
echo "Creating worker-init signal file..."
gosu postgres touch /worker-signal/worker-init.done

# Wait for PostgreSQL process
wait $POSTGRES_PID