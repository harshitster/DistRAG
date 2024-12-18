#!/bin/bash

echo "Beginning pg_hba.conf modifications..."

# Update pg_hba.conf
PG_HBA_PATH="/var/lib/postgresql/data/pg_hba.conf"

# Check if PostgreSQL is running using pg_isready instead of ps
if pg_isready -h localhost -p 5432; then
    # Backup existing configuration
    cp $PG_HBA_PATH "${PG_HBA_PATH}.backup"

    # Create new pg_hba.conf with updated rules
    cat > $PG_HBA_PATH << EOF
# TYPE  DATABASE        USER            ADDRESS                 METHOD
# Allow connections from all services in the docker network
host    all            all             samenet                 trust
host    all            all             10.0.0.0/8             trust
host    all            all             172.16.0.0/12          trust
host    all            all             192.168.0.0/16         trust

# Keep local connections
local   all            all                                    trust
host    all            all             127.0.0.1/32           trust
host    all            all             ::1/128                trust

# Allow replication connections from the backup service
host    replication     postgres        backup-service        trust
host    replication     postgres        all                  trust
EOF

    # Set proper ownership and permissions
    chown postgres:postgres $PG_HBA_PATH
    chmod 600 $PG_HBA_PATH

    # Reload PostgreSQL configuration
    gosu postgres pg_ctl reload
    echo "pg_hba.conf has been updated and PostgreSQL configuration reloaded"
else
    echo "ERROR: PostgreSQL is not running"
    exit 1
fi