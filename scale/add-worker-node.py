#!/usr/bin/env python3

import sys
import yaml
from typing import List, Dict

class MyDumper(yaml.Dumper):
    def write_line_break(self, data=None):
        super().write_line_break(data)
        if len(self.indents) == 1:
            super().write_line_break()

def get_worker_list_from_env(compose_data: Dict) -> List[str]:
    """Get worker list from backup_service environment variable"""
    if 'services' in compose_data and 'backup_service' in compose_data['services']:
        service = compose_data['services']['backup_service']
        if 'environment' in service:
            env = service['environment']
            if isinstance(env, list):
                for item in env:
                    if isinstance(item, str) and item.startswith('WORKER_NAMES='):
                        return item.split('=')[1].split(',')
    return []

def get_all_workers() -> List[str]:
    """Get all worker names from override file or docker-compose files"""
    # First try to get from override file's environment variable
    try:
        with open('docker-compose.override.yml', 'r') as f:
            override_compose = yaml.safe_load(f) or {'services': {}}
            workers = get_worker_list_from_env(override_compose)
            if workers:
                return workers
    except FileNotFoundError:
        pass

    # If no environment variable found, scan for worker services
    workers = []
    
    # Check base compose file
    try:
        with open('docker-compose.yml', 'r') as f:
            base_compose = yaml.safe_load(f) or {'services': {}}
            for service_name in base_compose.get('services', {}):
                if service_name.startswith('pg_worker_'):
                    workers.append(service_name)
    except FileNotFoundError:
        pass

    # Check override file services
    try:
        with open('docker-compose.override.yml', 'r') as f:
            override_compose = yaml.safe_load(f) or {'services': {}}
            for service_name in override_compose.get('services', {}):
                if service_name.startswith('pg_worker_'):
                    workers.append(service_name)
    except FileNotFoundError:
        pass
    
    # Remove duplicates while preserving order
    return list(dict.fromkeys(workers))

def create_worker_service(worker_num: int) -> dict:
    """Create worker service configuration"""
    worker_name = f"pg_worker_{worker_num}"
    return {
        worker_name: {
            "container_name": worker_name,
            "build": {
                "context": ".",
                "dockerfile": "worker-node/Dockerfile"
            },
            "platform": "linux/amd64",
            "labels": ["com.citusdata.role=Worker"],
            "depends_on": ["cluster_manager"],
            "environment": {
                "POSTGRES_USER": "postgres",
                "POSTGRES_PASSWORD": "postgres",
                "PGUSER": "postgres",
                "PGPASSWORD": "postgres",
                "POSTGRES_HOST_AUTH_METHOD": "trust",
                "POSTGRES_DB": "citus",
                "POSTGRES_INITDB_ARGS": "-c wal_level=logical"
            },
            "volumes": [
                "healthcheck-volume:/healthcheck",
                f"citus-worker{worker_num}-data:/var/lib/postgresql/data",
                "db-init-signal:/db-init-signal",
                "worker-signal:/worker-signal",
                "worker-backups:/backups"
            ],
            "networks": ["citus-network"]
        }
    }

def update_compose_file(worker_nums: List[int]) -> None:
    """Update docker-compose.override.yml with new worker configurations"""
    try:
        with open('docker-compose.override.yml', 'r') as f:
            compose_data = yaml.safe_load(f) or {'services': {}, 'volumes': {}}
    except FileNotFoundError:
        compose_data = {'services': {}, 'volumes': {}}

    # Get list of all existing workers
    existing_workers = get_all_workers()
    
    # Add new workers to services and update existing_workers list
    for worker_num in worker_nums:
        worker_name = f"pg_worker_{worker_num}"
        
        if worker_name in compose_data.get('services', {}):
            print(f"Warning: Worker {worker_name} already exists in configuration")
            continue

        if worker_name not in existing_workers:
            existing_workers.append(worker_name)

        # Add worker service
        if 'services' not in compose_data:
            compose_data['services'] = {}
        worker_service = create_worker_service(worker_num)
        compose_data['services'].update(worker_service)

        # Add worker volume
        if 'volumes' not in compose_data:
            compose_data['volumes'] = {}
        compose_data['volumes'][f"citus-worker{worker_num}-data"] = None

    # Update backup and recovery services with complete worker list
    if existing_workers:
        worker_names_str = ','.join(sorted(existing_workers))
        for service in ['backup_service', 'recovery_service']:
            if service not in compose_data['services']:
                compose_data['services'][service] = {}
            compose_data['services'][service]['environment'] = [f'WORKER_NAMES={worker_names_str}']

    # Write updated configuration
    with open('docker-compose.override.yml', 'w') as f:
        yaml.dump(compose_data, f, Dumper=MyDumper, default_flow_style=False, sort_keys=False)

def main():
    if len(sys.argv) < 2:
        print("Usage: python update_docker_compose.py <worker_number1> [worker_number2 ...]")
        sys.exit(1)
    
    worker_nums = [int(num) for num in sys.argv[1:]]
    update_compose_file(worker_nums)

if __name__ == '__main__':
    main()