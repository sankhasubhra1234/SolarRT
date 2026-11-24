#!/usr/bin/env bash
# Copy the feedback file out of the Docker volume into ~/solarrt-backups (keeps the last 30).
# Add to cron for daily backups:   0 3 * * * /home/<you>/SolarRT2/deploy/backup.sh
set -euo pipefail
cd "$(dirname "$0")"
DEST="$HOME/solarrt-backups"
mkdir -p "$DEST"
chmod 700 "$DEST"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
if docker compose ps --status running app | grep -q app; then
  docker compose cp app:/data/feedback.jsonl "$DEST/feedback-$STAMP.jsonl" 2>/dev/null \
    && chmod 600 "$DEST/feedback-$STAMP.jsonl" && echo "Backed up feedback to $DEST/feedback-$STAMP.jsonl" \
    || echo "No feedback yet - nothing to back up"
fi
ls -1t "$DEST"/feedback-*.jsonl 2>/dev/null | tail -n +31 | xargs -r rm -f
