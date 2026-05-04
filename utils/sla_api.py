# ─────────────────────────────────────────────────────────────────────────────
# sla_api.py — SLA XGBoost API  (inference + built-in feature engineering)
#
# The frontend sends raw CESNET hourly rows. This API:
#   1. Optionally merges with times_1_hour.csv rows (if id_time column present)
#   2. Runs the full feature engineering pipeline (sla_pipeline.py)
#   3. Predicts with the trained XGBoost model
#
# Artifacts:
#   artifacts/sla_xgboost_model.json
#   artifacts/sla_xgboost_model_config.pkl  → feature_cols, optimal_threshold
#
# Run:
#   uvicorn utils.sla_api:app --host 127.0.0.1 --port 8003
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import os
import pickle
import warnings
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import xgboost as xgb
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

warnings.filterwarnings("ignore")

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Import sibling pipeline modules — works when run as `uvicorn utils.sla_api:app`
try:
    from .sla_pipeline import engineer_sla_features
    from .sla_preprocess import merge_cesnet_times_1h, df_has_resolvable_clock, ensure_subnet_key
except ImportError:
    # Fallback for direct execution
    import sys
    sys.path.insert(0, _REPO_ROOT)
    from utils.sla_pipeline import engineer_sla_features
    from utils.sla_preprocess import merge_cesnet_times_1h, df_has_resolvable_clock, ensure_subnet_key

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


app = FastAPI(title="QoSBuddy SLA API", version="4.0.0", lifespan=_lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _require_ready():
    if not STATE["ready"]:
        raise HTTPException(503, detail=STATE.get("error") or "Not ready.")


class PredictBody(BaseModel):
    rows: List[Dict[str, object]] = Field(..., min_length=1)
    input_row_count: int = Field(..., ge=1)
    # Optional: rows from times_1_hour.csv — needed when the dataset uses id_time
    # instead of real timestamps. The API will merge on id_time automatically.
    times_rows: Optional[List[Dict[str, object]]] = None


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

    # ── Step 1: Build DataFrame from raw rows ─────────────────────────────────
    df = pd.DataFrame(body.rows)

    # Assign __row_id before any merging/reindexing so we can map results back
    if "__row_id" not in df.columns:
        df["__row_id"] = range(len(df))

    # ── Step 2: Merge with times_1_hour.csv if provided ───────────────────────
    if body.times_rows:
        try:
            times_df = pd.DataFrame(body.times_rows)
            df = merge_cesnet_times_1h(df, times_df)
        except ValueError as e:
            raise HTTPException(400, detail=f"Times merge error: {e}")

    # ── Step 3: Validate that we have a usable timestamp ─────────────────────
    has_clock = df_has_resolvable_clock(df)
    if not has_clock and "id_time" in df.columns and body.times_rows is None:
        raise HTTPException(
            400,
            detail=(
                "Dataset uses `id_time` (integer index) but no times_rows were provided. "
                "Please upload `times_1_hour.csv` so the API can resolve real timestamps "
                "needed for time-based SLA features (hour, dayofweek, rolling windows)."
            ),
        )
    if not has_clock and "id_time" not in df.columns:
        raise HTTPException(
            400,
            detail=(
                "No timestamp column found. "
                "CSV must include `datetime`, `timestamp`, `time`, "
                "or `id_time` + the matching `times_1_hour.csv`."
            ),
        )

    # ── Step 4: Ensure a group/series key exists ──────────────────────────────
    # engineer_sla_features() needs subnet_id or id_ip to group rolling windows.
    # If the CSV has neither, treat all rows as one series with key "default".
    df = ensure_subnet_key(df, "default")

    # ── Step 5: Run feature engineering pipeline ──────────────────────────────
    try:
        df_eng = engineer_sla_features(df, feature_cols)
    except ValueError as e:
        raise HTTPException(400, detail=f"Feature engineering error: {e}")

    if df_eng.empty:
        raise HTTPException(
            400,
            detail=(
                "All rows were dropped during feature engineering (NaN warmup). "
                "Send at least 24 consecutive hourly rows for the same subnet/IP."
            ),
        )

    # ── Step 6: Predict ───────────────────────────────────────────────────────
    df_eng = df_eng.replace([np.inf, -np.inf], np.nan).dropna(subset=feature_cols)
    if df_eng.empty:
        raise HTTPException(400, detail="All rows NaN after final cleanup.")

    X = df_eng[feature_cols].to_numpy(dtype=np.float64)
    proba = model.predict_proba(X)[:, 1]

    scored: dict[int, dict] = {}
    for i, rid in enumerate(df_eng["__row_id"].tolist()):
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

    # ── Step 7: Build output aligned to original row count ────────────────────
    results = []
    skipped = 0
    for rid in range(n_in):
        if rid in scored:
            results.append(scored[rid])
        else:
            skipped += 1
            results.append({
                "row_id": rid,
                "probability": None,
                "sla_violation": None,
                "severity": None,
                "recommendation": None,
                "report": None,
                "skipped": True,
                "reason": "Dropped during feature engineering (warmup / NaN).",
            })

    return {
        "optimal_threshold": threshold,
        "rows_input": n_in,
        "rows_scored": len(df_eng),
        "rows_skipped": skipped,
        "results": results,
    }
