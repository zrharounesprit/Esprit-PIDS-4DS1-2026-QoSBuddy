# ─────────────────────────────────────────────────────────────────────────────
# utils/noc_scheduler.py — APScheduler Cronjob for NOC Autopilot
#
# Runs run_noc_cycle() every NOC_INTERVAL_MINUTES (default 5).
# Stores results in noc_state.
#
# Usage (called from mcp_api.py lifespan):
#   from utils.noc_scheduler import start_noc_scheduler, stop_noc_scheduler
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import os
import threading
from datetime import datetime, timezone, timedelta

try:
    from .noc_agent import run_noc_cycle
    from .noc_state import update, push_cycle, set_phase
except ImportError:
    from utils.noc_agent import run_noc_cycle
    from utils.noc_state import update, push_cycle, set_phase

_INTERVAL = int(os.getenv("NOC_INTERVAL_MINUTES", "5"))
_timer: threading.Timer | None = None
_started = False


def _job() -> None:
    global _timer
    try:
        update({"status": "running", "error": None})
        cycle = run_noc_cycle()
        push_cycle(cycle)
        update({
            "status":        "idle",
            "last_run":      cycle.get("ts_end") or datetime.now(timezone.utc).isoformat(),
            "current_phase": None,
            "phase_detail":  None,
        })
    except Exception as e:
        update({"status": "error", "error": str(e), "current_phase": None})
    finally:
        # Reschedule
        next_dt = datetime.now(timezone.utc) + timedelta(minutes=_INTERVAL)
        update({"next_run": next_dt.isoformat()})
        _timer = threading.Timer(_INTERVAL * 60, _job)
        _timer.daemon = True
        _timer.start()


def start_noc_scheduler() -> None:
    global _timer, _started
    if _started:
        return
    _started = True
    # Run first cycle after 10 seconds to let the app finish starting
    next_dt = datetime.now(timezone.utc) + timedelta(seconds=10)
    update({"next_run": next_dt.isoformat(), "status": "idle"})
    _timer = threading.Timer(10, _job)
    _timer.daemon = True
    _timer.start()
    print(f"✅ NOC Autopilot scheduler started — interval={_INTERVAL}m")


def stop_noc_scheduler() -> None:
    global _timer, _started
    _started = False
    if _timer:
        _timer.cancel()
        _timer = None
    print("🛑 NOC Autopilot scheduler stopped.")
