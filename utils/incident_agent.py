# ─────────────────────────────────────────────────────────────────────────────
# utils/incident_agent.py — Autopilot Multi-Model Investigation Engine
#
# run_incident_investigation(csv_bytes, filename) → dict
#
# Pipeline:
#   Step 1: Anomaly Detection   (port 8001)
#   Step 2: Root Cause Analysis (port 8002)
#   Step 3: Persona Classification (port 8000)
#   Step 4: SLA Risk            (port 8003)
#   Step 5: Traffic Forecast    (port 8004)
#   Step 6: Kimi K2.6 Synthesis
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import io
import json
import os
import traceback
from typing import Any

import httpx
import numpy as np
import pandas as pd

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ANOMALY_API  = "http://127.0.0.1:8001"
RCA_API      = "http://127.0.0.1:8002"
PERSONA_API  = "http://127.0.0.1:8000"
SLA_API      = "http://127.0.0.1:8003"
FORECAST_API = "http://127.0.0.1:8004"

MOONSHOT_KEY = os.getenv("MOONSHOT_API_KEY", "")
KIMI_MODEL   = "kimi-k2.6"
KIMI_BASE    = "https://api.moonshot.ai/v1"

TIMEOUT_SHORT  = 10
TIMEOUT_MEDIUM = 30
TIMEOUT_LONG   = 60
MAX_ANOMALY_ROWS = 15
SEQ_LEN = 24   # LSTM requires exactly 24 rows


def _post(url: str, payload: Any, timeout: int = 20) -> dict:
    try:
        r = httpx.post(url, json=payload, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code}: {e.response.text[:300]}"}
    except Exception as e:
        return {"error": str(e)}


def _read_csv(csv_bytes: bytes) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(csv_bytes))


def _compute_severity(steps: list) -> str:
    breach = next((s for s in steps if s["step"] == "SLA Risk"), None)
    anomaly = next((s for s in steps if s["step"] == "Anomaly Detection"), None)
    breach_found = breach and breach.get("data", {}).get("breach_detected")
    anomaly_count = (anomaly or {}).get("data", {}).get("anomaly_count", 0)
    if breach_found and anomaly_count > 3:
        return "CRITICAL"
    if breach_found:
        return "HIGH"
    if anomaly_count > 0:
        return "MEDIUM"
    return "LOW"


# ── Step 1: Anomaly Detection ─────────────────────────────────────────────────

def _step_anomaly(df: pd.DataFrame) -> dict:
    step = {"step": "Anomaly Detection", "icon": "⚡", "status": "ok", "summary": "", "data": {}}
    cols_needed = ["n_flows", "n_packets", "n_bytes", "avg_duration",
                   "avg_ttl", "tcp_udp_ratio_packets", "dir_ratio_packets"]
    available = [c for c in cols_needed if c in df.columns]
    if not available:
        step["status"] = "warn"
        step["summary"] = "Required anomaly columns not found."
        return step

    sample = df[available].dropna().tail(MAX_ANOMALY_ROWS)
    payload_rows = []
    for i, row in enumerate(sample.to_dict(orient="records")):
        entry = {"id_ip": int(df.get("id_time", pd.Series([i])).iloc[i] if "id_time" in df.columns else i)}
        for c in available:
            entry[c] = float(row.get(c, 0))
        payload_rows.append(entry)

    resp = _post(f"{ANOMALY_API}/predict_anomaly", {"data": payload_rows}, TIMEOUT_SHORT)
    if "error" in resp:
        step["status"] = "warn"
        step["summary"] = f"Anomaly API: {resp['error']}"
        return step

    preds = resp.get("predictions", resp.get("results", []))
    anomaly_count = 0
    if isinstance(preds, list):
        anomaly_count = sum(
            1 for p in preds
            if (p.get("anomaly") or p.get("is_anomaly") or
                p.get("label") == -1 or p.get("prediction") == -1)
        )
    step["data"] = {"anomaly_count": anomaly_count, "total_sampled": len(payload_rows)}
    if anomaly_count > 0:
        step["status"] = "warn"
        step["summary"] = (
            f"⚠ {anomaly_count}/{len(payload_rows)} sampled flows flagged as anomalous. "
            "Possible DDoS, heavy hitters, or unusual traffic patterns."
        )
    else:
        step["summary"] = f"No anomalies detected in {len(payload_rows)} sampled flows."
    return step


