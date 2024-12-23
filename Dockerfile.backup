FROM postgres:16.3

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /backups && chown postgres:postgres /backups

COPY worker-backup/ /app/

RUN chmod +x /app/worker-backup-entrypoint.sh /app/worker-backup.sh

RUN python3 -m venv /app/venv && \
    . /app/venv/bin/activate && \
    pip install --upgrade pip --quiet && \
    pip install --no-cache-dir -r /app/requirements.txt --quiet

USER postgres

CMD ["bash", "/app/worker-backup-entrypoint.sh"]