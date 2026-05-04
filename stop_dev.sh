#!/usr/bin/env bash
# ============================================================
#  QoSBuddy — Stop all dev services started by start_dev.sh
# ============================================================

PID_FILE="$(cd "$(dirname "$0")" && pwd)/.dev_pids"

if [ ! -f "$PID_FILE" ]; then
  echo "No .dev_pids file found. Nothing to stop."
  exit 0
fi

echo "Stopping QoSBuddy dev services..."

while read -r pid name; do
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid"
    echo "  Stopped $name (PID $pid)"
  else
    echo "  $name (PID $pid) was already stopped"
  fi
done < "$PID_FILE"

rm -f "$PID_FILE"
echo "Done."
