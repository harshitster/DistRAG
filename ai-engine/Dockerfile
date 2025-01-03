FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && \
    apt install -y libgl1-mesa-glx && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY ai-engine/ .
COPY ai-engine/wait-for-db-init.sh /wait-for-db-init.sh

RUN chmod +x /wait-for-db-init.sh

RUN python3 -m venv /app/venv && \
    . /app/venv/bin/activate && \
    pip install --upgrade pip --quiet && \
    pip install --no-cache-dir -r requirements.txt --quiet 

ENV PYTHONPATH=/app
ENV LLM_MODEL="models/gemini-1.5-pro"
ENV EMBED_MODEL="models/text-embedding-004"
ENV CACHE_ENGINE_URL="http://cache_engine:6380"

CMD  ["bash", "/wait-for-db-init.sh"]