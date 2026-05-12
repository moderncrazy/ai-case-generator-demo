FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    zlib1g-dev \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY ./docker/backend-requirements.txt /app

RUN pip install --no-cache-dir -r backend-requirements.txt

VOLUME ["/app/data"]
VOLUME ["/app/logs"]
VOLUME ["/app/models"]

EXPOSE 8000

COPY ./ /app

ENTRYPOINT ["uvicorn","src.main:app"]

CMD ["--host", "0.0.0.0", "--port", "8000"]