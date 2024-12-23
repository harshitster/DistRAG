#!/bin/bash

set -e

# Configuration
WORKERS=${WORKER_NAMES:-"worker1,worker2"}
ARCHIVE_INTERVAL=${ARCHIVE_INTERVAL:-300}
FULL_BACKUP_INTERVAL=${FULL_BACKUP_INTERVAL:-86400}  # 24 hours
BACKUP_DIR="/backups"
RETENTION_DAYS=${RETENTION_DAYS:-7}
MAX_RETRIES=5
RETRY_DELAY=5

# Ensure backup directory exists with correct permissions
mkdir -p "$BACKUP_DIR"
chown postgres:postgres "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

# Logging function with proper timestamps and log levels
log() {
    local level=$1
    local message=$2
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] [${level}] $message"
}

# Function to wait for worker availability
wait_for_worker() {
    local worker=$1
    local retries=0
    
    while [ $retries -lt $MAX_RETRIES ]; do
        if pg_isready -h "$worker" -U "$POSTGRES_USER" > /dev/null 2>&1; then
            log "INFO" "Worker $worker is ready"
            return 0
        fi
        retries=$((retries + 1))
        log "WARN" "Worker $worker not ready, attempt $retries of $MAX_RETRIES"
        sleep $RETRY_DELAY
    done
    
    log "ERROR" "Worker $worker failed to become ready after $MAX_RETRIES attempts"
    return 1
}