# ── Step 2: Root Cause Analysis ───────────────────────────────────────────────

def _step_rca(df: pd.DataFrame) -> dict:
    step = {"step": "Root Cause Analysis", "icon": "🔬", "status": "ok", "summary": "", "data": {}}
    if "id_ip" not in df.columns:
        step["status"] = "info"
        step["summary"] = "No id_ip column — RCA skipped (requires per-IP data)."
        return step

    sample_ip = str(df["id_ip"].iloc[0])
    row_data = df.head(5).to_dict(orient="records")

    resp = _post(f"{RCA_API}/rca",
                 {"ip": sample_ip, "data": row_data},
                 TIMEOUT_MEDIUM)
    if "error" in resp:
        step["status"] = "warn"
        step["summary"] = f"RCA API: {resp['error']}"
        return step

    cluster = resp.get("cluster", resp.get("cluster_label", "N/A"))
    description = resp.get("description", resp.get("label", ""))
    step["data"] = {"cluster": cluster, "description": description}
    step["summary"] = f"IP cluster: {cluster}. {description}"
    return step


# ── Step 3: Persona Classification ───────────────────────────────────────────

def _step_persona(df: pd.DataFrame) -> dict:
    step = {"step": "Persona Classification", "icon": "👥", "status": "ok", "summary": "", "data": {}}
    row = df.dropna().head(1)
    if row.empty:
        step["status"] = "warn"
        step["summary"] = "No valid rows for persona classification."
        return step

    payload = row.to_dict(orient="records")
    resp = _post(f"{PERSONA_API}/classify_content", payload, TIMEOUT_SHORT)
    if "error" in resp:
        step["status"] = "warn"
        step["summary"] = f"Persona API: {resp['error']}"
        return step

    persona = resp.get("persona", resp.get("label", resp.get("class", "Unknown")))
    confidence = resp.get("confidence", resp.get("probability", None))
    conf_str = f" (confidence: {confidence:.1%})" if isinstance(confidence, float) else ""
    step["data"] = {"persona": persona, "confidence": confidence}
    step["summary"] = f"Dominant user persona: {persona}{conf_str}."
    return step


# ── Step 4: SLA Risk ──────────────────────────────────────────────────────────

def _step_sla(df: pd.DataFrame) -> dict:
    step = {"step": "SLA Risk", "icon": "🛡", "status": "ok", "summary": "", "data": {}}
    has_times = "id_time" in df.columns
    times_rows = None

    if has_times:
        from datetime import datetime, timezone, timedelta
        base_dt = datetime(2023, 10, 9, 0, 0, 0, tzinfo=timezone.utc)
        id_times = df["id_time"].tolist()
        times_rows = [
            {"id_time": int(it), "time": (base_dt + timedelta(hours=int(it))).isoformat()}
            for it in id_times
        ]

    payload = {
        "rows": df.to_dict(orient="records"),
        "input_row_count": len(df),
    }
    if times_rows:
        payload["times_rows"] = times_rows

    resp = _post(f"{SLA_API}/predict_sla", payload, TIMEOUT_MEDIUM)
    if "error" in resp:
        step["status"] = "warn"
        step["summary"] = f"SLA API: {resp['error']}"
        return step

    results = resp.get("results", [])
    probs = [r.get("probability") or 0.0 for r in results if r.get("probability") is not None]
    violations = [r for r in results if r.get("sla_violation")]
    max_prob = max(probs) if probs else 0.0
    avg_prob = float(np.mean(probs)) if probs else 0.0
    breach_detected = len(violations) > 0
    severity = violations[0].get("severity", "LOW") if violations else "LOW"

    step["data"] = {
        "breach_detected": breach_detected,
        "violation_count": len(violations),
        "max_probability": round(max_prob, 4),
        "avg_probability": round(avg_prob, 4),
        "severity": severity,
        "threshold": resp.get("optimal_threshold", 0.8233),
    }

    if breach_detected:
        step["status"] = "warn"
        step["summary"] = (
            f"⚠ SLA breach risk detected. "
            f"Max probability: {max_prob:.3f} — {len(violations)} violation(s). "
            f"Severity: {severity}."
        )
    else:
        step["summary"] = (
            f"No SLA breach detected. "
            f"Max probability: {max_prob:.3f} (threshold {resp.get('optimal_threshold', 0.8233):.4f})."
        )
    return step


