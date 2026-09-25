# syntax=docker/dockerfile:1

FROM python:3.11-slim AS base

# Prevent Python from writing .pyc files and buffering stdout/stderr.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps kept minimal; wheels cover python-docx/openpyxl/pandas/boto3.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY app ./app

# Data directory for the SQLite DB and (optional) local file storage.
# On Cloudflare Containers, mount a volume here or use R2 + Postgres instead.
RUN mkdir -p /app/data
VOLUME ["/app/data"]

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8080/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
