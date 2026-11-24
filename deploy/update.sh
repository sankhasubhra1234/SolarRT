#!/usr/bin/env bash
# Rebuild and restart SolarRT after uploading new code. Run on the server in the deploy/ folder:
#   ./update.sh
set -euo pipefail
cd "$(dirname "$0")"
[[ -f .env ]] || { echo "Missing .env (copy .env.example and edit it)"; exit 1; }

./backup.sh                                   # safety copy of feedback first
docker compose build --pull app               # also picks up security fixes in the base image
docker compose up -d
docker image prune -f >/dev/null
sleep 5
docker compose ps
echo "Health: $(curl -fsS "https://$(grep ^SOLARRT_DOMAIN= .env | cut -d= -f2)/api/health" || echo 'NOT RESPONDING')"
