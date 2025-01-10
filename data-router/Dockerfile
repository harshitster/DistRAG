FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && \
    apt install -y libgl1-mesa-glx && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY data-router/ .

RUN python3 -m venv /app/venv && \
    . /app/venv/bin/activate && \
    pip install --upgrade pip --quiet && \
    pip install --no-cache-dir -r requirements.txt --quiet 

RUN chmod +x /app/entrypoint.sh

CMD ["bash", "/app/entrypoint.sh"]