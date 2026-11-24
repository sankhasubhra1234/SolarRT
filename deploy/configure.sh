#!/usr/bin/env bash
# Configure and start SolarRT on the server. Run as your normal user (not root) in this folder:
#   bash configure.sh [server-ip]
#
# - Works out the sslip.io address from the IP (detected if not given): 203.0.113.5 -> 203-0-113-5.sslip.io
# - Creates .env from .env.example on the first run (domain, allowed hosts, random admin token).
#   An existing .env is never overwritten.
# - Builds and starts the stack, then shows its status.
# The admin token is written to .env only and never printed.
set -euo pipefail
cd "$(dirname "$0")"

[[ $EUID -ne 0 ]] || { echo "Run this as your normal user, not root"; exit 1; }
command -v docker >/dev/null || { echo "Docker is not installed (run setup-server.sh first)"; exit 1; }
[[ -f .env.example ]] || { echo "Missing .env.example - upload the whole deploy/ folder"; exit 1; }

is_ipv4() {
  local ip="$1" part
  local -a parts
  [[ "$ip" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]] || return 1
  IFS=. read -r -a parts <<< "$ip"
  for part in "${parts[@]}"; do
    (( 10#$part <= 255 )) || return 1
  done
}

is_private() {
  [[ "$1" =~ ^(10\.|127\.|169\.254\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.|100\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\.) ]]
}

IP="${1:-}"
if [[ -z "$IP" ]]; then
  # The address the server uses to reach the internet; on most VPSes this is the public IP.
  IP="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i = 1; i < NF; i++) if ($i == "src") { print $(i + 1); exit }}' || true)"
  if [[ -z "$IP" ]] || is_private "$IP"; then
    IP="$(curl -fsS4 --max-time 10 https://api.ipify.org || true)"
  fi
  [[ -n "$IP" ]] || { echo "Could not detect the public IP. Run: bash configure.sh <server-ip>"; exit 1; }
  echo "==> Detected public IP $IP"
fi
is_ipv4 "$IP" || { echo "Not a valid IPv4 address: $IP"; exit 1; }

DOMAIN="${IP//./-}.sslip.io"
echo "==> Address: https://$DOMAIN"

if [[ -f .env ]]; then
  echo "==> .env already exists - leaving it unchanged"
  CURRENT="$(grep -E '^SOLARRT_DOMAIN=' .env | cut -d= -f2- || true)"
  if [[ "$CURRENT" != "$DOMAIN" ]]; then
    echo "    Note: .env has SOLARRT_DOMAIN=${CURRENT:-<empty>}, not $DOMAIN. Edit .env if that is wrong."
  fi
else
  echo "==> Creating .env (random admin token, not shown)"
  command -v openssl >/dev/null || { echo "openssl is required to generate the admin token"; exit 1; }
  umask 077
  TMP="$(mktemp .env.XXXXXX)"
  trap 'rm -f "$TMP"' EXIT
  # Values go in through the environment, so the token never appears on a command line.
  SOLARRT_NEW_DOMAIN="$DOMAIN" SOLARRT_NEW_TOKEN="$(openssl rand -hex 32)" awk '
    /^SOLARRT_DOMAIN=/        { print "SOLARRT_DOMAIN=" ENVIRON["SOLARRT_NEW_DOMAIN"]; next }
    /^SOLARRT_ALLOWED_HOSTS=/ { print "SOLARRT_ALLOWED_HOSTS=" ENVIRON["SOLARRT_NEW_DOMAIN"]; next }
    /^SOLARRT_ADMIN_TOKEN=/   { print "SOLARRT_ADMIN_TOKEN=" ENVIRON["SOLARRT_NEW_TOKEN"]; next }
    { sub(/\r$/, ""); print }
  ' .env.example > "$TMP"
  grep -qE '^SOLARRT_ADMIN_TOKEN=[0-9a-f]{64}$' "$TMP" || { echo "Failed to write the admin token"; exit 1; }
  mv "$TMP" .env
  trap - EXIT
  echo "    Read the token later with:  grep ^SOLARRT_ADMIN_TOKEN= .env"
fi

chmod 600 .env
chmod +x ./*.sh

echo "==> Building and starting (the first build takes a few minutes)"
docker compose up -d --build
docker compose ps

echo
echo "Done. Open https://$DOMAIN - the first visit can take up to a minute while Caddy gets the certificate."
