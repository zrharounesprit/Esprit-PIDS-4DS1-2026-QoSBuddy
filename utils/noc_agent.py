# ─────────────────────────────────────────────────────────────────────────────
# utils/noc_agent.py — NOC Autopilot SLA Guardian Agent
#
# Autonomous 7-phase agentic loop powered by Kimi K2.6.
#
# Architecture:
#   - Synthetic CESNET traffic is generated locally
#   - Feature engineering runs locally (55 features)
#   - Engineered rows are POST'd to the SLA XGBoost API on port 8003
#   - Kimi K2.6 drives all reasoning: attribution, planning, synthesis
#
#   OBSERVE   → Generate synthetic traffic, engineer features, POST to SLA API
#   ATTRIBUTE → Kimi K2.6 analyses SLA output + feature values → root cause
#   PLAN      → Kimi K2.6 decides mitigation strategy from actual data
#   SIMULATE  → Apply mitigation, re-POST to SLA API
#   VERIFY    → Check if breach is resolved
#   ITERATE   → Up to 3 rounds, Kimi adjusts strategy each time
#   SYNTHESIZE→ Kimi K2.6 generates executive incident report
#
# Entry point: run_noc_cycle(inject_breach=None) → dict
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import json
import os
import random
import traceback
import warnings
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

try:
    from .synthetic_traffic import generate_traffic_window, inject_scenario
    from .noc_state import set_phase
    from .sla_preprocess import merge_cesnet_times_1h, ensure_subnet_key
    from .sla_pipeline import engineer_sla_features
except ImportError:
    from utils.synthetic_traffic import generate_traffic_window, inject_scenario
    from utils.noc_state import set_phase
    from utils.sla_preprocess import merge_cesnet_times_1h, ensure_subnet_key
    from utils.sla_pipeline import engineer_sla_features

from dotenv import load_dotenv
load_dotenv(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
    override=True,
)

# ── Config ────────────────────────────────────────────────────────────────────
SLA_API_URL      = os.getenv("SLA_API_URL", "http://127.0.0.1:8003")
MOONSHOT_KEY     = os.getenv("MOONSHOT_API_KEY", "")
SLACK_WEBHOOK    = os.getenv("SLACK_WEBHOOK_URL", "")
KIMI_MODEL       = "kimi-k2.6"
KIMI_BASE        = "https://api.moonshot.ai/v1"

print(f"[NOC] MOONSHOT_API_KEY loaded: {'yes (' + MOONSHOT_KEY[:8] + '...)' if MOONSHOT_KEY else 'NO — Kimi will fallback'}")
print(f"[NOC] Slack webhook: {'configured' if SLACK_WEBHOOK else 'NOT SET — alerts disabled'}")

TIMEOUT_SLA     = 30
TIMEOUT_KIMI    = 60
MAX_ITERATIONS  = 3
N_ROWS          = 48

_SCENARIOS = ["capacity_increase", "qos_throttle", "rate_limit"]

_SYSTEM_PROMPT = (
    "Return ONLY a JSON object. Every string value MUST be one sentence, max 20 words. "
    "No explanation. No thinking. Just the JSON."
)


# ── Fetch SLA feature columns from the running API ───────────────────────────

_SLA_FEATURE_COLS: Optional[list] = None
_SLA_THRESHOLD:    Optional[float] = None


def _fetch_sla_metadata() -> tuple[Optional[list], Optional[float]]:
    """Ask the SLA API for its feature columns and threshold."""
    global _SLA_FEATURE_COLS, _SLA_THRESHOLD
    if _SLA_FEATURE_COLS is not None:
        return _SLA_FEATURE_COLS, _SLA_THRESHOLD
    try:
        r = httpx.get(f"{SLA_API_URL}/sla_metadata", timeout=10)
        r.raise_for_status()
        meta = r.json()
        if meta.get("ready"):
            _SLA_FEATURE_COLS = meta["feature_columns"]
            _SLA_THRESHOLD = meta["optimal_threshold"]
            print(f"[NOC] SLA metadata fetched: {len(_SLA_FEATURE_COLS)} features, "
                  f"threshold={_SLA_THRESHOLD:.4f}")
            return _SLA_FEATURE_COLS, _SLA_THRESHOLD
        return None, None
    except Exception as e:
        print(f"[NOC] Failed to fetch SLA metadata: {e}")
        return None, None


