# Override PYTHON_IMAGE with a verified digest for release.
ARG PYTHON_IMAGE=python:3.13-slim
FROM ${PYTHON_IMAGE} AS builder
WORKDIR /build
COPY deploy/requirements-web.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements-web.txt

FROM ${PYTHON_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    SOLARRT_HOST=0.0.0.0 SOLARRT_PORT=8000 \
    SOLARRT_DATA_DIR=/data SOLARRT_ENABLE_DOCS=0

WORKDIR /app
COPY --from=builder /install/ /usr/local/
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