# Function to setup replication with error handling
setup_replication() {
    local all_success=true

    for worker in ${WORKERS//,/ }; do
        log "INFO" "Setting up replication for $worker"
        
        # Wait for worker to be ready
        if ! wait_for_worker "$worker"; then
            log "ERROR" "Cannot setup replication for $worker - worker not available"
            all_success=false
            continue
        fi
        
        local attempt=1
        local worker_success=false
        
        while [ $attempt -le $MAX_RETRIES ]; do
            if psql -h "$worker" -U "$POSTGRES_USER" -d citus -c "SELECT 1 FROM pg_replication_slots WHERE slot_name = '${worker}_slot'" 2>/dev/null | grep -q 1; then
                log "INFO" "Replication slot already exists for $worker"
                worker_success=true
                break
            else
                if psql -h "$worker" -U "$POSTGRES_USER" -d citus -c "SELECT pg_create_physical_replication_slot('${worker}_slot');" 2>/dev/null; then
                    log "INFO" "Created replication slot for $worker"
                    worker_success=true
                    break
                fi
            fi
            
            log "WARN" "Attempt $attempt failed for $worker, retrying in $RETRY_DELAY seconds..."
            sleep $RETRY_DELAY
            attempt=$((attempt + 1))
        done
        
        if ! $worker_success; then
            log "ERROR" "Failed to setup replication for $worker after $MAX_RETRIES attempts"
            all_success=false
        fi
    done
    
    if ! $all_success; then
        return 1
    fi
    return 0
}

# Function to take full backup with proper error handling
take_full_backup() {
    local all_success=true
    
    for worker in ${WORKERS//,/ }; do
        log "INFO" "Starting full backup for $worker"
        
        if ! wait_for_worker "$worker"; then
            log "ERROR" "Cannot take backup for $worker - worker not available"
            all_success=false
            continue
        fi
        
        local backup_dir="$BACKUP_DIR/$worker/$(date +'%Y%m%d_%H%M%S')"
        mkdir -p "$backup_dir"
        chown postgres:postgres "$backup_dir"
        chmod 700 "$backup_dir"
        
        local attempt=1
        local backup_success=false
        
        while [ $attempt -le $MAX_RETRIES ]; do
            if pg_basebackup -h "$worker" -D "$backup_dir" -P -U "$POSTGRES_USER" -X stream 2>&1; then
                log "INFO" "Successfully completed full backup for $worker"
                chmod -R 700 "$backup_dir"
                backup_success=true
                break
            else
                log "WARN" "Backup attempt $attempt failed for $worker"
                sleep $RETRY_DELAY
                attempt=$((attempt + 1))
            fi
        done
        
        if ! $backup_success; then
            log "ERROR" "Failed to take backup for $worker after $MAX_RETRIES attempts"
            rm -rf "$backup_dir"
            all_success=false
        fi
    done
    
    if ! $all_success; then
        return 1
    fi
    
    # Signal successful backup completion
    touch "/worker-signal/backup-init.done"
    log "INFO" "Created backup completion signal file"
    return 0
}

# Function to archive WAL files with error handling
archive_wal() {
    local all_success=true

    for worker in ${WORKERS//,/ }; do
        log "INFO" "Starting WAL archival for $worker"
        
        if ! wait_for_worker "$worker"; then
            log "ERROR" "Cannot archive WAL for $worker - worker not available"
            all_success=false
            continue
        fi
        
        local wal_dir="$BACKUP_DIR/wal_archive/$worker"
        mkdir -p "$wal_dir"
        chown postgres:postgres "$wal_dir"
        chmod 700 "$wal_dir"
        
        # Start WAL archiving in background
        pg_receivewal -h "$worker" -D "$wal_dir" -U "$POSTGRES_USER" \
            --slot="${worker}_slot" --create-slot --start -v >> "$BACKUP_DIR/wal_${worker}.log" 2>&1 &
        
        # Store PID for potential future use
        echo $! > "$BACKUP_DIR/wal_${worker}.pid"
    done
    
    if ! $all_success; then
        return 1
    fi
    return 0
}

# Function to cleanup old backups safely
cleanup_old_backups() {
    log "INFO" "Starting cleanup of old backups"
    
    # Find and delete old backup directories
    find "$BACKUP_DIR" -type d -mtime +"$RETENTION_DAYS" -path "*/2*" | while read -r dir; do
        log "INFO" "Removing old backup: $dir"
        rm -rf "$dir"
    done
    
    # Find and delete old WAL files
    find "$BACKUP_DIR/wal_archive" -type f -mtime +"$RETENTION_DAYS" | while read -r file; do
        log "INFO" "Removing old WAL file: $file"
        rm -f "$file"
    done
    
    # Clean up empty directories
    find "$BACKUP_DIR" -type d -empty -delete
}

# Trap for cleanup
cleanup() {
    log "INFO" "Stopping backup service..."
    # Kill any running WAL receiver processes
    for worker in ${WORKERS//,/ }; do
        if [ -f "$BACKUP_DIR/wal_${worker}.pid" ]; then
            pid=$(cat "$BACKUP_DIR/wal_${worker}.pid")
            kill -TERM "$pid" 2>/dev/null || true
            rm -f "$BACKUP_DIR/wal_${worker}.pid"
        fi
    done
    exit 0
}

trap cleanup SIGTERM SIGINT

# Initial setup
log "INFO" "Starting backup service"
log "INFO" "Performing initial setup"

if ! setup_replication; then
    log "ERROR" "Initial replication setup failed"
    exit 1
fi

if ! take_full_backup; then
    log "ERROR" "Initial full backup failed"
    exit 1
fi

if ! archive_wal; then
    log "ERROR" "Initial WAL archiving setup failed"
    exit 1
fi

# Main loop
log "INFO" "Starting main backup loop"
last_full_backup=$(date +%s)

while true; do
    current_time=$(date +%s)
    
    # Take full backup if interval has passed
    if [ $((current_time - last_full_backup)) -ge "$FULL_BACKUP_INTERVAL" ]; then
        log "INFO" "Full backup interval reached"
        if take_full_backup; then
            last_full_backup=$current_time
            log "INFO" "Full backup completed successfully"
        else
            log "ERROR" "Full backup failed"
        fi
    fi
    
    # Check if WAL archiving is still running and restart if needed
    for worker in ${WORKERS//,/ }; do
        if [ -f "$BACKUP_DIR/wal_${worker}.pid" ]; then
            pid=$(cat "$BACKUP_DIR/wal_${worker}.pid")
            if ! kill -0 "$pid" 2>/dev/null; then
                log "WARN" "WAL archiving for $worker died, restarting..."
                archive_wal
            fi
        else
            log "WARN" "No PID file for WAL archiving of $worker, restarting..."
            archive_wal
        fi
    done
    
    cleanup_old_backups
    
    log "INFO" "Sleeping for $ARCHIVE_INTERVAL seconds"
    sleep "$ARCHIVE_INTERVAL"
done