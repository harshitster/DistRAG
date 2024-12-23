import os
import time
import subprocess
import docker
import logging
import sys
from datetime import datetime
from typing import Optional, Dict, List
import json

# Configuration
WORKER_NAMES = os.environ['WORKER_NAMES'].split(',')
POSTGRES_USER = os.environ['POSTGRES_USER']
POSTGRES_PASSWORD = os.environ['POSTGRES_PASSWORD']
BACKUP_DIR = '/backups'
MAX_RETRIES = 5
RETRY_DELAY = 5
HEALTH_CHECK_INTERVAL = 60  # seconds

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/var/log/worker-recovery.log')
    ]
)
logger = logging.getLogger(__name__)

try:
    # Modified Docker client initialization to use the default socket path
    client = docker.from_env()
    logger.error("Docker client initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize Docker client: {str(e)}")
    sys.exit(1)

def run_command(cmd: str, timeout: int = 30) -> tuple[bool, str]:
    """
    Run a shell command with timeout and return success status and output.
    """
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode == 0, result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out after {timeout} seconds: {cmd}")
        return False, "Command timed out"
    except Exception as e:
        logger.error(f"Command failed: {cmd}, Error: {str(e)}")
        return False, str(e)

def check_worker_health(worker: str) -> bool:
    """
    Check if a worker is healthy using pg_isready with retries.
    """
    for attempt in range(MAX_RETRIES):
        success, output = run_command(f"pg_isready -h {worker} -U {POSTGRES_USER}")
        if success:
            return True
        if attempt < MAX_RETRIES - 1:
            logger.warning(f"Health check failed for {worker}, attempt {attempt + 1}/{MAX_RETRIES}")
            time.sleep(RETRY_DELAY)
    
    logger.error(f"Worker {worker} is unhealthy after {MAX_RETRIES} attempts")
    return False

def get_latest_backup(worker: str) -> Optional[str]:
    """
    Get the path to the latest backup for a worker.
    """
    worker_backup_dir = os.path.join(BACKUP_DIR, worker)
    try:
        if not os.path.exists(worker_backup_dir):
            logger.error(f"Backup directory does not exist for worker {worker}")
            return None
        
        backup_dirs = [
            d for d in os.listdir(worker_backup_dir)
            if os.path.isdir(os.path.join(worker_backup_dir, d))
            and d.replace("_", "").isdigit()  # Ensure directory name is a valid timestamp
        ]
        
        if not backup_dirs:
            logger.error(f"No valid backups found for worker {worker}")
            return None
        
        latest = max(backup_dirs, key=lambda d: datetime.strptime(d, '%Y%m%d_%H%M%S'))
        return os.path.join(worker_backup_dir, latest)
    
    except Exception as e:
        logger.error(f"Error finding latest backup for {worker}: {str(e)}")
        return None

def verify_backup_integrity(backup_path: str) -> bool:
    """
    Verify the integrity of a backup directory.
    """
    try:
        # Check if backup directory exists and is not empty
        if not os.path.isdir(backup_path) or not os.listdir(backup_path):
            logger.error(f"Backup directory {backup_path} is invalid or empty")
            return False
        
        # Check for essential PostgreSQL files
        required_files = ['PG_VERSION', 'postgresql.conf']
        for file in required_files:
            if not os.path.exists(os.path.join(backup_path, file)):
                logger.error(f"Missing required file {file} in backup {backup_path}")
                return False
        
        return True
    
    except Exception as e:
        logger.error(f"Error verifying backup integrity: {str(e)}")
        return False

def restore_worker(worker: str) -> bool:
    """
    Restore a worker from the latest backup.
    """
    logger.info(f"Starting restoration of {worker}")
    success = False
    
    try:
        # Get container
        try:
            container = client.containers.get(worker)
        except docker.errors.NotFound:
            logger.error(f"Container {worker} not found")
            return False
        
        # Get latest backup
        backup_path = get_latest_backup(worker)
        if not backup_path or not verify_backup_integrity(backup_path):
            logger.error(f"No valid backup available for {worker}")
            return False
        
        logger.info(f"Using backup: {backup_path}")
        
        try:
            # Stop container
            logger.info(f"Stopping {worker} container")
            container.stop(timeout=30)  # Give container 30 seconds to stop gracefully
            
            # Clear old data
            logger.info(f"Clearing old data from {worker}")
            exec_result = container.exec_run(
                "bash -c 'rm -rf /var/lib/postgresql/data/*'",
                user='root'
            )
            if exec_result.exit_code != 0:
                raise Exception(f"Failed to clear old data: {exec_result.output.decode()}")
            
            # Copy backup
            logger.info(f"Restoring backup to {worker}")
            exec_result = container.exec_run(
                f"bash -c 'cp -R {backup_path}/* /var/lib/postgresql/data/'",
                user='root'
            )
            if exec_result.exit_code != 0:
                raise Exception(f"Failed to copy backup: {exec_result.output.decode()}")
            
            # Configure recovery
            recovery_config = [
                f"restore_command = 'cp /backups/wal_archive/{worker}/%f %p'",
                "recovery_target_timeline = 'latest'",
                "restore_command_timeout = '300s'",
                "recovery_min_apply_delay = '0'"
            ]
            
            logger.info("Writing recovery configuration")
            config_cmd = f"echo '{'; '.join(recovery_config)}' >> /var/lib/postgresql/data/postgresql.auto.conf"
            exec_result = container.exec_run(
                f"bash -c '{config_cmd}'",
                user='root'
            )
            if exec_result.exit_code != 0:
                raise Exception(f"Failed to write recovery configuration: {exec_result.output.decode()}")
            
            # Set permissions
            logger.info("Setting correct permissions")
            exec_result = container.exec_run(
                "chown -R postgres:postgres /var/lib/postgresql/data",
                user='root'
            )
            if exec_result.exit_code != 0:
                raise Exception(f"Failed to set permissions: {exec_result.output.decode()}")
            
            # Start container
            logger.info(f"Starting {worker} container")
            container.start()
            
            # Wait for recovery to complete
            recovery_timeout = MAX_RETRIES * 2  # Longer timeout for recovery
            for attempt in range(recovery_timeout):
                if check_worker_health(worker):
                    logger.info(f"Worker {worker} restored and healthy")
                    success = True
                    break
                logger.info(f"Waiting for worker to become healthy... ({attempt + 1}/{recovery_timeout})")
                time.sleep(RETRY_DELAY)
            
            if not success:
                logger.error(f"Worker {worker} failed to become healthy after restore")
                
        except Exception as e:
            logger.error(f"Error during restoration process: {str(e)}")
            try:
                # Try to start the container even if restoration failed
                container.start()
            except Exception as start_error:
                logger.error(f"Failed to restart container after error: {str(start_error)}")
    
    except Exception as e:
        logger.error(f"Critical error during worker restoration: {str(e)}")
    
    return success

def main():
    """
    Main function to monitor and restore workers.
    """
    logger.info("Starting worker recovery service")
    
    # Initial health check
    for worker in WORKER_NAMES:
        if not check_worker_health(worker):
            logger.warning(f"Worker {worker} unhealthy at startup")
    
    while True:
        try:
            for worker in WORKER_NAMES:
                if not check_worker_health(worker):
                    logger.warning(f"{worker} is down. Initiating recovery...")
                    if restore_worker(worker):
                        logger.info(f"Successfully restored {worker}")
                    else:
                        logger.error(f"Failed to restore {worker}")
                else:
                    logger.info(f"{worker} is healthy")
            
            time.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Error in main loop: {str(e)}")
            time.sleep(RETRY_DELAY)

if __name__ == "__main__":
    main()