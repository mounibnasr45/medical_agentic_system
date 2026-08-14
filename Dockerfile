# Single-stage: the API is pure Python and the frontend deploys separately as a
# static site, so there is nothing to compile here.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Build-only toolchain, removed in the same layer so it never reaches the image.
COPY requirements.txt .
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y gcc \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY medical_agent/ ./medical_agent/
COPY scripts/ ./scripts/
COPY data/ ./data/

# Run unprivileged.
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Render assigns the port at runtime; binding a fixed 8000 fails its health check.
# One worker deliberately: the instance has 512MB, and both the session store and
# the rate limiter are per-process.
CMD ["sh", "-c", "uvicorn medical_agent.api.server:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
