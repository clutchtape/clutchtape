#!/bin/sh
# Optional encrypted offsite service. Secrets belong in /config/restic.env (0600), never source control.
set -eu
set -a
. /config/restic.env
set +a
export RESTIC_REPOSITORY RESTIC_PASSWORD_FILE
while true; do
  latest=$(find /snapshots -maxdepth 1 -name 'clutchtape-????????-??????.sqlite' -type f | sort | tail -n 1)
  if [ -n "$latest" ]; then
    if restic backup --tag clutchtape "$latest" /private-data && restic check && restic forget --tag clutchtape --group-by tags --keep-within 7d --keep-last 1 --prune; then
      date -u +%s > /status/offsite-success
    else
      date -u +%s > /status/offsite-failure
    fi
  fi
  sleep 21600
done
