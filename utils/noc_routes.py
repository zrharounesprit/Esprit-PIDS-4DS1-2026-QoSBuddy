# ─────────────────────────────────────────────────────────────────────────────
# utils/noc_routes.py — FastAPI Routes for NOC Autopilot
#
# Endpoints:
#   GET  /noc/status      — live scheduler status + latest cycle summary
#   GET  /noc/history     — last N completed cycles
#   POST /noc/trigger     — manually fire one cycle right now
#
# Registration:
#   from utils.noc_routes import add_noc_routes
#   add_noc_routes(app)
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import threading
from fastapi import APIRouter, Query

try:
    from .noc_state import get_state, update, push_cycle
    from .noc_agent import run_noc_cycle
except ImportError:
    from utils.noc_state import get_state, update, push_cycle
    from utils.noc_agent import run_noc_cycle

router = APIRouter(prefix="/noc", tags=["NOC Autopilot"])


@router.get("/status")
def noc_status():
    """Return live scheduler state + the most recently completed cycle."""
    state = get_state()
    return {
        "status":        state["status"],
        "last_run":      state["last_run"],
        "next_run":      state["next_run"],
        "current_phase": state["current_phase"],
        "phase_detail":  state["phase_detail"],
        "latest_cycle":  state["latest_cycle"],
        "cycle_count":   len(state["cycles"]),
    }


@router.get("/history")
def noc_history(limit: int = Query(default=10, ge=1, le=20)):
    """Return the last `limit` completed cycles (newest first)."""
    state = get_state()
    cycles = list(reversed(state["cycles"]))[:limit]
    return {"cycles": cycles, "total": len(state["cycles"])}


@router.post("/trigger")
def noc_trigger(inject_breach: bool = False):
    """
    Manually trigger one NOC cycle asynchronously.
    Returns immediately; poll /noc/status to watch progress.
    """
    state = get_state()
    if state["status"] == "running":
        return {"queued": False, "message": "A cycle is already running."}

    def _run():
        try:
            update({"status": "running", "error": None})
            cycle = run_noc_cycle(inject_breach=inject_breach)
            push_cycle(cycle)
            update({"status": "idle", "current_phase": None, "phase_detail": None,
                    "last_run": cycle.get("ts_end")})
        except Exception as e:
            update({"status": "error", "error": str(e), "current_phase": None})

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return {
        "queued": True,
        "message": f"NOC cycle triggered (inject_breach={inject_breach}). Poll /noc/status.",
    }


def add_noc_routes(app) -> None:
    app.include_router(router)