# ── Kimi K2.6 LLM calls ─────────────────────────────────────────────────────

def _kimi_call(user_prompt: str, max_tokens: int = 1024) -> Optional[str]:
    if not MOONSHOT_KEY:
        print("[NOC] Kimi skipped: no MOONSHOT_API_KEY")
        return None

    from openai import OpenAI
    client = OpenAI(api_key=MOONSHOT_KEY, base_url=KIMI_BASE)
    msgs = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    try:
        resp = client.chat.completions.create(
            model=KIMI_MODEL,
            messages=msgs,
            max_tokens=max_tokens,
            temperature=0.6,
            extra_body={
                "thinking": {"type": "disabled"},
            },
        )
        content = (resp.choices[0].message.content or "").strip()
        print(f"[NOC] Kimi responded: {len(content)} chars, first 200: {content[:200]}")
        return content if content else None
    except Exception as e:
        print(f"[NOC] Kimi call failed: {e}")
        return None


def _fix_json_str(s: str) -> str:
    """Fix common JSON issues: trailing commas, single quotes, etc."""
    import re
    s = re.sub(r",\s*([}\]])", r"\1", s)
    return s


def _kimi_json(user_prompt: str, max_tokens: int = 1024) -> Optional[dict]:
    text = _kimi_call(user_prompt, max_tokens)
    if not text:
        return None
    import re
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip()
    cleaned = re.sub(r"```\s*$", "", cleaned).strip()

    # With json_object mode, response may be pure JSON — try direct parse first
    try:
        parsed = json.loads(_fix_json_str(cleaned))
        print(f"[NOC] Kimi JSON parsed directly: {list(parsed.keys())}")
        return parsed
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: Kimi embeds chain-of-thought before JSON — find last complete object
    last_brace = cleaned.rfind("}")
    if last_brace < 0:
        print(f"[NOC] Kimi response has no '}}' — cannot parse JSON")
        return None

    depth = 0
    start = -1
    for i in range(last_brace, -1, -1):
        if cleaned[i] == "}":
            depth += 1
        elif cleaned[i] == "{":
            depth -= 1
            if depth == 0:
                start = i
                break

    if start < 0:
        print(f"[NOC] Kimi response: no matching '{{' found")
        return None

    candidate = _fix_json_str(cleaned[start:last_brace + 1])
    try:
        parsed = json.loads(candidate)
        print(f"[NOC] Kimi JSON parsed OK: {list(parsed.keys())}")
        return parsed
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"[NOC] Kimi JSON parse failed: {exc}")
        print(f"[NOC] Candidate: {candidate[:300]}")
    return None


# ── SLA prediction via HTTP to port 8003 ────────────────────────────────────

def _call_sla_api(data_df: pd.DataFrame, times_df: pd.DataFrame) -> dict:
    """
    Send raw synthetic CESNET rows + times to the SLA API on port 8003.
    The API handles feature engineering + XGBoost prediction internally (v4).
    We also run local feature engineering to extract stats for Kimi context.
    """
    try:
        # Build raw rows payload — the SLA API v4 does its own engineering
        raw_rows = data_df.to_dict(orient="records")
        for row in raw_rows:
            for k, v in row.items():
                if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
                    row[k] = 0.0

        times_rows = times_df.to_dict(orient="records")

        payload = {
            "rows": raw_rows,
            "input_row_count": len(data_df),
            "times_rows": times_rows,
        }

        print(f"[NOC] POSTing {len(raw_rows)} raw rows + {len(times_rows)} times to {SLA_API_URL}/predict_sla")
        r = httpx.post(
            f"{SLA_API_URL}/predict_sla",
            json=payload,
            timeout=TIMEOUT_SLA,
        )
        r.raise_for_status()
        resp = r.json()
        print(f"[NOC] SLA API responded: {resp.get('rows_scored', 0)} scored, "
              f"{resp.get('rows_skipped', 0)} skipped")

        # Run local feature engineering just to get stats for Kimi context
        feature_cols, _ = _fetch_sla_metadata()
        if feature_cols:
            try:
                merged = merge_cesnet_times_1h(data_df.copy(), times_df.copy())
                merged = ensure_subnet_key(merged, "default")
                df_eng = engineer_sla_features(merged, feature_cols)
                df_eng = df_eng.replace([np.inf, -np.inf], np.nan).dropna(subset=feature_cols)
                feature_stats = {}
                for col in feature_cols:
                    if col in df_eng.columns:
                        vals = df_eng[col].dropna()
                        if not vals.empty:
                            feature_stats[col] = {
                                "mean": round(float(vals.mean()), 4),
                                "max":  round(float(vals.max()), 4),
                                "min":  round(float(vals.min()), 4),
                            }
                resp["feature_stats"] = feature_stats
            except Exception:
                resp["feature_stats"] = {}

        return resp

    except httpx.HTTPStatusError as e:
        return {"error": f"SLA API HTTP {e.response.status_code}: {e.response.text[:300]}"}
    except httpx.ConnectError:
        return {"error": f"SLA API not reachable at {SLA_API_URL} — is it running on port 8003?"}
    except Exception as e:
        return {"error": traceback.format_exc(limit=5)}


