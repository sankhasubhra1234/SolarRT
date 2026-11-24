# Production image for the SolarRT website/API server (used by deploy/docker-compose.yml).
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    SOLARRT_HOST=0.0.0.0 SOLARRT_PORT=8000 \
    SOLARRT_DATA_DIR=/data SOLARRT_ENABLE_DOCS=0

WORKDIR /app
# Exact, audited versions (see requirements.txt / docs/SECURITY.md)
RUN pip install --no-cache-dir fastapi==0.163.1 "uvicorn[standard]==0.54.0" httpx==0.28.1 sgp4==2.27
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
