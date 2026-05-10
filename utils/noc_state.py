# ─────────────────────────────────────────────────────────────────────────────
# utils/noc_state.py — Shared in-memory state for the NOC Autopilot
#
# Thread-safe store for scheduler → route communication.
# Holds the last 20 completed cycles + live status of the running cycle.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import threading
from typing import Any, Optional

_lock = threading.Lock()

_STATE: dict[str, Any] = {
    # Scheduler lifecycle
    "status":        "idle",          # "idle" | "running" | "error"
    "last_run":      None,            # ISO string
    "next_run":      None,            # ISO string
    "error":         None,            # last error message if status == "error"

    # Live phase of the active cycle (updated during the run)
    "current_phase": None,            # "OBSERVE" | "ATTRIBUTE" | ... | "SYNTHESIZE"
    "phase_detail":  None,            # short human-readable detail

    # History
    "cycles":        [],              # list[dict] — last 20 completed cycles
    "latest_cycle":  None,            # most recently completed cycle
}

MAX_HISTORY = 20


def get_state() -> dict:
    with _lock:
        return dict(_STATE)


def update(patch: dict) -> None:
    with _lock:
        _STATE.update(patch)


def push_cycle(cycle: dict) -> None:
    """Append a completed cycle to the history ring buffer."""
    with _lock:
        _STATE["cycles"].append(cycle)
        if len(_STATE["cycles"]) > MAX_HISTORY:
            _STATE["cycles"] = _STATE["cycles"][-MAX_HISTORY:]
        _STATE["latest_cycle"] = cycle


def set_phase(phase: str, detail: str = "") -> None:
    with _lock:
        _STATE["current_phase"] = phase
        _STATE["phase_detail"] = detail