def _extract_breach_summary(sla_resp: dict) -> dict:
    results    = sla_resp.get("results", [])
    probs      = [r["probability"] for r in results
                  if r.get("probability") is not None and not r.get("skipped")]
    violations = [r for r in results if r.get("sla_violation")]
    threshold  = sla_resp.get("optimal_threshold", _SLA_THRESHOLD or 0.8233)
    return {
        "breach_count":  len(violations),
        "max_prob":      round(max(probs), 4) if probs else 0.0,
        "avg_prob":      round(float(np.mean(probs)), 4) if probs else 0.0,
        "rows_scored":   sla_resp.get("rows_scored", 0),
        "threshold":     threshold,
        "severity":      violations[0].get("severity", "HIGH") if violations else "OK",
    }


def _top_features(sla_resp: dict, n: int = 10) -> dict:
    stats = sla_resp.get("feature_stats", {})
    if not stats:
        return {}
    sorted_feats = sorted(stats.items(), key=lambda x: abs(x[1].get("max", 0)), reverse=True)
    return dict(sorted_feats[:n])


def _build_data_summary(data_df: pd.DataFrame) -> dict:
    summary: dict = {"rows": len(data_df)}
    for col in ["n_bytes", "n_packets", "n_flows"]:
        if col in data_df.columns:
            vals = data_df[col].dropna()
            summary[col] = {
                "mean": round(float(vals.mean()), 2),
                "max":  round(float(vals.max()), 2),
                "min":  round(float(vals.min()), 2),
                "std":  round(float(vals.std()), 2),
                "p75":  round(float(vals.quantile(0.75)), 2),
                "p95":  round(float(vals.quantile(0.95)), 2),
            }
    for col in ["tcp_udp_ratio_packets", "dir_ratio_packets"]:
        if col in data_df.columns:
            summary[col] = round(float(data_df[col].mean()), 4)
    return summary


# ── Kimi-driven ATTRIBUTE ────────────────────────────────────────────────────

def _kimi_attribute(breach_summary: dict, feature_stats: dict, data_summary: dict) -> dict:
    prompt = f"""SLA breach: {breach_summary['breach_count']}/{breach_summary['rows_scored']} rows, max_prob={breach_summary['max_prob']}, severity={breach_summary['severity']}.
Top features: {json.dumps(feature_stats)}
Traffic: {json.dumps(data_summary)}
Return ONLY this JSON (keep values short):
{{"root_cause":"<one sentence>","driving_features":["f1","f2","f3"],"feature_analysis":"<one sentence>","confidence":"high|medium|low"}}"""

    result = _kimi_json(prompt)
    if result:
        result["source"] = "kimi-k2.6"
        return result

    return {
        "source": "fallback",
        "root_cause": f"n_bytes_peak_ratio spike detected (max_prob={breach_summary['max_prob']:.3f})",
        "driving_features": ["n_bytes_peak_ratio", "n_bytes_mean_24h", "n_bytes"],
        "feature_analysis": (
            f"Breach probability {breach_summary['max_prob']:.3f} exceeds threshold "
            f"{breach_summary['threshold']:.4f}. Volume features are the likely driver."
        ),
        "confidence": "medium",
    }


# ── Kimi-driven PLAN ────────────────────────────────────────────────────────

