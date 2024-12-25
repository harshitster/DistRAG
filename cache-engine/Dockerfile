FROM --platform=linux/amd64 python:3.11-slim

WORKDIR /app

RUN apt-get update && \
    apt install -y libgl1-mesa-glx && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY cache-engine/ .

RUN python3 -m venv /app/venv && \
    . /app/venv/bin/activate && \
    pip install --upgrade pip --quiet && \
    pip install --no-cache-dir -r requirements.txt --quiet 

ENV PYTHONPATH=/app
ENV VECTOR_DIMENSION=768
ENV EMBEDER=msmarco-distilbert-base-v4
ENV INDEX_NAME=idx:cache
ENV MAX_CACHE_PER=100
ENV CACHE_ALGO=LFU

CMD ["/app/venv/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "6380"]