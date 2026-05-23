# ── Build stage ──────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install dependencies into a prefix so they can be copied cleanly
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy service source
COPY app/       ./app/
COPY config/    ./config/
COPY prompts/   ./prompts/

# Environment defaults (override at runtime)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DD_LLMOBS_ENABLED=1 \
    DD_LLMOBS_ML_APP=policydiff \
    CLASSIFIER_POLL_INTERVAL_SECONDS=60 \
    CLASSIFIER_BATCH_SIZE=5

# Run via ddtrace-run so every process gets Datadog instrumentation
CMD ["ddtrace-run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
