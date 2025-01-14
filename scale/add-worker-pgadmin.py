#!/usr/bin/env python3

import sys
import json
import yaml
import os
from pathlib import Path
from typing import Dict, Any

class MyDumper(yaml.Dumper):
    def write_line_break(self, data=None):
        super().write_line_break(data)
        if len(self.indents) == 1:
            super().write_line_break()

def create_servers_config(worker_num: int, pgadmin_dir: str) -> str:
    """Create and update pgAdmin server configuration"""
    worker_name = f"pg_worker_{worker_num}"
    
    # Create directory structure
    versions_dir = Path(pgadmin_dir) / "versions"
    versions_dir.mkdir(parents=True, exist_ok=True)
    
    # Determine new version number
    version_files = list(versions_dir.glob("citus-servers.v*.json"))
    new_version_num = len(version_files) + 1
    new_servers_json = versions_dir / f"citus-servers.v{new_version_num}.json"
    
    # Load or create initial configuration
    if new_version_num == 1:
        original_file = Path(pgadmin_dir) / "citus-servers.json"
        if not original_file.exists():
            initial_config = {
                "Servers": {
                    "1": {
                        "Name": "Citus Coordinator",
                        "Group": "Citus Cluster",
                        "Host": "pg_coordinator",
                        "Port": 5432,
                        "MaintenanceDB": "postgres",
                        "Username": "postgres",
                        "SSLMode": "prefer"
                    }
                }
            }
            original_file.write_text(json.dumps(initial_config, indent=4))
        servers_config = json.loads(original_file.read_text())
    else:
        prev_version = versions_dir / f"citus-servers.v{new_version_num - 1}.json"
        servers_config = json.loads(prev_version.read_text())
    
    # Get next server ID
    next_id = max(map(int, servers_config["Servers"].keys())) + 1
    
    # Add new server
    servers_config["Servers"][str(next_id)] = {
        "Name": f"Citus Worker {worker_num}",
        "Group": "Citus Cluster",
        "Host": worker_name,
        "Port": 5432,
        "MaintenanceDB": "postgres",
        "Username": "postgres",
        "SSLMode": "prefer"
    }
    
    # Save new configuration
    new_servers_json.write_text(json.dumps(servers_config, indent=4))
    
    # Update symlink
    latest_link = Path(pgadmin_dir) / "citus-servers.latest.json"
    if latest_link.exists():
        latest_link.unlink()
    latest_link.symlink_to(f"versions/citus-servers.v{new_version_num}.json")
    
    return new_servers_json.name

def update_compose_file(pgadmin_config: str) -> None:
    """Update docker-compose.override.yml with pgAdmin configuration"""
    try:
        with open('docker-compose.override.yml', 'r') as f:
            compose_data = yaml.safe_load(f) or {'services': {}, 'volumes': {}}
    except FileNotFoundError:
        compose_data = {'services': {}, 'volumes': {}}
    
    # Add or update pgAdmin service
    if 'services' not in compose_data:
        compose_data['services'] = {}
        
    compose_data['services']['pg_admin'] = {
        'volumes': [
            f'./pgadmin/{pgadmin_config}:/pgadmin4/servers.json:ro',
            'pgadmin-data:/var/lib/pgadmin'
        ]
    }
    
    # Ensure volumes section exists
    if 'volumes' not in compose_data:
        compose_data['volumes'] = {}
    
    # Add pgadmin volume
    compose_data['volumes']['pgadmin-data'] = None
    
    # Write updated configuration
    with open('docker-compose.override.yml', 'w') as f:
        yaml.dump(compose_data, f, Dumper=MyDumper, default_flow_style=False, sort_keys=False)

def main():
    if len(sys.argv) != 2:
        print("Usage: python add-worker-pgadmin.py <worker_number>")
        sys.exit(1)
    
    worker_num = int(sys.argv[1])
    pgadmin_dir = "./pgadmin"
    
    # Update servers configuration
    config_file = create_servers_config(worker_num, pgadmin_dir)
    
    # Update docker-compose.override.yml
    update_compose_file("citus-servers.latest.json")

if __name__ == '__main__':
    main()