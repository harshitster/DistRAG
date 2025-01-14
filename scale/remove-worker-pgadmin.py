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

def remove_server_config(worker_num: int, pgadmin_dir: str) -> bool:
    """Remove server from pgAdmin configuration and create new version"""
    worker_name = f"pg_worker_{worker_num}"
    
    # Check directory structure
    versions_dir = Path(pgadmin_dir) / "versions"
    if not versions_dir.exists():
        print(f"Error: No configuration versions found in {versions_dir}")
        return False
    
    # Find latest version
    version_files = list(versions_dir.glob("citus-servers.v*.json"))
    if not version_files:
        print("Error: No configuration versions found")
        return False
    
    current_version = max(int(f.stem.split('.v')[1]) for f in version_files)
    current_file = versions_dir / f"citus-servers.v{current_version}.json"
    
    # Load current configuration
    try:
        with current_file.open() as f:
            servers_config = json.load(f)
    except Exception as e:
        print(f"Error reading configuration: {e}")
        return False
    
    # Find and remove server
    server_id = None
    for sid, server in servers_config["Servers"].items():
        if server.get("Host") == worker_name:
            server_id = sid
            break
    
    if not server_id:
        print(f"Warning: Server {worker_name} not found in configuration")
        return False
    
    # Create new version with server removed
    new_version = current_version + 1
    new_config = servers_config.copy()
    del new_config["Servers"][server_id]
    
    # Save new configuration
    new_file = versions_dir / f"citus-servers.v{new_version}.json"
    new_file.write_text(json.dumps(new_config, indent=4))
    
    # Update symlink
    latest_link = Path(pgadmin_dir) / "citus-servers.latest.json"
    if latest_link.exists():
        latest_link.unlink()
    latest_link.symlink_to(f"versions/citus-servers.v{new_version}.json")
    
    return True

def update_compose_file() -> None:
    """Update docker-compose.override.yml"""
    try:
        with open('docker-compose.override.yml', 'r') as f:
            compose_data = yaml.safe_load(f) or {'services': {}, 'volumes': {}}
    except FileNotFoundError:
        compose_data = {'services': {}, 'volumes': {}}
    
    # Ensure pg_admin service points to latest config
    if 'services' not in compose_data:
        compose_data['services'] = {}
    
    if 'pg_admin' in compose_data['services']:
        compose_data['services']['pg_admin']['volumes'] = [
            './pgadmin/citus-servers.latest.json:/pgadmin4/servers.json:ro',
            'pgadmin-data:/var/lib/pgadmin'
        ]
    
    # Write updated configuration
    with open('docker-compose.override.yml', 'w') as f:
        yaml.dump(compose_data, f, Dumper=MyDumper, default_flow_style=False, sort_keys=False)

def main():
    if len(sys.argv) != 2:
        print("Usage: python remove_pgadmin_config.py <worker_number>")
        sys.exit(1)
    
    worker_num = int(sys.argv[1])
    pgadmin_dir = "./pgadmin"
    
    # Remove server from configuration
    if remove_server_config(worker_num, pgadmin_dir):
        # Update docker-compose.override.yml
        update_compose_file()
        print(f"Successfully removed worker {worker_num} from pgAdmin configuration")
    else:
        sys.exit(1)

if __name__ == '__main__':
    main()