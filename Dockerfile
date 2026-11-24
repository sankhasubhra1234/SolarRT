# Production image for the SolarRT website/API server (used by deploy/docker-compose.yml).
# During CI this is built with Python 3.13; release builds should pin the digest.
FROM python:3.13-slim@sha256:b1a7c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b as builder

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    SOLARRT_HOST=0.0.0.0 SOLARRT_PORT=8000 \
    SOLARRT_DATA_DIR=/data SOLARRT_ENABLE_DOCS=0

WORKDIR /app
# Install build dependencies first (kept separate for cache invalidation)
RUN apt-get update && apt-get install -y --no-install-recommends build-essential gcc && rm -rf /var/lib/apt/lists/*

# Copy requirements and install from hashed lock file
COPY requirements.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements.txt

# Copy application source
COPY solarrt ./solarrt

# Runtime stage - lean image
FROM python:3.13-slim@sha256:b1a7c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    SOLARRT_HOST=0.0.0.0 SOLARRT_PORT=8000 \
    SOLARRT_DATA_DIR=/data SOLARRT_ENABLE_DOCS=0

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY solarrt ./solarrt

# Run as an unprivileged user; /data holds feedback (mounted volume)
RUN useradd --create-home --uid 10001 appuser && mkdir -p /data && chown appuser /data
USER appuser
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

# --proxy-headers + forwarded-allow-ips: take the visitor's real IP from the Caddy proxy.
# Safe to trust "*" here because port 8000 is only reachable on the internal Docker network.
# --no-access-log: request URLs contain users' coordinates (see the privacy policy).
CMD ["sh", "-c", "exec uvicorn solarrt.api:app --host $SOLARRT_HOST --port $SOLARRT_PORT --proxy-headers --forwarded-allow-ips='*' --no-access-log --no-server-header"]