def _kimi_plan(
    breach_summary: dict,
    attribution: dict,
    data_summary: dict,
    iteration: int = 0,
    prev_result: Optional[dict] = None,
) -> dict:
    prev_context = ""
    if prev_result and iteration > 0:
        prev_context = (
            f"Previous try: {prev_result.get('scenario')} factor={prev_result.get('factor')}, "
            f"still {prev_result.get('breach_count')} breaches. Be MORE aggressive."
        )

    prompt = f"""Breach: severity={breach_summary['severity']}, max_prob={breach_summary['max_prob']}, rows={breach_summary['breach_count']}/{breach_summary['rows_scored']}.
Root cause: {attribution.get('root_cause','unknown')}.
{prev_context}
Pick ONE scenario: capacity_increase|qos_throttle|rate_limit. Factor 0.15-0.70 (lower=more aggressive). HIGH→0.2-0.35, MEDIUM→0.35-0.55.
Return ONLY this JSON:
{{"scenario":"<choice>","factor":0.3,"reasoning":"<one sentence>","expected_outcome":"<one sentence>","actions":["action1","action2","action3"]}}"""

    result = _kimi_json(prompt)
    if result:
        scenario = result.get("scenario", "capacity_increase")
        if scenario not in _SCENARIOS:
            scenario = "capacity_increase"
        result["scenario"] = scenario

        factor = result.get("factor", 0.55)
        try:
            factor = float(factor)
            factor = max(0.15, min(0.70, factor))
        except (TypeError, ValueError):
            factor = 0.55
        result["factor"] = factor
        result["source"] = "kimi-k2.6"
        return result

    scenario = _SCENARIOS[min(iteration, len(_SCENARIOS) - 1)]
    factor = max(0.20, 0.55 - iteration * 0.15)
    return {
        "source": "fallback",
        "scenario": scenario,
        "factor": factor,
        "reasoning": f"Fallback: trying {scenario} with factor={factor:.2f} (iteration {iteration + 1})",
        "expected_outcome": "Reduce peak traffic to bring SLA probability below threshold",
        "actions": [
            f"Apply {scenario.replace('_', ' ')} mitigation",
            "Monitor n_bytes_peak_ratio after changes",
            "Escalate to NOC team if breach persists",
        ],
    }


# ── Kimi-driven SYNTHESIZE ──────────────────────────────────────────────────

def _kimi_synthesize(context: dict) -> dict:
    b    = context.get("breach_summary", {})
    attr = context.get("attribution", {})
    plan = context.get("plan", {})

    prompt = f"""Incident report. severity={b.get('severity')}, max_prob={b.get('max_prob')}, breaches={b.get('breach_count',0)}/{b.get('rows_scored',0)}, resolved={context.get('resolved',False)}, mitigation={context.get('mitigation_scenario')}, iterations={context.get('iterations',0)}.
Root cause: {attr.get('root_cause','N/A')}.
Return ONLY this JSON (keep each value under 25 words):
{{"executive_summary":"<2 sentences>","root_cause":"<one sentence>","business_impact":"<one sentence>","recommendations":["r1","r2","r3","r4"]}}"""

    result = _kimi_json(prompt, max_tokens=1024)
    if result:
        result["source"] = "kimi-k2.6"
        return result

    return _rule_based_synthesis(context)


def _rule_based_synthesis(context: dict, note: str = "") -> dict:
    b        = context.get("breach_summary", {})
    sev      = b.get("severity", "HIGH")
    prob     = b.get("max_prob", 0)
    resolved = context.get("resolved", False)
    scenario = context.get("mitigation_scenario", "capacity adjustment")
    attr     = context.get("attribution", {})

    driving = attr.get("driving_features", ["n_bytes_peak_ratio"])
    root    = attr.get("root_cause", "Volume spike detected in traffic features")
    status  = "resolved after automated mitigation" if resolved else "requires manual intervention"
    src     = "rule-based" + (f" (Kimi K2.6 unavailable: {note})" if note else "")

    return {
        "source": src,
        "executive_summary": (
            f"SLA breach detected with probability {prob:.3f} ({sev} severity). "
            f"Automated {scenario.replace('_', ' ')} simulation was {status}. "
            f"Primary driver: {', '.join(driving[:2])}."
        ),
        "root_cause": root,
        "business_impact": (
            "Latency-sensitive applications (VoIP, video conferencing) at risk. "
            "QoS guarantees may be violated for premium subscribers."
        ),
        "recommendations": context.get("plan", {}).get("actions", [
            f"Apply {scenario.replace('_', ' ')} to reduce peak byte throughput.",
            "Identify top-N source IPs contributing to volume spike.",
            "Review QoS queuing — prioritise real-time traffic classes.",
            "Set early-warning alert on n_bytes_peak_ratio > 1.3.",
        ]),
    }


