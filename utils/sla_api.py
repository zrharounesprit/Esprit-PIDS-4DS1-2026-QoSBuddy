# ─────────────────────────────────────────────────────────────────────────────
# sla_api.py — SLA violation detection API (FastAPI)
#
# Run (from repo root):
#   uvicorn utils.sla_api:app --host 127.0.0.1 --port 8003
#
# Place trained artifacts next to the anomaly models:
#   artifacts/sla_model.pkl          (required)
#   artifacts/sla_scaler.pkl         (optional; skipped if missing)
#
# Supports the same row features as the dashboard CSV / anomaly flow.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import os
import warnings
from typing import Any

import joblib
import shap
from fastapi import FastAPI
from pydantic import BaseModel
from sklearn.ensemble import IsolationForest

warnings.filterwarnings("ignore")

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ARTIFACTS = os.path.join(_REPO_ROOT, "artifacts")

app = FastAPI(title="QoSBuddy SLA API", version="1.0.0")


class Observation(BaseModel):
    n_bytes: float
    n_packets: float
    n_flows: float
    tcp_udp_ratio_packets: float
    dir_ratio_packets: float


def _load_optional_scaler():
    path = os.path.join(_ARTIFACTS, "sla_scaler.pkl")
    if os.path.isfile(path):
        return joblib.load(path)
    return None


model = joblib.load(os.path.join(_ARTIFACTS, "sla_model.pkl"))
scaler = _load_optional_scaler()

_explainer = None


def _get_explainer():
    global _explainer
    if _explainer is not None:
        return _explainer
    try:
        _explainer = shap.TreeExplainer(model)
    except Exception:
        _explainer = False  # type: ignore[assignment]
    return _explainer


def process_observation(obs_dict: dict) -> tuple[float, Any, Any, Any]:
    import pandas as pd

    df = pd.DataFrame([obs_dict])
    X = scaler.transform(df) if scaler is not None else df.values
    X_scaled = X  # name kept for parity with anomaly_api

    if isinstance(model, IsolationForest):
        score = float(model.decision_function(X_scaled)[0])
        label = model.predict(X_scaled)[0]
    elif hasattr(model, "predict_proba"):
        proba = model.predict_proba(X_scaled)[0]
        label = model.predict(X_scaled)[0]
        score = float(max(proba))
    else:
        label = model.predict(X_scaled)[0]
        score = float(label)

    return score, label, df, X_scaled


def _is_violation(label: Any) -> bool:
    if isinstance(model, IsolationForest):
        return label == -1
    return bool(label == 1 or label is True)


def get_explanation(df, X_scaled) -> dict:
    explainer = _get_explainer()
    if explainer in (None, False):
        return {}

    shap_values = explainer.shap_values(X_scaled)
    row = shap_values[0] if isinstance(shap_values, list) else shap_values[0]
    return dict(zip(df.columns, row))


def compute_severity(score: float, obs: dict) -> str:
    severity = abs(score) * 10 + obs["n_bytes"] / 1e7
    if severity > 15:
        return "HIGH"
    if severity > 8:
        return "MEDIUM"
    return "LOW"


def generate_recommendation(contributions: dict) -> str:
    if not contributions:
        return "Review traffic against your SLA thresholds and capacity plans."

    top_feature = max(contributions, key=lambda k: abs(contributions[k]))
    findings: list[str] = []

    if top_feature in ["n_bytes", "n_packets"]:
        findings.append(
            "Heavy volume may breach throughput or utilization SLAs — "
            "consider shaping, QoS, or scaling."
        )
    if top_feature == "dir_ratio_packets":
        findings.append("Asymmetric traffic can stress uplinks or NAT paths tied to SLA paths.")
    if top_feature == "tcp_udp_ratio_packets":
        findings.append("Unusual TCP/UDP mix can correlate with real-time or DNS-like patterns affecting latency SLAs.")
    if top_feature == "n_flows":
        findings.append("High flow count can indicate fan-out that strains state tables and delay-sensitive traffic.")

    if not findings:
        findings.append("Monitor baseline versus contracted SLA metrics (latency, loss, jitter).")
    return "\n".join(findings)


def generate_report(violation: bool, severity: str, contributions: dict, recommendation: str) -> str:
    if not violation:
        return "No SLA risk signal detected for this observation under the current model."

    if contributions:
        top_features = sorted(contributions.items(), key=lambda x: abs(x[1]), reverse=True)[:2]
        explanation = ", ".join([f"{f}" for f, _ in top_features])
    else:
        explanation = "model drivers not available (non-tree model or SHAP unavailable)"

    return f"""
An SLA-related risk signal was raised for this traffic profile.

Severity: {severity}

Main contributing factors: {explanation}

Recommended action: {recommendation}
"""


@app.post("/predict_sla")
def predict_sla(obs: Observation):
    obs_dict = obs.model_dump()
    score, label, df, X_scaled = process_observation(obs_dict)
    violation = _is_violation(label)

    if not violation:
        return {
            "sla_violation": False,
            "message": "Within expected profile for SLA monitoring",
        }

    contributions = get_explanation(df, X_scaled)
    severity = compute_severity(score, obs_dict)
    recommendation = generate_recommendation(contributions)
    report = generate_report(violation, severity, contributions, recommendation)

    return {
        "sla_violation": True,
        "severity": severity,
        "score": score,
        "contributions": contributions,
        "recommendation": recommendation,
        "report": report,
    }
