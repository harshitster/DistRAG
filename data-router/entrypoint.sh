#!/bin/sh

while [ ! -f /worker-signal/backup-init.done ]; do
    echo "Waiting for backup-init to complete..."
    sleep 1
done
echo "backup-init completed. Starting data_router service..."

/app/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8085