# ── Step 5: Traffic Forecast ──────────────────────────────────────────────────

def _step_forecast(df: pd.DataFrame) -> dict:
    step = {"step": "Traffic Forecast", "icon": "📈", "status": "ok", "summary": "", "data": {}}
    if len(df) < SEQ_LEN:
        step["status"] = "info"
        step["summary"] = (
            f"Forecast skipped — requires ≥{SEQ_LEN} rows, got {len(df)}."
        )
        return step

    rows = df[["n_bytes"] if "n_bytes" in df.columns else df.columns[:1]].tail(SEQ_LEN)
    n_bytes_col = "n_bytes" if "n_bytes" in df.columns else df.columns[0]
    rows_payload = [{"n_bytes": float(v)} for v in df[n_bytes_col].tail(SEQ_LEN)]

    resp = _post(f"{FORECAST_API}/forecast",
                 {"rows": rows_payload, "ip_id": 0},
                 TIMEOUT_LONG)
    if "error" in resp:
        step["status"] = "warn"
        step["summary"] = f"Forecast API: {resp['error']}"
        return step

    forecast = resp.get("forecast", [])
    if not forecast:
        step["status"] = "warn"
        step["summary"] = "Forecast returned empty result."
        return step

    first_val = float(forecast[0]) if not isinstance(forecast[0], dict) else float(forecast[0].get("predicted_bytes", 0))
    last_val = float(forecast[-1]) if not isinstance(forecast[-1], dict) else float(forecast[-1].get("predicted_bytes", 0))
    trend = "↑ increasing" if last_val > first_val * 1.05 else ("↓ decreasing" if last_val < first_val * 0.95 else "→ stable")
    unit = resp.get("unit", "n_bytes")

    step["data"] = {
        "horizon": resp.get("horizon", len(forecast)),
        "first_forecast": first_val,
        "last_forecast": last_val,
        "trend": trend,
        "unit": unit,
    }
    step["summary"] = (
        f"Next {len(forecast)}-hour {unit} forecast: "
        f"{first_val/1e9:.2f}GB → {last_val/1e9:.2f}GB. Trend: {trend}."
    )
    return step


# ── Step 6: Kimi K2.6 Synthesis ───────────────────────────────────────────────