# ── Slack Notification ───────────────────────────────────────────────────────

def _send_slack_alert(cycle: dict) -> None:
    if not SLACK_WEBHOOK:
        print("[NOC] Slack alert skipped: no SLACK_WEBHOOK_URL")
        return

    report = cycle.get("report", {})
    breach = cycle.get("breach_detected", False)
    resolved = cycle.get("resolved", False)
    severity = cycle.get("severity", "OK")
    b = cycle.get("breach_summary", {})

    if not breach:
        emoji = ":large_green_circle:"
        color = "#2eb886"
        status = "ALL CLEAR — No SLA breach detected"
        title = "NOC Autopilot — Nominal"
    elif resolved:
        emoji = ":white_check_mark:"
        color = "#f0ad4e"
        status = "RESOLVED — Automated mitigation successful"
        title = f"NOC Autopilot — SLA Breach {severity} (Resolved)"
    else:
        emoji = ":rotating_light:"
        color = "#dc3545"
        status = "UNRESOLVED — Human intervention required"
        title = f"NOC Autopilot — SLA Breach {severity} (Action Required)"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{emoji}  {title}"},
        },
    ]

    if not breach:
        blocks.append({
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Status:*\n{status}"},
                {"type": "mrkdwn", "text": f"*Max Probability:*\n{b.get('max_prob', 'N/A')}"},
                {"type": "mrkdwn", "text": f"*Rows Scored:*\n{b.get('rows_scored', 'N/A')}"},
                {"type": "mrkdwn", "text": f"*Threshold:*\n{b.get('threshold', 'N/A')}"},
            ],
        })
    else:
        blocks.append({
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Status:*\n{status}"},
                {"type": "mrkdwn", "text": f"*Severity:*\n{severity}"},
                {"type": "mrkdwn", "text": f"*Max Probability:*\n{b.get('max_prob', 'N/A')}"},
                {"type": "mrkdwn", "text": f"*Breaches:*\n{b.get('breach_count', 0)}/{b.get('rows_scored', 0)} rows"},
                {"type": "mrkdwn", "text": f"*Mitigation:*\n{cycle.get('mitigation_scenario', 'N/A')}"},
                {"type": "mrkdwn", "text": f"*Iterations:*\n{cycle.get('iterations', 0)}"},
            ],
        })

    blocks.append({"type": "divider"})

    if report.get("executive_summary"):
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Executive Summary*\n{report['executive_summary']}"},
        })

    if breach and report.get("root_cause"):
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Root Cause*\n{report['root_cause']}"},
        })

    if breach and report.get("business_impact"):
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Business Impact*\n{report['business_impact']}"},
        })

    recs = report.get("recommendations", [])
    if recs:
        rec_text = "\n".join(f"• {r}" for r in recs)
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Recommendations*\n{rec_text}"},
        })

    if breach and not resolved:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": ":warning: *This breach could not be resolved automatically. A NOC engineer must take action immediately.*",
            },
        })

    blocks.append({
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": f"QoSBuddy NOC Autopilot • {cycle.get('ts_start', '')}"},
        ],
    })

    payload = {"blocks": blocks, "attachments": [{"color": color, "blocks": []}]}

    try:
        r = httpx.post(SLACK_WEBHOOK, json=payload, timeout=10)
        print(f"[NOC] Slack alert sent: {r.status_code}")
    except Exception as e:
        print(f"[NOC] Slack alert failed: {e}")


# ── Main cycle ────────────────────────────────────────────────────────────────

