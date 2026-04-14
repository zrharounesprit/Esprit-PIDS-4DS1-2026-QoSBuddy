# ─────────────────────────────────────────────────────────────────────────────
# sla_api.py — SLA XGBoost API (inference only, no scaling)
#
# XGBoost was trained on RAW (unscaled) feature_cols in the notebook.
# The saved scaler was only used for Logistic Regression.
# So: engineered features → predict_proba directly (NO scaler.transform).
#
# Artifacts:
#   artifacts/sla_xgboost_model.json
#   artifacts/sla_xgboost_model_config.pkl → feature_cols, optimal_threshold
#
# Run:  .\.venv\Scripts\uvicorn.exe utils.sla_api:app --host 127.0.0.1 --port 8003
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import os
import pickle
import warnings
from contextlib import asynccontextmanager
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import xgboost as xgb
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

warnings.filterwarnings("ignore")

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STATE: dict[str, Any] = {
    "ready": False,
    "error": None,
    "model": None,
    "feature_cols": None,
    "optimal_threshold": None,
}


def _resolve(rel: str) -> str:
    return os.path.normpath(os.path.join(_REPO_ROOT, rel))


def _severity_from_proba(p: float, threshold: float) -> str:
    if p >= min(0.95, threshold + 0.35):
        return "HIGH"
    if p >= threshold + 0.12:
        return "MEDIUM"
    return "LOW"


def _recommendation(p: float, threshold: float) -> str:
    if p >= threshold:
        return (
            f"Breach probability {p:.3f} >= threshold {threshold:.3f}. "
            "Review capacity, QoS policies, and heavy hitters."
        )
    return f"Probability {p:.3f} < threshold {threshold:.3f}. Within normal range."


def _report(violation: bool, p: float, threshold: float, severity: str) -> str:
    if not violation:
        return f"No SLA breach signal. Probability: {p:.3f}, threshold: {threshold:.3f}."
    return (
        f"SLA BREACH DETECTED\n"
        f"Probability: {p:.3f}\nThreshold: {threshold:.3f}\nSeverity: {severity}\n\n"
        f"Action: Review capacity, QoS, and heavy hitters (bytes/flows/asymmetry)."
    )


def _init_sla() -> None:
    STATE["ready"] = False
    STATE["error"] = None
    STATE["model"] = None
    STATE["feature_cols"] = None
    STATE["optimal_threshold"] = None

    model_path = _resolve(os.environ.get("SLA_MODEL_JSON", "artifacts/sla_xgboost_model.json"))
    cfg_path = _resolve(os.environ.get("SLA_CONFIG_PKL", "artifacts/sla_xgboost_model_config.pkl"))

    try:
        if not os.path.isfile(model_path):
            STATE["error"] = f"XGBoost JSON not found: {model_path}"
            return
        if not os.path.isfile(cfg_path):
            STATE["error"] = f"Config pickle not found: {cfg_path}"
            return

        with open(cfg_path, "rb") as f:
            cfg = pickle.load(f)

        feature_cols = cfg.get("feature_cols")
        if not feature_cols:
            STATE["error"] = "Pickle missing `feature_cols`."
            return

        threshold = cfg.get("optimal_threshold")
        if threshold is None:
            STATE["error"] = "Pickle missing `optimal_threshold`."
            return

        clf = xgb.XGBClassifier()
        clf.load_model(model_path)

        STATE["model"] = clf
        STATE["feature_cols"] = list(feature_cols)
        STATE["optimal_threshold"] = float(threshold)
        STATE["ready"] = True
        print(f"SLA model loaded: {len(feature_cols)} features, threshold={threshold:.4f}")
    except Exception as e:
        STATE["error"] = f"Failed to load: {e}"


@asynccontextmanager
async def _lifespan(app: FastAPI):
    _init_sla()
    yield


app = FastAPI(title="QoSBuddy SLA API", version="3.0.0", lifespan=_lifespan)


def _require_ready():
    if not STATE["ready"]:
        raise HTTPException(503, detail=STATE.get("error") or "Not ready.")


class PredictBody(BaseModel):
    rows: List[Dict[str, object]] = Field(..., min_length=1)
    input_row_count: int = Field(..., ge=1)


@app.get("/sla_metadata")
def sla_metadata():
    return {
        "ready": STATE["ready"],
        "error": STATE.get("error"),
        "feature_columns": STATE.get("feature_cols") or [],
        "optimal_threshold": STATE.get("optimal_threshold"),
    }


@app.get("/health")
def health():
    return {"ready": STATE["ready"], "error": STATE.get("error")}


@app.post("/predict_sla")
def predict_sla(body: PredictBody):
    _require_ready()
    model = STATE["model"]
    feature_cols = STATE["feature_cols"]
    threshold = STATE["optimal_threshold"]
    n_in = body.input_row_count

    df = pd.DataFrame(body.rows)
    missing = [c for c in feature_cols if c not in df.columns]
    if missing:
        raise HTTPException(400, detail=f"Missing columns: {missing}")
    if "__row_id" not in df.columns:
        raise HTTPException(400, detail="Rows must include `__row_id`.")

    df = df.replace([np.inf, -np.inf], np.nan).dropna(subset=feature_cols)
    if df.empty:
        raise HTTPException(400, detail="All rows NaN after cleanup.")

    X = df[feature_cols].to_numpy(dtype=np.float64)
    proba = model.predict_proba(X)[:, 1]

    scored = {}
    for i, rid in enumerate(df["__row_id"].tolist()):
        p = float(proba[i])
        violation = p >= threshold
        severity = _severity_from_proba(p, threshold)
        scored[int(rid)] = {
            "row_id": int(rid),
            "probability": p,
            "sla_violation": violation,
            "severity": severity,
            "recommendation": _recommendation(p, threshold),
            "report": _report(violation, p, threshold, severity),
        }

    results = []
    skipped = 0
    for rid in range(n_in):
        if rid in scored:
            results.append(scored[rid])
        else:
            skipped += 1
            results.append({
                "row_id": rid, "probability": None, "sla_violation": None,
                "severity": None, "recommendation": None, "report": None,
                "skipped": True, "reason": "Dropped during feature engineering (warmup/NaN).",
            })

    return {
        "optimal_threshold": threshold,
        "rows_input": n_in,
        "rows_scored": len(df),
        "rows_skipped": skipped,
        "results": results,
    }