def _kimi_synthesis(steps: list, df: pd.DataFrame, severity: str) -> dict:
    if not MOONSHOT_KEY:
        return _rule_based_synthesis(steps, severity)

    steps_text = "\n".join(
        f"  {s['step']}: {s['summary']}" for s in steps
    )
    n_rows = len(df)
    prompt = f"""You are QoSBuddy Autopilot. Analyse the following network incident findings and produce a structured JSON report.

=== DATASET ===
Rows: {n_rows}
Overall Severity: {severity}

=== FINDINGS FROM 5 AI MODELS ===
{steps_text}

Produce JSON with exactly these fields:
{{
  "executive_summary": "<2-3 sentences describing what happened and the overall risk level>",
  "root_cause": "<most likely technical root cause>",
  "business_impact": "<impact on users and services if unaddressed>",
  "recommendations": [
    "<action 1>",
    "<action 2>",
    "<action 3>",
    "<action 4>"
  ]
}}
JSON only, no markdown."""

    try:
        from openai import OpenAI
        client = OpenAI(api_key=MOONSHOT_KEY, base_url=KIMI_BASE)
        response = client.chat.completions.create(
            model=KIMI_MODEL,
            messages=[
                {"role": "system", "content": "You are a network operations AI assistant. Be concise and data-driven."},
                {"role": "user",   "content": prompt},
            ],
            max_tokens=900,
            temperature=0.25,
        )
        content = response.choices[0].message.content.strip()
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                parsed = json.loads(content[start:end])
                parsed["source"] = "kimi-k2.6"
                return parsed
        except Exception:
            pass
        return {
            "source": "kimi-k2.6",
            "executive_summary": content[:600],
            "root_cause": "See summary.",
            "business_impact": "See summary.",
            "recommendations": [],
        }
    except Exception as e:
        return _rule_based_synthesis(steps, severity, note=str(e))


def _rule_based_synthesis(steps: list, severity: str, note: str = "") -> dict:
    sla_step = next((s for s in steps if s["step"] == "SLA Risk"), {})
    anom_step = next((s for s in steps if s["step"] == "Anomaly Detection"), {})
    fore_step = next((s for s in steps if s["step"] == "Traffic Forecast"), {})
    breach = sla_step.get("data", {}).get("breach_detected", False)
    anom_count = anom_step.get("data", {}).get("anomaly_count", 0)
    trend = fore_step.get("data", {}).get("trend", "stable")
    source = f"rule-based" + (f" (Kimi K2.6 unavailable: {note})" if note else "")

    summary = (
        f"Analysis of this dataset shows {severity} severity. "
        f"{'SLA breach risk detected. ' if breach else 'No SLA breach detected. '}"
        f"{'Anomalous flows present indicating unusual traffic. ' if anom_count else ''}"
        f"Traffic trend: {trend}."
    )
    return {
        "source": source,
        "executive_summary": summary,
        "root_cause": (
            "Elevated byte-rate volume driving SLA risk. "
            "n_bytes_peak_ratio is the dominant SLA risk factor (66% feature importance)."
            if breach else "Traffic within normal operational parameters."
        ),
        "business_impact": (
            "Risk of latency degradation and SLA violations for premium subscribers."
            if breach else "No immediate business impact."
        ),
        "recommendations": [
            "Monitor n_bytes_peak_ratio — trigger alert above 1.3.",
            "Investigate top-N source IPs for heavy-hitter traffic.",
            "Review QoS policies for peak-hour traffic shaping.",
            "Consider temporary burst capacity increase if trend continues upward.",
        ],
    }


# ── Entry Point ───────────────────────────────────────────────────────────────

def run_incident_investigation(csv_bytes: bytes, filename: str) -> dict:
    """Run a complete 6-step investigation on a CSV upload."""
    try:
        df = _read_csv(csv_bytes)
    except Exception as e:
        return {"error": f"Failed to parse CSV: {e}", "steps": [], "severity": "LOW"}

    steps = []
    step_funcs = [
        _step_anomaly,
        _step_rca,
        _step_persona,
        _step_sla,
        _step_forecast,
    ]
    for fn in step_funcs:
        try:
            result = fn(df)
        except Exception as e:
            result = {
                "step": fn.__name__.replace("_step_", "").replace("_", " ").title(),
                "icon": "⚠",
                "status": "error",
                "summary": traceback.format_exc(limit=3),
                "data": {},
            }
        steps.append(result)

    severity = _compute_severity(steps)

    # Kimi K2.6 synthesis
    synthesis = _kimi_synthesis(steps, df, severity)

    return {
        "filename": filename,
        "rows": len(df),
        "columns": list(df.columns),
        "severity": severity,
        "steps": steps,
        "synthesis": synthesis,
    }
