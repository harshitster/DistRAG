# Dockerfile.recovery
FROM python:3.11-slim

WORKDIR /app

# Add PostgreSQL apt repository to get PostgreSQL 16 client
RUN apt-get update && \
    apt-get install -y curl gnupg2 && \
    curl https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add - && \
    echo "deb http://apt.postgresql.org/pub/repos/apt/ bookworm-pgdg main" > /etc/apt/sources.list.d/pgdg.list && \
    apt-get update && \
    apt-get install -y \
    postgresql-client-16 \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

COPY worker-recovery/ /app/

RUN chmod +x /app/worker-recovery-entrypoint.sh

RUN python3 -m venv /app/venv && \
    . /app/venv/bin/activate && \
    pip install --upgrade pip --quiet && \
    pip install --no-cache-dir -r /app/requirements.txt --quiet

CMD ["bash", "/app/worker-recovery-entrypoint.sh"]