#!/bin/sh

while [ ! -f /db-init-signal/db-init.done ]; do
  echo "Waiting for python-init to complete..."
  sleep 1
done
echo "python-init completed. Starting service..."

exec "$@"