def run_noc_cycle(inject_breach: Optional[bool] = None) -> dict:
    """
    Full 7-phase NOC cycle.
    - inject_breach=None → random (50% chance)
    - Synthetic data is generated and feature-engineered locally
    - Engineered rows are POST'd to SLA API on port 8003
    - Kimi K2.6 drives attribution, planning, and synthesis
    """
    ts_start = datetime.now(timezone.utc).isoformat()
    if inject_breach is None:
        inject_breach = random.random() < 0.50

    cycle: dict = {
        "ts_start":        ts_start,
        "ts_end":          None,
        "phases":          [],
        "breach_detected": False,
        "resolved":        False,
        "severity":        "OK",
        "iterations":      0,
    }

    # ── OBSERVE ──────────────────────────────────────────────────────────────
    set_phase("OBSERVE", "Generating synthetic traffic + sending to SLA API (port 8003)")
    ph_obs: dict = {"name": "OBSERVE", "icon": "eye", "status": "running", "detail": ""}

    try:
        data_df, times_df = generate_traffic_window(
            n_rows=N_ROWS,
            inject_breach=inject_breach,
            breach_factor=random.uniform(5.5, 7.5),
        )
        sla_resp = _call_sla_api(data_df, times_df)

        if "error" in sla_resp:
            ph_obs["status"] = "error"
            ph_obs["detail"] = f"SLA API error: {sla_resp['error']}"
            cycle["phases"].append(ph_obs)
            cycle["ts_end"] = datetime.now(timezone.utc).isoformat()
            cycle["error"] = sla_resp["error"]
            return cycle

        breach_summary  = _extract_breach_summary(sla_resp)
        breach_detected = breach_summary["breach_count"] > 0
        cycle["breach_detected"] = breach_detected
        cycle["breach_summary"]  = breach_summary
        cycle["severity"] = breach_summary["severity"] if breach_detected else "OK"

        data_summary = _build_data_summary(data_df)
        cycle["data_summary"] = data_summary

        feature_stats = _top_features(sla_resp)
        cycle["feature_stats"] = feature_stats

        ph_obs["status"] = "done"
        ph_obs["detail"] = (
            f"Observed {N_ROWS} synthetic hourly rows — "
            f"{sla_resp['rows_scored']} scored via SLA API (port 8003). "
            f"Max SLA probability: {breach_summary['max_prob']:.4f}. "
            f"Breaches: {breach_summary['breach_count']}/{sla_resp['rows_scored']}."
        )
    except Exception as e:
        ph_obs["status"] = "error"
        ph_obs["detail"] = traceback.format_exc(limit=3)
        cycle["phases"].append(ph_obs)
        cycle["ts_end"] = datetime.now(timezone.utc).isoformat()
        cycle["error"]  = str(e)
        return cycle

    cycle["phases"].append(ph_obs)

    # ── ATTRIBUTE ────────────────────────────────────────────────────────────
    set_phase("ATTRIBUTE", "Kimi K2.6 analyzing SLA features to identify root cause")
    ph_attr: dict = {"name": "ATTRIBUTE", "icon": "search", "status": "running", "detail": ""}

    if breach_detected:
        attribution = _kimi_attribute(breach_summary, feature_stats, data_summary)
        cycle["attribution"] = attribution
        ph_attr["status"] = "done"
        ph_attr["detail"] = (
            f"Root cause ({attribution.get('source', 'unknown')}): "
            f"{attribution.get('root_cause', 'N/A')[:150]}"
        )
    else:
        attribution = {
            "source": "skipped",
            "root_cause": "No breach — SLA within normal parameters.",
            "driving_features": [],
            "feature_analysis": "All probabilities below threshold.",
            "confidence": "high",
        }
        cycle["attribution"] = attribution
        ph_attr["detail"] = "No breach — attribution skipped."
        ph_attr["status"] = "done"

    cycle["phases"].append(ph_attr)

    # ── PLAN ─────────────────────────────────────────────────────────────────
    set_phase("PLAN", "Kimi K2.6 building mitigation strategy")
    ph_plan: dict = {"name": "PLAN", "icon": "clipboard", "status": "running", "detail": ""}

    if breach_detected:
        plan = _kimi_plan(breach_summary, attribution, data_summary)
        cycle["plan"] = plan
        ph_plan["status"] = "done"
        ph_plan["detail"] = (
            f"Strategy ({plan.get('source', 'unknown')}): "
            f"{plan.get('scenario', 'N/A')} factor={plan.get('factor', 'N/A')}. "
            f"{plan.get('reasoning', '')[:120]}"
        )
    else:
        plan = {
            "source": "skipped",
            "scenario": "none",
            "factor": 1.0,
            "reasoning": "No intervention required.",
            "actions": ["Continue monitoring.", "Maintain current QoS configuration."],
        }
        cycle["plan"] = plan
        ph_plan["status"] = "done"
        ph_plan["detail"] = "No intervention required."

    cycle["phases"].append(ph_plan)

    # ── SIMULATE / VERIFY / ITERATE ──────────────────────────────────────────
    resolved  = False
    iteration = 0
    mitigation_scenario = plan.get("scenario", _SCENARIOS[0])
    sim_history: list = []

    if breach_detected:
        prev_result = None
        for iteration in range(1, MAX_ITERATIONS + 1):
            if iteration > 1:
                plan = _kimi_plan(
                    breach_summary, attribution, data_summary,
                    iteration=iteration - 1, prev_result=prev_result,
                )
                cycle["plan"] = plan
                mitigation_scenario = plan.get("scenario", _SCENARIOS[0])

            factor = plan.get("factor", 0.55)

            set_phase("SIMULATE", f"Iteration {iteration}: applying {mitigation_scenario} (factor={factor:.2f})")
            sim_df   = inject_scenario(data_df, scenario=mitigation_scenario, factor=factor)
            sim_resp = _call_sla_api(sim_df, times_df)

            ph_sim: dict = {
                "name":   f"SIMULATE (iter {iteration})",
                "icon":   "settings",
                "status": "running",
                "detail": f"Scenario: {mitigation_scenario}, factor={factor:.2f}",
            }

            if "error" in sim_resp:
                ph_sim["status"] = "warn"
                ph_sim["detail"] += f" — SLA API error: {sim_resp['error'][:80]}"
                cycle["phases"].append(ph_sim)
                break

            sim_breach = _extract_breach_summary(sim_resp)
            ph_sim["status"] = "done"
            ph_sim["detail"] += (
                f" → max_prob={sim_breach['max_prob']:.4f}, "
                f"breaches={sim_breach['breach_count']}/{sim_breach['rows_scored']}"
            )
            cycle["phases"].append(ph_sim)

            prev_result = {
                "scenario": mitigation_scenario,
                "factor": factor,
                **sim_breach,
            }
            sim_history.append({
                "iteration": iteration,
                "scenario": mitigation_scenario,
                "factor": factor,
                **sim_breach,
            })

            set_phase("VERIFY", f"Verifying iteration {iteration}")
            ph_ver: dict = {
                "name":   f"VERIFY (iter {iteration})",
                "icon":   "check-circle",
                "status": "running",
                "detail": "",
            }

            if sim_breach["breach_count"] == 0:
                resolved = True
                ph_ver["status"] = "done"
                ph_ver["detail"] = (
                    f"Breach resolved by {mitigation_scenario} "
                    f"after {iteration} iteration(s). "
                    f"max_prob dropped to {sim_breach['max_prob']:.4f}."
                )
                cycle["phases"].append(ph_ver)
                break
            else:
                ph_ver["status"] = "warn"
                ph_ver["detail"] = (
                    f"Breach persists (max_prob={sim_breach['max_prob']:.4f}). "
                    f"{'Kimi adjusting strategy...' if iteration < MAX_ITERATIONS else 'Max iterations — escalating.'}"
                )
                cycle["phases"].append(ph_ver)
    else:
        for name, detail in [
            ("SIMULATE", "No breach — simulation not required."),
            ("VERIFY",   "SLA within normal parameters."),
        ]:
            cycle["phases"].append({
                "name": name,
                "icon": "settings" if name == "SIMULATE" else "check-circle",
                "status": "skipped",
                "detail": detail,
            })
        resolved = True

    cycle["resolved"]            = resolved
    cycle["iterations"]          = iteration
    cycle["mitigation_scenario"] = mitigation_scenario
    cycle["sim_history"]         = sim_history

    # ── SYNTHESIZE ───────────────────────────────────────────────────────────
    set_phase("SYNTHESIZE", "Kimi K2.6 generating executive report")
    report = _kimi_synthesize(cycle)
    cycle["report"] = report
    cycle["phases"].append({
        "name":   "SYNTHESIZE",
        "icon":   "file-text",
        "status": "done",
        "detail": (
            f"Report by {report.get('source', '?')}. "
            f"{'Breach resolved.' if resolved else 'Manual action recommended.'}"
        ),
    })

    cycle["ts_end"] = datetime.now(timezone.utc).isoformat()

    _send_slack_alert(cycle)

    return cycle
