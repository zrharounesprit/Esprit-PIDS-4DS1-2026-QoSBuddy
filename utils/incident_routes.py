# ─────────────────────────────────────────────────────────────────────────────
# utils/incident_routes.py — Autopilot Incident Analysis Route
#
# POST /incident-analyze  — single CSV upload → 6-step investigation
#
# Registration:
#   from utils.incident_routes import add_incident_routes
#   add_incident_routes(app)
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from fastapi import APIRouter, UploadFile, File, HTTPException

try:
    from .incident_agent import run_incident_investigation
except ImportError:
    from utils.incident_agent import run_incident_investigation

router = APIRouter(tags=["Autopilot"])


@router.post("/incident-analyze")
async def incident_analyze(file: UploadFile = File(...)):
    """
    Upload a CESNET CSV file for a full AI-powered incident investigation.
    Runs anomaly detection, RCA, persona classification, SLA risk, and forecasting,
    then synthesises findings with Kimi K2.6.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(400, "Only CSV files are accepted.")
    try:
        csv_bytes = await file.read()
        result = run_incident_investigation(csv_bytes, file.filename)
        return result
    except Exception as e:
        raise HTTPException(500, detail=f"Investigation failed: {e}")


def add_incident_routes(app) -> None:
    app.include_router(router)
