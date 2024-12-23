#!/bin/sh

while [ ! -f /worker-signal/backup-init.done ]; do
    echo "Waiting for backup-init to complete..."
    sleep 1
done
echo "backup-init completed. Starting recovery service..."

/app/venv/bin/python /app/worker-recovery.py