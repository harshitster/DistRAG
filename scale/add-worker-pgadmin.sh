#!/bin/bash

set -e

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <worker_number>"
    echo "Example: $0 3"
    exit 1
fi

WORKER_NUM=$1
WORKER_NAME="pg_worker_${WORKER_NUM}"

# Setup directory structure
PGADMIN_DIR="./pgadmin"
mkdir -p "${PGADMIN_DIR}/versions"

# Path to the original and new servers.json files
ORIGINAL_SERVERS_JSON="${PGADMIN_DIR}/citus-servers.json"
NEW_VERSION_NUM=$(ls ${PGADMIN_DIR}/versions/citus-servers.v*.json 2>/dev/null | wc -l)
NEW_VERSION_NUM=$((NEW_VERSION_NUM + 1))
NEW_SERVERS_JSON="${PGADMIN_DIR}/versions/citus-servers.v${NEW_VERSION_NUM}.json"

# Copy the most recent version or the original if no versions exist
if [ $NEW_VERSION_NUM -eq 1 ]; then
    if [ ! -f "$ORIGINAL_SERVERS_JSON" ]; then
        echo '{
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
        }' > "$ORIGINAL_SERVERS_JSON"
    fi
    cp "$ORIGINAL_SERVERS_JSON" "$NEW_SERVERS_JSON"
else
    PREV_VERSION="${PGADMIN_DIR}/versions/citus-servers.v$((NEW_VERSION_NUM - 1)).json"
    cp "$PREV_VERSION" "$NEW_SERVERS_JSON"
fi

# Get the next server ID
NEXT_ID=$(jq '.Servers | keys[] | tonumber' "$NEW_SERVERS_JSON" | sort -n | tail -n1)
NEXT_ID=$((NEXT_ID + 1))

# Add new server to the configuration
NEW_SERVER=$(cat << EOF
{
    "Name": "Citus Worker ${WORKER_NUM}",
    "Group": "Citus Cluster",
    "Host": "${WORKER_NAME}",
    "Port": 5432,
    "MaintenanceDB": "postgres",
    "Username": "postgres",
    "SSLMode": "prefer"
}
EOF
)

# Update the JSON file with new server
TMP_FILE=$(mktemp)
jq --arg id "$NEXT_ID" --arg server "$NEW_SERVER" \
    ".Servers += {(\$id): \$server | fromjson}" "$NEW_SERVERS_JSON" > "$TMP_FILE"
mv "$TMP_FILE" "$NEW_SERVERS_JSON"

# Create a symlink to the latest version
LATEST_LINK="${PGADMIN_DIR}/citus-servers.latest.json"
ln -sf "versions/citus-servers.v${NEW_VERSION_NUM}.json" "$LATEST_LINK"

# Create temporary file for the new docker-compose.override.yml
TMP_FILE=$(mktemp)

# Read the existing docker-compose.override.yml and process it
{
    # Write services header
    echo "services:"
    
    # Process the file line by line
    while IFS= read -r line; do
        if [[ $line =~ ^services: ]]; then
            # Skip the services line as we already wrote it
            continue
        elif [[ $line =~ ^[[:space:]]*pg_admin: ]]; then
            # Skip the existing pg_admin section
            while IFS= read -r subline; do
                if [[ $subline =~ ^[[:space:]]*[a-zA-Z] && ! $subline =~ ^[[:space:]]*volumes: ]]; then
                    # Break when we hit the next service or main section
                    echo "$subline"
                    break
                fi
            done
        elif [[ $line =~ ^volumes: ]]; then
            # Add pg_admin configuration before volumes section
            echo "  pg_admin:"
            echo "    volumes:"
            echo "      - ./pgadmin/citus-servers.latest.json:/pgadmin4/servers.json:ro"
            echo "      - pgadmin-data:/var/lib/pgadmin"
            echo ""
            echo "$line"
        else
            # Copy all other lines as is
            echo "$line"
        fi
    done < docker-compose.override.yml
} > "$TMP_FILE"

# If volumes section wasn't found, add pg_admin and volumes at the end
if ! grep -q "^volumes:" "$TMP_FILE"; then
    echo "" >> "$TMP_FILE"
    echo "  pg_admin:" >> "$TMP_FILE"
    echo "    volumes:" >> "$TMP_FILE"
    echo "      - ./pgadmin/citus-servers.latest.json:/pgadmin4/servers.json:ro" >> "$TMP_FILE"
    echo "      - pgadmin-data:/var/lib/pgadmin" >> "$TMP_FILE"
    echo "" >> "$TMP_FILE"
    echo "volumes:" >> "$TMP_FILE"
    echo "  pgadmin-data:" >> "$TMP_FILE"
fi

# Replace original file with new content
mv "$TMP_FILE" docker-compose.override.yml

# Restart pgAdmin container
echo "Recreating pgAdmin container with new configuration..."
docker stop pg_admin
docker rm -f pg_admin
docker volume rm -f club-management-system_pgadmin-data
docker compose up -d pg_admin

echo "Successfully updated docker-compose.override.yml and citus-servers configuration"
echo "New worker node ${WORKER_NAME} has been added to pgAdmin"