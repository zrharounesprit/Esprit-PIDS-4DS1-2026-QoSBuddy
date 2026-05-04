#!/usr/bin/env bash
# ============================================================
#  QoSBuddy — Dev Start Script (Linux / macOS)
#  Runs all services as background processes and writes
#  their PIDs to .dev_pids so you can stop them cleanly.
#
#  Start:  ./start_dev.sh
#  Stop:   ./stop_dev.sh
# ============================================================

set -e

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$REPO_ROOT/.venv/bin/activate"
LOG_DIR="$REPO_ROOT/.dev_logs"
PID_FILE="$REPO_ROOT/.dev_pids"

mkdir -p "$LOG_DIR"
> "$PID_FILE"   # clear old PIDs

# Helper — starts a uvicorn service in the background
start_service() {
  local name="$1"
  local module="$2"
  local port="$3"

  echo "  Starting $name on port $port..."
  (
    source "$VENV"
    cd "$REPO_ROOT"
    uvicorn "$module" --host 127.0.0.1 --port "$port" --reload \
      > "$LOG_DIR/${name}.log" 2>&1
  ) &
  echo "$! $name" >> "$PID_FILE"
}

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║         QoSBuddy Dev Stack               ║"
echo "╚══════════════════════════════════════════╝"
echo ""

start_service "persona"     "main:app"                    8000
start_service "anomaly"     "utils.anomaly_api:app"       8001
start_service "rca"         "utils.main_RCA:app"          8002
start_service "sla"         "utils.sla_api:app"           8003
start_service "forecasting" "utils.forecasting_api:app"   8004
start_service "mcp_sim"     "utils.mcp_api:app"           8005

echo "  Starting React frontend on port 3000..."
(
  cd "$REPO_ROOT/frontend"
  npm run dev > "$LOG_DIR/frontend.log" 2>&1
) &
echo "$! frontend" >> "$PID_FILE"

echo ""
echo "  All services started."
echo ""
echo "  Persona Classification  ->  http://127.0.0.1:8000"
echo "  Anomaly Detection       ->  http://127.0.0.1:8001"
echo "  Root Cause Analysis     ->  http://127.0.0.1:8002"
echo "  SLA Detection           ->  http://127.0.0.1:8003"
echo "  Traffic Forecasting     ->  http://127.0.0.1:8004"
echo "  MCP / Simulation        ->  http://127.0.0.1:8005"
echo "  React Frontend          ->  http://localhost:3000"
echo ""
echo "  Logs -> .dev_logs/"
echo "  Run ./stop_dev.sh to stop all services."
echo ""
