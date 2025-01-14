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

def update_compose_file(worker_nums: List[int]) -> None:
    """Update docker-compose.override.yml to remove specified workers"""
    try:
        with open('docker-compose.override.yml', 'r') as f:
            compose_data = yaml.safe_load(f) or {'services': {}, 'volumes': {}}
    except FileNotFoundError:
        print("Error: docker-compose.override.yml not found")
        sys.exit(1)

    # Get current worker list from environment
    existing_workers = get_worker_list_from_env(compose_data)
    if not existing_workers:
        existing_workers = [name for name in compose_data.get('services', {}).keys() 
                          if name.startswith('pg_worker_')]

    services_to_remove = []
    volumes_to_remove = []
    
    for worker_num in worker_nums:
        worker_name = f"pg_worker_{worker_num}"
        
        # Check if worker exists in services
        if worker_name not in compose_data.get('services', {}):
            print(f"Warning: Worker {worker_name} not found in configuration")
            continue

        # Add to removal lists
        services_to_remove.append(worker_name)
        volumes_to_remove.append(f"citus-worker{worker_num}-data")
        
        # Remove from worker list
        if worker_name in existing_workers:
            existing_workers.remove(worker_name)

    # Remove services
    for service in services_to_remove:
        compose_data['services'].pop(service, None)

    # Remove volumes
    for volume in volumes_to_remove:
        compose_data['volumes'].pop(volume, None)

    # Update environment variables if we have any workers left
    worker_names_str = ','.join(sorted(existing_workers)) if existing_workers else ''
    
    # Update or remove backup and recovery services based on remaining workers
    for service in ['backup_service', 'recovery_service']:
        if service in compose_data['services']:
            if worker_names_str:
                compose_data['services'][service]['environment'] = [f'WORKER_NAMES={worker_names_str}']
            else:
                # If no workers left, remove the services
                compose_data['services'].pop(service)

    # Remove empty sections
    if not compose_data['services']:
        del compose_data['services']
    if not compose_data['volumes']:
        del compose_data['volumes']

    # Write updated configuration
    with open('docker-compose.override.yml', 'w') as f:
        if compose_data:  # Only write if there's content
            yaml.dump(compose_data, f, Dumper=MyDumper, default_flow_style=False, sort_keys=False)
        else:
            f.write('')  # Create empty file if no content

def main():
    if len(sys.argv) < 2:
        print("Usage: python remove_worker_compose.py <worker_number1> [worker_number2 ...]")
        sys.exit(1)
    
    worker_nums = [int(num) for num in sys.argv[1:]]
    update_compose_file(worker_nums)

if __name__ == '__main__':
    main()