#!/bin/sh

while [ ! -f /worker-signal/worker-init.done ]; do
    echo "Waiting for worker-init to complete..."
    sleep 1
done
echo "worker-init completed. Starting backup service..."

# Start the backup script
/app/worker-backup.sh &

# Wait for initial backup by checking for backup directories
max_attempts=60  # Wait up to 5 minutes (60 * 5 seconds)
attempt=1

while [ $attempt -le $max_attempts ]; do
    # Check if backup directories exist and contain data for both workers
    if [ -d "/backups/pg_worker_1" ] && [ -d "/backups/pg_worker_2" ] && \
       [ "$(ls -A /backups/pg_worker_1)" ] && [ "$(ls -A /backups/pg_worker_2)" ]; then
        echo "Initial backup completed successfully. Creating signal file..."
        touch /worker-signal/backup-init.done
        break
    fi
    echo "Waiting for initial backup to complete... (attempt $attempt of $max_attempts)"
    sleep 5
    attempt=$((attempt + 1))
done

if [ $attempt -gt $max_attempts ]; then
    echo "Timeout waiting for initial backup to complete"
    exit 1
fi

# Wait for the backup process to complete (it won't because it's a continuous loop)
wait