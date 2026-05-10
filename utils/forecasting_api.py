# ─────────────────────────────────────────────────────────────────────────────
# utils/forecasting_api.py — Traffic Forecasting FastAPI
#
# Run:
#   uvicorn utils.forecasting_api:app --port 8004 --reload
# ─────────────────────────────────────────────────────────────────────────────

import os
import pickle
import glob
import time
import numpy as np
import urllib.request
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

GEMINI_KEY = "AIzaSyDzkTnwp1jV3vD1f2cgxGCh4SjPX4ug88c"
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"gemini-2.0-flash:generateContent?key={GEMINI_KEY}"
)

# ── Load artifacts ────────────────────────────────────────────────────────────
ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "..", "model_export")

with open(os.path.join(ARTIFACTS_DIR, "config.pkl"), "rb") as f:
    config = pickle.load(f)

with open(os.path.join(ARTIFACTS_DIR, "scaler_params.pkl"), "rb") as f:
    scaler = pickle.load(f)

with open(os.path.join(ARTIFACTS_DIR, "ip_to_id.pkl"), "rb") as f:
    ip_to_id = pickle.load(f)

from tensorflow.keras.models import load_model  # noqa: E402

model = load_model(os.path.join(ARTIFACTS_DIR, "lstm_embedding_model.keras"))

# ── Constants from config ─────────────────────────────────────────────────────
FEATURES  = config["FEATURES"]
SEQ_LEN   = config["SEQ_LEN"]       # 24
HORIZON   = config["HORIZON"]       # 6
N_IPS     = config["n_ips"]         # 1000

feat_mean = scaler["feat_mean"]
feat_std  = scaler["feat_std"]
tgt_mean  = scaler["tgt_mean"]
tgt_std   = scaler["tgt_std"]

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(title="QoSBuddy Forecasting API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ForecastRequest(BaseModel):
    rows: List[dict]
    ip_id: Optional[int] = 0


class ForecastResponse(BaseModel):
    forecast: List[float]
    horizon: int
    unit: str


class ExplainRequest(BaseModel):
    historical_bytes: List[float]   # 24 raw n_bytes values
    forecast_bytes:   List[float]   # 6 predicted values
    filename:         Optional[str] = None


class ExplainResponse(BaseModel):
    explanation:     str
    health_score:    int
    trend:           str
    recommendations: List[str]
    peak_hour:       int


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model": "lstm_embedding",
        "seq_len": SEQ_LEN,
        "horizon": HORIZON,
        "n_ips": N_IPS,
        "mape": config.get("mape"),
    }


@app.post("/forecast", response_model=ForecastResponse)
def forecast(req: ForecastRequest):
    if len(req.rows) != SEQ_LEN:
        raise HTTPException(400, f"Expected {SEQ_LEN} rows, got {len(req.rows)}")

    if not 0 <= req.ip_id < N_IPS:
        raise HTTPException(400, f"ip_id must be in [0, {N_IPS - 1}]")

    # Preprocessing matches training notebook exactly:
    # 1. log1p on ALL features  (not partial log)
    # 2. standardise with global scaler params
    raw = np.zeros((SEQ_LEN, len(FEATURES)))
    for t, row in enumerate(req.rows):
        for j, feat in enumerate(FEATURES):
            val = float(row.get(feat, 0.0))
            raw[t, j] = np.log1p(val)   # log1p on ALL features

    X = (raw - feat_mean) / (feat_std + 1e-9)

    ts_input = X.reshape(1, SEQ_LEN, len(FEATURES)).astype(np.float32)
    id_input = np.array([[req.ip_id]], dtype=np.int32)

    pred_std = model.predict([ts_input, id_input], verbose=0)

    # Denormalise → log1p space → real bytes
    pred_log1p = pred_std[0] * tgt_std + tgt_mean
    pred_real  = np.expm1(pred_log1p)   # inverse of log1p

    return ForecastResponse(
        forecast=[round(float(v), 2) for v in pred_real],
        horizon=HORIZON,
        unit="n_bytes",
    )


@app.get("/ip-id")
def get_ip_id(filename: str):
    """Resolve a CSV filename to its trained embedding ID."""
    clean = filename.replace(".csv", "")
    key   = clean + ".csv"
    if key in ip_to_id:
        return {"ip_id": ip_to_id[key], "found": True}
    if clean in ip_to_id:
        return {"ip_id": ip_to_id[clean], "found": True}
    return {"ip_id": 0, "found": False}


@app.post("/explain", response_model=ExplainResponse)
def explain(req: ExplainRequest):
    hist = req.historical_bytes
    fc   = req.forecast_bytes

    hist_avg  = float(np.mean(hist))   if hist else 0
    hist_max  = float(np.max(hist))    if hist else 0
    hist_min  = float(np.min(hist))    if hist else 0
    hist_std  = float(np.std(hist))    if hist else 0
    fc_avg    = float(np.mean(fc))     if fc   else 0
    peak_hour = int(np.argmax(fc)) + 1

    # ── Trend ─────────────────────────────────────────────────────────────────
    if   fc[-1] > fc[0] * 1.2:   trend = "Rising"
    elif fc[-1] < fc[0] * 0.8:   trend = "Declining"
    elif max(fc) > fc_avg * 1.6: trend = "Volatile"
    else:                         trend = "Stable"

    non_zero = sum(1 for v in hist if v > 0) / max(len(hist), 1)

    def fmt(b):
        if b >= 1e9: return f"{b/1e9:.2f} GB"
        if b >= 1e6: return f"{b/1e6:.2f} MB"
        if b >= 1e3: return f"{b/1e3:.2f} KB"
        return f"{b:.0f} B"

    hist_cv   = hist_std / (hist_avg + 1e-9)   # coefficient of variation
    fc_change = (fc[-1] - fc[0]) / (fc[0] + 1e-9) * 100

    # ── Gemini explanation ────────────────────────────────────────────────────
    fc_lines  = "\n".join(
        f"  +{i+1}h: {fmt(v)}  ({v:,.0f} bytes)"
        for i, v in enumerate(fc)
    )
    prompt = (
        "You are an expert network analyst writing a report for both technical "
        "engineers and non-technical managers.\n\n"
        f"An LSTM deep-learning model analysed the last 24 hours of network "
        f"traffic for IP '{req.filename or 'unknown'}' and produced a 6-hour forecast.\n\n"
        "=== HISTORICAL DATA (last 24 hours) ===\n"
        f"  Average throughput : {fmt(hist_avg)}  ({hist_avg:,.0f} bytes/h)\n"
        f"  Peak throughput    : {fmt(hist_max)}  ({hist_max:,.0f} bytes/h)\n"
        f"  Minimum throughput : {fmt(hist_min)}  ({hist_min:,.0f} bytes/h)\n"
        f"  Std deviation      : {fmt(hist_std)}  (variability index: {hist_cv:.2f})\n"
        f"  Active hours       : {int(non_zero*24)}/24\n\n"
        "=== 6-HOUR FORECAST ===\n"
        f"{fc_lines}\n"
        f"  Overall change     : {fc_change:+.1f}%\n"
        f"  Trend              : {trend}\n"
        f"  Peak expected at   : +{peak_hour}h\n\n"
        "Write a detailed analysis in 3 clear paragraphs — NO markdown, NO bullet points:\n"
        "Paragraph 1 (Pattern): Describe what happened in the last 24 hours. "
        "Was it a busy or quiet period? Was traffic stable or erratic? "
        "Use both human-readable sizes (MB/GB) and technical detail.\n"
        "Paragraph 2 (Forecast): Explain what the next 6 hours look like. "
        "Is traffic expected to rise, fall, or stay flat? By how much? "
        "When is the busiest hour? What does this mean practically?\n"
        "Paragraph 3 (Action): Give 2 specific, actionable recommendations "
        "for the network team based on this forecast. Be concrete."
    )

    explanation = "AI explanation unavailable."
    import time
    for attempt in range(3):
        try:
            payload = json.dumps({
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.3, "maxOutputTokens": 500},
            }).encode("utf-8")
            req_obj = urllib.request.Request(
                GEMINI_URL,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req_obj, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            explanation = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            break  # success — stop retrying
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                time.sleep(3 * (attempt + 1))  # wait 3s, then 6s
                continue
            explanation = f"AI explanation unavailable (rate limit — try again in a moment)." if e.code == 429 else f"AI explanation unavailable ({e})."
        except Exception as e:
            explanation = f"AI explanation unavailable ({e})."
            break

    # ── Rule-based recommendations ────────────────────────────────────────────
    recs = []
    if fc_avg > hist_avg * 1.5:
        recs.append(f"Bandwidth alert — predicted avg {fmt(fc_avg)} is 50%+ above the historical avg {fmt(hist_avg)}. Consider pre-provisioning capacity.")
    if trend == "Rising":
        recs.append("Sustained upward trend detected. Monitor for congestion in the next 3–6 hours.")
    if trend == "Volatile":
        recs.append("High traffic variance expected. Avoid scheduled maintenance during this window.")
    if non_zero < 0.5:
        recs.append("Over half the lookback window had no traffic. Forecast is based on limited activity — treat with caution.")
    if fc_avg < hist_avg * 0.3:
        recs.append(f"Traffic is expected to drop significantly ({fmt(fc_avg)} avg vs {fmt(hist_avg)} historical). Possible device inactivity or network issue.")
    if not recs:
        recs.append(f"Traffic is forecast to remain stable around {fmt(fc_avg)}/h. No immediate action required.")

    return ExplainResponse(
        explanation=explanation,
        health_score=min(100, max(0, int(non_zero * 60 + (1 - abs(fc_avg/(hist_avg+1e-9) - 1)) * 40))),
        trend=trend,
        recommendations=recs,
        peak_hour=peak_hour,
    )


# ── Network Coverage Simulation ───────────────────────────────────────────────

# Display info per segment
_SEG_INFO = {
    "gamers":    {"label": "Gamers",     "color": "#A855F7", "description": "Bursty traffic, late-night peaks (CV>1.5 or peak 0–4h)"},
    "streamers": {"label": "Streamers",  "color": "#EF4444", "description": "Evening peak hours (18–23h)"},
    "workers":   {"label": "Workers",    "color": "#3B82F6", "description": "Business-hours peak (7–17h)"},
    "casual":    {"label": "Casual",     "color": "#22C55E", "description": "Moderate, distributed traffic"},
    "iot":       {"label": "IoT",        "color": "#94A3B8", "description": "Very low, steady traffic (<100 KB/h)"},
}

SEG_KEYS_PY = ["gamers", "streamers", "workers", "casual", "iot"]


def _classify_ip(mean_bytes_h: float, cv: float, peak_hour: int) -> str:
    """Rule-based classifier — applied to REAL measured stats from the dataset."""
    if mean_bytes_h < 1e5:
        return "iot"
    if cv > 1.5 or peak_hour in (0, 1, 2, 3, 4):
        return "gamers"
    if 18 <= peak_hour <= 23:
        return "streamers"
    if 7 <= peak_hour <= 17:
        return "workers"
    return "casual"


# ── Build the segments cache from the REAL training dataset ──────────────────
SEGMENTS_CACHE_FILE = os.path.join(ARTIFACTS_DIR, "segments_cache.json")
DATA_DIR = os.path.normpath(os.path.join(
    ARTIFACTS_DIR, "..", "..", "ip_addresses_sample", "ip_addresses_sample", "agg_1_hour"
))


def _build_segments_from_data(max_ips: int = 250):
    if os.path.exists(SEGMENTS_CACHE_FILE):
        try:
            with open(SEGMENTS_CACHE_FILE) as f:
                return json.load(f)
        except Exception:
            pass

    if not os.path.exists(DATA_DIR):
        print(f"[segments] dataset not found at {DATA_DIR}")
        return None

    print(f"[segments] scanning real dataset (sampling {max_ips} IPs)…")
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.csv")))[:max_ips]

    import pandas as pd

    cluster = {s: {"ips": [], "patterns": [], "means": [], "totals": []} for s in SEG_KEYS_PY}

    for fpath in files:
        try:
            df = pd.read_csv(fpath, usecols=["id_time", "n_bytes"])
            if len(df) < 168:
                continue
            df = df.head(7 * 24 * 4)
            df["hour"] = df["id_time"] % 24
            hourly = df.groupby("hour")["n_bytes"].mean().reindex(range(24), fill_value=0).values

            mean = float(hourly.mean())
            std = float(hourly.std())
            cv = std / (mean + 1e-9)
            peak = int(np.argmax(hourly))
            seg = _classify_ip(mean, cv, peak)

            ip_name = os.path.splitext(os.path.basename(fpath))[0]
            cluster[seg]["ips"].append(ip_name)
            cluster[seg]["patterns"].append(hourly.tolist())
            cluster[seg]["means"].append(mean)
            cluster[seg]["totals"].append(float(hourly.sum()))
        except Exception:
            continue

    total_ips = sum(len(v["ips"]) for v in cluster.values())
    if total_ips == 0:
        return None

    result = {"_meta": {"total_ips": total_ips, "data_source": DATA_DIR}}
    for seg, data in cluster.items():
        if data["patterns"]:
            patterns = np.array(data["patterns"])
            avg_pattern = patterns.mean(axis=0)
            peak = avg_pattern.max()
            normalized = (avg_pattern / peak).tolist() if peak > 0 else [0.0] * 24
            sorted_idx = list(np.argsort(data["totals"])[::-1][:5])
            top_ips = [
                {"name": data["ips"][i], "total_bytes": float(data["totals"][i])}
                for i in sorted_idx
            ]
            result[seg] = {
                "count": len(data["ips"]),
                "pct": round(len(data["ips"]) / total_ips * 100, 1),
                "pattern": normalized,
                "mean_bytes_per_hour": float(np.mean(data["means"])),
                "top_ips": top_ips,
            }
        else:
            result[seg] = {"count": 0, "pct": 0.0, "pattern": [0.5] * 24,
                           "mean_bytes_per_hour": 1e6, "top_ips": []}

    try:
        with open(SEGMENTS_CACHE_FILE, "w") as f:
            json.dump(result, f)
        print(f"[segments] cached to {SEGMENTS_CACHE_FILE}")
    except Exception as e:
        print(f"[segments] cache write failed: {e}")

    return result


DATASET_SEGMENTS = _build_segments_from_data()
if DATASET_SEGMENTS:
    print("[segments] real-data clusters loaded:")
    for s in SEG_KEYS_PY:
        d = DATASET_SEGMENTS.get(s, {})
        print(f"  {s:10s} {d.get('count', 0):3d} IPs ({d.get('pct', 0)}%)  avg {d.get('mean_bytes_per_hour', 0):.2e} B/h")


# ── Real-data-driven patterns and weights ────────────────────────────────────
def _get_seg_patterns():
    if DATASET_SEGMENTS:
        return {s: DATASET_SEGMENTS[s]["pattern"] for s in SEG_KEYS_PY}
    # Fallback: synthetic (only used if dataset not available)
    return {s: [0.5] * 24 for s in SEG_KEYS_PY}


def _get_seg_byte_weights():
    """Return relative weights (NORMALIZED to sum to 1) based on real avg bytes/h per segment."""
    if DATASET_SEGMENTS:
        raw = {s: DATASET_SEGMENTS[s]["mean_bytes_per_hour"] for s in SEG_KEYS_PY}
        return raw   # we keep absolute values — used in normalization step
    return {"gamers": 150.0, "streamers": 800.0, "workers": 80.0, "casual": 30.0, "iot": 2.0}


def _get_real_top_ips_for_segment(seg_key: str):
    if DATASET_SEGMENTS and seg_key in DATASET_SEGMENTS:
        return DATASET_SEGMENTS[seg_key].get("top_ips", [])
    return []


# ── ONE-TIME normalization factor ────────────────────────────────────────────
# Calibrated so the reference scenario (50k pop, 500 MB/h cap, default segment mix)
# peaks at ~83% capacity.  After this, population and capacity changes propagate
# to the chart linearly — making the simulator actually responsive.
_NORM_REF_POP    = 50000
_NORM_REF_CAP_MB = 500
_NORM_REF_SEGS   = {"gamers": 15, "streamers": 25, "workers": 25, "casual": 30, "iot": 5}


def _compute_norm_factor():
    real_patterns = _get_seg_patterns()
    real_weights  = _get_seg_byte_weights()
    seg_pops = {s: _NORM_REF_POP * _NORM_REF_SEGS[s] / 100.0 for s in SEG_KEYS_PY}
    natural = []
    for h_idx in range(24):
        total = sum(seg_pops[s] * real_weights[s] * real_patterns[s][h_idx] for s in SEG_KEYS_PY)
        natural.append(total)
    natural_peak = max(natural) if natural else 1.0
    cap_ref_b = _NORM_REF_CAP_MB * 1_000_000
    return (cap_ref_b * 0.83) / natural_peak if natural_peak > 0 else 1.0


NORM_FACTOR = _compute_norm_factor()
print(f"[segments] normalization factor = {NORM_FACTOR:.6e} (calibrated to {_NORM_REF_POP} pop / {_NORM_REF_CAP_MB} MB/h)")


@app.get("/dataset-segments")
def get_dataset_segments():
    """Public endpoint: returns the REAL clustering computed from the training dataset."""
    if not DATASET_SEGMENTS:
        raise HTTPException(503, "Dataset not available")
    return DATASET_SEGMENTS


class UserSegments(BaseModel):
    gamers:    float = 15.0
    streamers: float = 25.0
    workers:   float = 25.0
    casual:    float = 30.0
    iot:       float = 5.0


class SimEvent(BaseModel):
    hour:      int                 # 0-29 (24h history + 6h forecast)
    type:      str                 # "match" | "concert" | "emergency" | "outage"
    intensity: float = 1.6         # multiplier on traffic at that hour


class SimulateRequest(BaseModel):
    population:     int   = 50000
    capacity_mbph:  float = 500.0
    num_nodes:      int   = 3
    growth_factor:  float = 1.0
    segments:       Optional[UserSegments] = None
    events:         Optional[List[SimEvent]] = []
    failed_nodes:   Optional[List[int]] = []   # indices of failed nodes


class SimulateHour(BaseModel):
    hour:          int
    traffic_bytes: float
    load_pct:      float
    status:        str
    by_segment:    dict   # { gamers: bytes, streamers: bytes, ... }


class TopConsumer(BaseModel):
    name:    str
    segment: str
    bytes:   float
    rank:    int


class SLAImpact(BaseModel):
    affected_users:     int
    degraded_hours:     int
    critical_hours:     int
    estimated_churn:    int           # users likely to leave
    recommended_nodes:  int           # additional nodes to fix
    revenue_at_risk:    float          # USD/h estimate


class SimulateResponse(BaseModel):
    history:            List[SimulateHour]
    forecast:           List[SimulateHour]
    capacity_bytes:     float
    effective_capacity: float          # adjusted for failed nodes
    peak_load_pct:      float
    breach_hours:       List[int]
    summary:            str
    top_consumers:      List[TopConsumer]
    sla_impact:         SLAImpact
    segment_info:       dict           # for frontend rendering


@app.post("/simulate", response_model=SimulateResponse)
def simulate(req: SimulateRequest):
    # ── Set up ────────────────────────────────────────────────────────────────
    seg = req.segments or UserSegments()
    seg_pcts = {
        "gamers":    seg.gamers,
        "streamers": seg.streamers,
        "workers":   seg.workers,
        "casual":    seg.casual,
        "iot":       seg.iot,
    }
    total_pct = sum(seg_pcts.values())
    if total_pct == 0:
        seg_pcts = {k: 20.0 for k in seg_pcts}    # equal fallback
        total_pct = 100.0
    seg_pops = {k: req.population * v / total_pct for k, v in seg_pcts.items()}

    capacity_bytes = req.capacity_mbph * 1_000_000

    # Failed-node adjustment: each failure reduces capacity proportionally
    failed = list(set((req.failed_nodes or [])))
    failed = [i for i in failed if 0 <= i < req.num_nodes]
    active_nodes = max(req.num_nodes - len(failed), 0)
    if req.num_nodes > 0:
        effective_capacity = capacity_bytes * active_nodes / req.num_nodes
    else:
        effective_capacity = capacity_bytes
    if active_nodes == 0:
        effective_capacity = capacity_bytes * 0.05    # tiny residual

    # ── Compute per-segment traffic using REAL DATASET patterns ──────────────
    # Pattern shape and per-IP weights come from the training data
    # (see `_build_segments_from_data()` above).  NORM_FACTOR is a one-time
    # calibration so the reference scenario (50k pop, 500 MB/h) peaks at ~83%.
    # After that, population / capacity / nodes / segments all affect the
    # output linearly — no per-request rescaling.
    real_patterns = _get_seg_patterns()
    real_weights  = _get_seg_byte_weights()
    rng = np.random.RandomState(42)

    def hourly_segment(hour_idx):
        h = hour_idx % 24
        out = {}
        for s in seg_pops:
            base = seg_pops[s] * real_weights[s] * real_patterns[s][h] * NORM_FACTOR
            noise = float(rng.normal(1.0, 0.06))
            out[s] = max(0.0, base * noise)
        return out

    raw_30 = [hourly_segment(h) for h in range(30)]

    # ── Build hours with growth + events + failures ──────────────────────────
    def make_hour(idx):
        seg_bytes = {}
        for s, val in raw_30[idx].items():
            v = val * req.growth_factor
            for ev in (req.events or []):
                if ev.hour == idx:
                    v *= ev.intensity
            seg_bytes[s] = round(v, 0)
        total_b = sum(seg_bytes.values())
        load = (total_b / effective_capacity * 100) if effective_capacity > 0 else 200
        status = "critical" if load > 85 else "warning" if load > 60 else "safe"
        return SimulateHour(
            hour          = idx,
            traffic_bytes = round(total_b, 0),
            load_pct      = round(min(load, 250.0), 1),
            status        = status,
            by_segment    = seg_bytes,
        )

    history  = [make_hour(i) for i in range(24)]
    forecast = [make_hour(i) for i in range(24, 30)]
    all_hours    = history + forecast
    peak_load    = max(h.load_pct for h in all_hours)
    breach_hours = [h.hour for h in all_hours if h.status in ("warning", "critical")]
    crit_hours   = [h.hour for h in all_hours if h.status == "critical"]

    # ── Top consumers — REAL IPs from the dataset, weighted by sim contribution ──
    peak_idx = max(range(30), key=lambda i: all_hours[i].traffic_bytes)
    peak_segs = all_hours[peak_idx].by_segment

    # For each segment, pick the top real-data IPs (already sorted by total bytes)
    # and scale their reported usage so the totals align with this simulation
    candidates = []
    for s, sim_total in peak_segs.items():
        real_top = _get_real_top_ips_for_segment(s)
        if not real_top:
            continue
        # Real total weekly bytes → scale to this hour's contribution-share
        real_sum = sum(ip["total_bytes"] for ip in real_top) or 1.0
        # Distribute the SIMULATED segment-total among the real top IPs proportionally
        for ip in real_top[:2]:                       # take 2 per segment
            share = ip["total_bytes"] / real_sum
            candidates.append({
                "name":    f"IP {ip['name']}",        # real IP id from dataset
                "segment": s,
                "bytes":   sim_total * share * 0.6,   # peak-hour fraction
            })

    candidates.sort(key=lambda c: c["bytes"], reverse=True)
    top = [
        TopConsumer(name=c["name"], segment=c["segment"], bytes=round(c["bytes"], 0), rank=i + 1)
        for i, c in enumerate(candidates[:5])
    ]

    # ── SLA Impact Report ────────────────────────────────────────────────────
    # Affected users at peak: % over 85 threshold mapped to user fraction
    over_pct = max(peak_load - 85.0, 0.0)
    affected = int(req.population * min(over_pct / 50.0, 1.0))   # at peak load 135% → 100% affected
    deg_hours  = len(breach_hours)
    crit_count = len(crit_hours)
    # Churn: 0.5% of affected per critical hour, capped at 8%
    churn = int(affected * min(0.005 * crit_count, 0.08))
    # Recommended additional nodes: enough to bring peak ≤ 80%
    if peak_load > 80 and effective_capacity > 0:
        needed_capacity = effective_capacity * peak_load / 80
        cap_per_node = capacity_bytes / max(req.num_nodes, 1)
        rec_nodes = max(int(np.ceil((needed_capacity - effective_capacity) / cap_per_node)), 1) \
                    if cap_per_node > 0 else 0
    else:
        rec_nodes = 0
    # Revenue at risk: $0.5/user/h during degraded hours
    revenue_risk = round(affected * 0.5 * deg_hours, 2)

    sla = SLAImpact(
        affected_users    = affected,
        degraded_hours    = deg_hours,
        critical_hours    = crit_count,
        estimated_churn   = churn,
        recommended_nodes = rec_nodes,
        revenue_at_risk   = revenue_risk,
    )

    # ── Summary text ─────────────────────────────────────────────────────────
    fail_msg = f" with {len(failed)} node{'s' if len(failed) != 1 else ''} failed" if failed else ""
    if peak_load > 100:
        summary = (f"OUTAGE RISK: Peak demand reaches {peak_load:.0f}% of capacity{fail_msg}. "
                   f"Service degradation guaranteed. Add {rec_nodes} node(s) to recover.")
    elif peak_load > 85:
        summary = (f"CRITICAL: Peak load {peak_load:.0f}%{fail_msg}. "
                   f"~{affected:,} users impacted during peak hours. Plan upgrade.")
    elif peak_load > 60:
        summary = (f"WARNING: Peak load {peak_load:.0f}%{fail_msg}. Headroom is shrinking.")
    else:
        summary = (f"HEALTHY: Peak load {peak_load:.0f}%{fail_msg}. Infrastructure has comfortable headroom.")

    return SimulateResponse(
        history            = history,
        forecast           = forecast,
        capacity_bytes     = capacity_bytes,
        effective_capacity = round(effective_capacity, 0),
        peak_load_pct      = round(peak_load, 1),
        breach_hours       = breach_hours,
        summary            = summary,
        top_consumers      = top,
        sla_impact         = sla,
        segment_info       = _SEG_INFO,
    )


# ── AI Network Strategist ─────────────────────────────────────────────────────

class StrategistRequest(BaseModel):
    peak_load_pct:    float
    effective_capacity: float
    capacity_bytes:   float
    breach_hours:     List[int]
    sla_impact:       dict
    segment_mix:      dict          # current segment percentages
    peak_segments:    dict          # bytes per segment at peak hour
    population:       int
    num_nodes:        int
    failed_nodes:     List[int] = []


class StrategistAction(BaseModel):
    title:    str
    detail:   str
    priority: str   # "high" | "medium" | "low"


class StrategistResponse(BaseModel):
    headline: str
    actions:  List[StrategistAction]


@app.post("/strategist", response_model=StrategistResponse)
def strategist(req: StrategistRequest):
    # Find dominant segment at peak
    peak_total = sum(req.peak_segments.values()) or 1
    dom_seg = max(req.peak_segments, key=lambda k: req.peak_segments[k])
    dom_pct = req.peak_segments[dom_seg] / peak_total * 100

    breach_str = ", ".join(f"{h}h" if h < 24 else f"+{h-23}h" for h in req.breach_hours[:8])

    prompt = (
        "You are a senior network operations engineer giving tactical advice to "
        "a junior infra team. Be concise, specific, and actionable.\n\n"
        f"Network state:\n"
        f"  Population: {req.population:,} users\n"
        f"  Nodes: {req.num_nodes - len(req.failed_nodes)}/{req.num_nodes} active\n"
        f"  Effective capacity: {req.effective_capacity/1e6:.0f} MB/h\n"
        f"  Peak load: {req.peak_load_pct:.0f}%\n"
        f"  Hours breaching SLA: {breach_str or 'none'}\n"
        f"  Affected users at peak: {req.sla_impact.get('affected_users', 0):,}\n"
        f"  Dominant segment at peak: {dom_seg} ({dom_pct:.0f}%)\n"
        f"  Segment mix: {req.segment_mix}\n\n"
        "Provide:\n"
        "1. ONE-LINE HEADLINE summarizing the situation (no markdown).\n"
        "2. THREE concrete actions, each with a short title (<10 words) and "
        "1-2 sentence detail. Mark each action priority as HIGH, MEDIUM, or LOW.\n\n"
        "Format your response EXACTLY as JSON:\n"
        '{"headline":"...", "actions":[{"title":"...","detail":"...","priority":"HIGH"}, ...]}\n'
        "Do not wrap in code blocks. Return raw JSON only."
    )

    # Defaults if AI fails
    fallback = StrategistResponse(
        headline=f"Network running at {req.peak_load_pct:.0f}% peak load.",
        actions=[
            StrategistAction(
                title="Monitor peak hours",
                detail=f"Watch hours {breach_str or 'with elevated load'} closely.",
                priority="MEDIUM",
            ),
        ],
    )

    import time as _t
    last_err = None
    for attempt in range(3):
        try:
            payload = json.dumps({
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.4, "maxOutputTokens": 600},
            }).encode("utf-8")
            req_obj = urllib.request.Request(
                GEMINI_URL, data=payload,
                headers={"Content-Type": "application/json"}, method="POST",
            )
            with urllib.request.urlopen(req_obj, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            if text.startswith("```"):
                text = text.strip("`")
                if text.startswith("json"):
                    text = text[4:].strip()
            parsed = json.loads(text)
            actions = [
                StrategistAction(
                    title=a.get("title", "Action"),
                    detail=a.get("detail", ""),
                    priority=a.get("priority", "MEDIUM").upper(),
                )
                for a in parsed.get("actions", [])
            ][:4]
            return StrategistResponse(
                headline=parsed.get("headline", fallback.headline),
                actions=actions or fallback.actions,
            )
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 429 and attempt < 2:
                _t.sleep(3 * (attempt + 1))
                continue
            break
        except Exception as e:
            last_err = e
            break
    print(f"[strategist] AI call failed after retries: {last_err}")
    return fallback


# ═════════════════════════════════════════════════════════════════════════════
#  GREEN AUTO-PILOT — Multi-agent eco system with LSTM-driven decisions
#  Data: real measurements from training dataset, replayed continuously.
# ═════════════════════════════════════════════════════════════════════════════

class _LiveStream:
    """
    Pre-loads N representative IPs.
    For each IP we keep:
      - aggregated n_bytes per hour (for the chart)
      - the FULL 15-feature matrix per hour (for real LSTM forecasting)
    """

    def __init__(self, ips_per_segment: int = 8, history_hours: int = 168):
        self.ips_per_segment = ips_per_segment
        self.history_hours   = history_hours
        self.ip_data: dict   = {}     # {ip_name: 1D np.array of n_bytes}
        self.ip_features: dict = {}   # {ip_name: 2D np.array (history_hours × 15)}
        self.ip_segments: dict = {}   # {ip_name: segment_label}
        self.ip_embed_id: dict = {}   # {ip_name: int (LSTM embedding ID)}
        self._loaded         = False

    def load(self):
        if self._loaded or not DATASET_SEGMENTS:
            return
        try:
            import pandas as pd
        except ImportError:
            print("[auto-pilot] pandas required for live stream")
            return

        for seg_key in SEG_KEYS_PY:
            top_ips = DATASET_SEGMENTS.get(seg_key, {}).get("top_ips", [])
            for ip in top_ips[:self.ips_per_segment]:
                ip_name = ip["name"]
                csv_path = os.path.join(DATA_DIR, f"{ip_name}.csv")
                try:
                    # Load the full 15-feature matrix
                    df = pd.read_csv(csv_path, usecols=["id_time"] + FEATURES)
                    if len(df) < self.history_hours:
                        continue
                    df = df.head(self.history_hours)
                    feat_matrix = df[FEATURES].astype(float).values  # (H, 15)
                    self.ip_features[ip_name] = feat_matrix
                    self.ip_data[ip_name]     = df["n_bytes"].astype(float).values
                    self.ip_segments[ip_name] = seg_key
                    self.ip_embed_id[ip_name] = ip_to_id.get(f"{ip_name}.csv", 0)
                except Exception as e:
                    print(f"[auto-pilot] skip {ip_name}: {e}")
                    continue
        self._loaded = True
        print(f"[auto-pilot] live stream ready — {len(self.ip_data)} IPs × {self.history_hours} hours × {len(FEATURES)} features")

    def aggregate_at_hour(self, hour: int) -> dict:
        if not self._loaded:
            self.load()
        idx = hour % self.history_hours
        by_segment = {s: 0.0 for s in SEG_KEYS_PY}
        for ip_name, series in self.ip_data.items():
            by_segment[self.ip_segments[ip_name]] += float(series[idx])
        return by_segment

    def total_at_hour(self, hour: int) -> float:
        return sum(self.aggregate_at_hour(hour).values())

    def lstm_forecast_for_ip(self, ip_name: str, cursor: int) -> List[float]:
        """Run the REAL LSTM on this IP's last 24 hours of features."""
        if not self._loaded:
            self.load()
        if ip_name not in self.ip_features:
            return []
        # Take 24 hours ending at cursor (wrap-safe)
        H = self.history_hours
        idxs = [(cursor - 24 + i) % H for i in range(24)]
        window = self.ip_features[ip_name][idxs]  # (24, 15)

        # Apply same preprocessing as /forecast endpoint
        raw = np.log1p(window)
        X   = (raw - feat_mean) / (feat_std + 1e-9)
        ts  = X.reshape(1, SEQ_LEN, len(FEATURES)).astype(np.float32)
        ip  = np.array([[self.ip_embed_id[ip_name]]], dtype=np.int32)
        pred_std = model.predict([ts, ip], verbose=0)
        pred_log = pred_std[0] * tgt_std + tgt_mean
        pred_b   = np.expm1(pred_log)
        return [float(round(v, 0)) for v in pred_b]

    def aggregate_lstm_forecast(self, cursor: int) -> List[float]:
        """
        Aggregated LSTM forecast across all loaded IPs.
        Sums per-IP predictions to give the same scale as the chart.
        """
        if not self._loaded:
            self.load()
        total = np.zeros(HORIZON)
        for ip_name in self.ip_data:
            try:
                fc = self.lstm_forecast_for_ip(ip_name, cursor)
                if fc:
                    total += np.array(fc[:HORIZON])
            except Exception:
                continue
        return [float(round(v, 0)) for v in total]


_LIVE = _LiveStream()


# ── Pydantic models ───────────────────────────────────────────────────────────

class StreamTick(BaseModel):
    hour:           int
    by_segment:     dict
    total_bytes:    float
    ips_count:      int
    cursor_max:     int


class AgentProposal(BaseModel):
    name:        str
    icon:        str
    sleep_count: int
    confidence:  float
    reasoning:   str
    color:       str


class AutopilotDecision(BaseModel):
    agents:           List[AgentProposal]
    judge_choice:     int                   # final sleep count
    judge_reasoning:  str
    forecast_6h:      List[float]           # next 6h LSTM-style projection
    capacity_per_node_bytes: float


class SentinelStatus(BaseModel):
    delta_pct:       float
    status:          str   # "normal" | "warning" | "anomaly"
    consecutive_bad: int


class MedicPlan(BaseModel):
    diagnosis:    str
    actions:      List[str]
    eta_seconds:  int


# ── Stream initialization ────────────────────────────────────────────────────

@app.get("/autopilot/init")
def autopilot_init():
    """Returns metadata about the live stream so the frontend can configure itself."""
    _LIVE.load()
    return {
        "ips_count":     len(_LIVE.ip_data),
        "history_hours": _LIVE.history_hours,
        "segments":      SEG_KEYS_PY,
        "segment_info":  _SEG_INFO,
    }


@app.get("/autopilot/tick", response_model=StreamTick)
def autopilot_tick(hour: int):
    """Returns aggregated network state for a single replayed hour."""
    _LIVE.load()
    if not _LIVE.ip_data:
        raise HTTPException(503, "Live stream not ready")
    by_seg = _LIVE.aggregate_at_hour(hour)
    return StreamTick(
        hour        = hour,
        by_segment  = by_seg,
        total_bytes = sum(by_seg.values()),
        ips_count   = len(_LIVE.ip_data),
        cursor_max  = _LIVE.history_hours,
    )


@app.get("/autopilot/lstm-forecast")
def autopilot_lstm_forecast(cursor: int):
    """
    REAL LSTM forecast for the next 6 hours, aggregated across all 25 streamed IPs.
    Each IP is run through the trained LSTM with its embedding ID.
    """
    _LIVE.load()
    if not _LIVE.ip_data:
        raise HTTPException(503, "Live stream not ready")
    forecast = _LIVE.aggregate_lstm_forecast(cursor)
    return {
        "cursor":     cursor,
        "forecast":   forecast,
        "horizon":    HORIZON,
        "model":      "lstm_embedding",
        "mape":       config.get("mape", 5.88),
        "ips_used":   len(_LIVE.ip_data),
    }


# ── The 4 agents (3 LLM specialists + 1 LLM judge) ───────────────────────────

class DecideRequest(BaseModel):
    history_24h:        List[float]       # last 24 hours of total bytes
    forecast_6h:        List[float]       # next 6h LSTM forecast
    capacity_mbph:      float = 500.0
    num_nodes:          int   = 4
    failed_nodes_count: int   = 0


def _fmt_series(values: List[float], unit: str = "MB/h") -> str:
    """Format a list of byte values as readable MB/h strings for LLM prompts."""
    return "[" + ", ".join(f"{v/1e6:.1f}" for v in values) + f"] {unit}"


def _trend_label(values: List[float]) -> str:
    """Simple trend description for the last 24h series."""
    if len(values) < 4:
        return "insufficient data"
    first_half  = np.mean(values[:len(values)//2])
    second_half = np.mean(values[len(values)//2:])
    pct = (second_half - first_half) / max(first_half, 1) * 100
    if pct > 15:   return f"rising sharply (+{pct:.0f}%)"
    if pct > 5:    return f"rising moderately (+{pct:.0f}%)"
    if pct < -15:  return f"falling sharply ({pct:.0f}%)"
    if pct < -5:   return f"falling moderately ({pct:.0f}%)"
    return f"stable ({pct:+.0f}%)"


def _rule_based_eco(req: DecideRequest) -> AgentProposal:
    """Fallback rule-based ECO (used if LLM call fails)."""
    cap_per_node_b = (req.capacity_mbph * 1_000_000) / max(req.num_nodes, 1)
    min_demand = min(req.forecast_6h) if req.forecast_6h else 0
    needed = max(int(np.ceil(min_demand / (cap_per_node_b * 0.80))), 1)
    active = req.num_nodes - req.failed_nodes_count
    sleep  = max(active - needed, 0)
    return AgentProposal(name="ECO", icon="🌱", color="#22C55E",
        sleep_count=sleep, confidence=0.75,
        reasoning=f"[fallback] Min forecast {min_demand/1e6:.0f} MB/h → need {needed} nodes → sleep {sleep}.")


def _rule_based_reliability(req: DecideRequest) -> AgentProposal:
    """Fallback rule-based RELIABILITY (used if LLM call fails)."""
    cap_per_node_b = (req.capacity_mbph * 1_000_000) / max(req.num_nodes, 1)
    peak = max(req.forecast_6h) if req.forecast_6h else 0
    needed = max(int(np.ceil(peak * 1.20 / (cap_per_node_b * 0.80))), 1)
    active = req.num_nodes - req.failed_nodes_count
    sleep  = max(active - needed, 0)
    return AgentProposal(name="RELIABILITY", icon="🛡", color="#3B82F6",
        sleep_count=sleep, confidence=0.75,
        reasoning=f"[fallback] Peak {peak/1e6:.0f} MB/h + 20% safety → need {needed} nodes → sleep {sleep}.")


def _rule_based_cost(req: DecideRequest) -> AgentProposal:
    """Fallback rule-based COST (used if LLM call fails)."""
    cap_per_node_b = (req.capacity_mbph * 1_000_000) / max(req.num_nodes, 1)
    avg = float(np.mean(req.forecast_6h)) if req.forecast_6h else 0
    needed = max(int(np.ceil(avg / (cap_per_node_b * 0.75))), 1)
    active = req.num_nodes - req.failed_nodes_count
    sleep  = max(active - needed, 0)
    return AgentProposal(name="COST", icon="💰", color="#F59E0B",
        sleep_count=sleep, confidence=0.75,
        reasoning=f"[fallback] Avg {avg/1e6:.0f} MB/h → need {needed} nodes → sleep {sleep}.")


def _call_gemini_agent(prompt: str, fallback: AgentProposal, max_sleep: int,
                       stagger_seconds: float = 0.0) -> AgentProposal:
    """
    Call Gemini for a single LLM specialist agent.
    Retries up to 3 times with exponential backoff on 429 rate-limit errors.
    stagger_seconds: initial delay before first attempt (spreads parallel calls).
    Falls back to rule-based result only if all retries fail.
    """
    if stagger_seconds > 0:
        time.sleep(stagger_seconds)

    last_error = None
    for attempt in range(3):
        try:
            payload = json.dumps({
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.55, "maxOutputTokens": 300},
            }).encode("utf-8")
            req_obj = urllib.request.Request(
                GEMINI_URL, data=payload,
                headers={"Content-Type": "application/json"}, method="POST",
            )
            with urllib.request.urlopen(req_obj, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            # Strip markdown fences if present
            if text.startswith("```"):
                text = text.strip("`")
                if text.startswith("json"):
                    text = text[4:].strip()
            parsed = json.loads(text)
            # Validate and hard-clamp to valid range
            sleep = int(parsed.get("sleep_count", fallback.sleep_count))
            sleep = max(0, min(sleep, max_sleep))
            confidence = float(parsed.get("confidence", fallback.confidence))
            confidence = max(0.0, min(confidence, 1.0))
            reasoning = str(parsed.get("reasoning", fallback.reasoning))[:400]
            return AgentProposal(
                name=fallback.name, icon=fallback.icon, color=fallback.color,
                sleep_count=sleep, confidence=confidence, reasoning=reasoning,
            )
        except urllib.error.HTTPError as e:
            last_error = e
            if e.code == 429:
                wait = 2 ** (attempt + 1)   # 2s, 4s, 8s
                print(f"[{fallback.name} agent] 429 rate-limited — retrying in {wait}s (attempt {attempt+1}/3)")
                time.sleep(wait)
            else:
                print(f"[{fallback.name} agent] HTTP {e.code} error — using rule fallback")
                break
        except Exception as e:
            last_error = e
            print(f"[{fallback.name} agent] LLM error — using rule fallback: {e}")
            break

    print(f"[{fallback.name} agent] All retries exhausted ({last_error}) — using rule fallback")
    return fallback


def _eco_agent(req: DecideRequest) -> AgentProposal:
    """
    LLM-based ECO agent: aggressive green energy optimizer.
    Persona: sustainability-first, willing to take calculated risks to save power.
    """
    active       = req.num_nodes - req.failed_nodes_count
    cap_node_mb  = req.capacity_mbph / max(req.num_nodes, 1)
    total_cap_mb = req.capacity_mbph
    fallback     = _rule_based_eco(req)

    prompt = f"""You are the ECO agent — an aggressive green energy optimizer for a telecom network.

YOUR MANDATE: Put as many cell tower nodes into eco-sleep as possible to save energy.
You care about sustainability above all. You accept moderate risk if it means saving power.

NETWORK STATE:
- Total nodes: {req.num_nodes} | Currently active: {active} | Failed: {req.failed_nodes_count}
- Total capacity: {total_cap_mb:.0f} MB/h | Capacity per node: {cap_node_mb:.1f} MB/h
- Last 24h traffic trend: {_trend_label(req.history_24h)}
- Last 24h actual traffic: {_fmt_series(req.history_24h)}
- LSTM forecast next 6h:  {_fmt_series(req.forecast_6h)}

FORECAST ANALYSIS:
- Forecast minimum: {min(req.forecast_6h)/1e6:.1f} MB/h
- Forecast maximum: {max(req.forecast_6h)/1e6:.1f} MB/h
- Forecast average: {float(np.mean(req.forecast_6h))/1e6:.1f} MB/h

YOUR GOAL: Propose the maximum number of nodes to sleep while keeping load under 85%.
Argue your case from an energy efficiency perspective. Be bold — sleeping nodes saves real energy.

Respond with JSON only (no markdown):
{{"sleep_count": <integer 0-{active}>, "confidence": <float 0.0-1.0>, "reasoning": "<1-2 sentences from your energy-saving perspective>"}}"""

    return _call_gemini_agent(prompt, fallback, max_sleep=active, stagger_seconds=0.0)


def _reliability_agent(req: DecideRequest) -> AgentProposal:
    """
    LLM-based RELIABILITY agent: conservative QoS guardian.
    Persona: SLA-obsessed, never wants to risk a breach, prioritizes headroom.
    """
    active       = req.num_nodes - req.failed_nodes_count
    cap_node_mb  = req.capacity_mbph / max(req.num_nodes, 1)
    total_cap_mb = req.capacity_mbph
    fallback     = _rule_based_reliability(req)

    prompt = f"""You are the RELIABILITY agent — a conservative QoS guardian for a telecom network.

YOUR MANDATE: Guarantee service quality at all times. Never let load breach capacity.
You prioritize SLA compliance above cost or energy. You demand safety margins.

NETWORK STATE:
- Total nodes: {req.num_nodes} | Currently active: {active} | Failed: {req.failed_nodes_count}
- Total capacity: {total_cap_mb:.0f} MB/h | Capacity per node: {cap_node_mb:.1f} MB/h
- Last 24h traffic trend: {_trend_label(req.history_24h)}
- Last 24h actual traffic: {_fmt_series(req.history_24h)}
- LSTM forecast next 6h:  {_fmt_series(req.forecast_6h)}
- LSTM model MAPE: 5.88% (forecast has inherent error — plan for it)

FORECAST ANALYSIS:
- Forecast minimum: {min(req.forecast_6h)/1e6:.1f} MB/h
- Forecast maximum: {max(req.forecast_6h)/1e6:.1f} MB/h
- Forecast average: {float(np.mean(req.forecast_6h))/1e6:.1f} MB/h

YOUR GOAL: Propose the MINIMUM number of nodes to sleep — keep as many awake as possible.
Account for forecast uncertainty. Add a safety margin. Argue from a reliability perspective.

Respond with JSON only (no markdown):
{{"sleep_count": <integer 0-{active}>, "confidence": <float 0.0-1.0>, "reasoning": "<1-2 sentences from your QoS/SLA perspective>"}}"""

    return _call_gemini_agent(prompt, fallback, max_sleep=active, stagger_seconds=5.0)


def _cost_agent(req: DecideRequest) -> AgentProposal:
    """
    LLM-based COST agent: FinOps analyst minimizing total cost of ownership.
    Persona: pragmatic, balances switching cost vs energy savings, avoids churn.
    """
    active       = req.num_nodes - req.failed_nodes_count
    cap_node_mb  = req.capacity_mbph / max(req.num_nodes, 1)
    total_cap_mb = req.capacity_mbph
    fallback     = _rule_based_cost(req)

    # Estimate how many wake/sleep transitions recently (proxy for switching cost)
    forecast_variance = float(np.std(req.forecast_6h)) / 1e6 if req.forecast_6h else 0

    prompt = f"""You are the COST agent — a FinOps analyst for a telecom network.

YOUR MANDATE: Minimize total cost of ownership. Balance energy savings against switching costs.
Every time a node wakes or sleeps, there is hardware wear and reconfiguration overhead.
You prefer stable, predictable configurations over aggressive toggling.

NETWORK STATE:
- Total nodes: {req.num_nodes} | Currently active: {active} | Failed: {req.failed_nodes_count}
- Total capacity: {total_cap_mb:.0f} MB/h | Capacity per node: {cap_node_mb:.1f} MB/h
- Last 24h traffic trend: {_trend_label(req.history_24h)}
- Last 24h actual traffic: {_fmt_series(req.history_24h)}
- LSTM forecast next 6h:  {_fmt_series(req.forecast_6h)}

FORECAST ANALYSIS:
- Forecast minimum: {min(req.forecast_6h)/1e6:.1f} MB/h
- Forecast maximum: {max(req.forecast_6h)/1e6:.1f} MB/h
- Forecast average: {float(np.mean(req.forecast_6h))/1e6:.1f} MB/h
- Forecast variability (std dev): {forecast_variance:.1f} MB/h
  {"⚠ HIGH variability — frequent wakeups likely, switching cost is high" if forecast_variance > 50 else "✓ Low variability — stable config is viable"}

YOUR GOAL: Propose a balanced sleep count that minimizes both energy waste AND switching churn.
If the forecast is volatile, sleeping fewer nodes avoids costly wake-up cycles.
Argue from a total cost of ownership perspective.

Respond with JSON only (no markdown):
{{"sleep_count": <integer 0-{active}>, "confidence": <float 0.0-1.0>, "reasoning": "<1-2 sentences from your FinOps/TCO perspective>"}}"""

    return _call_gemini_agent(prompt, fallback, max_sleep=active, stagger_seconds=10.0)


def _judge_with_gemini(proposals: List[AgentProposal], req: DecideRequest) -> tuple:
    """Synthesize the three proposals using Gemini. Falls back to weighted average."""
    sleep_options = [p.sleep_count for p in proposals]
    weights = [p.confidence for p in proposals]
    # Confidence-weighted average, rounded
    weighted = sum(s * w for s, w in zip(sleep_options, weights)) / sum(weights)
    final = int(round(weighted))

    fallback_reason = (
        f"Confidence-weighted consensus: ECO={proposals[0].sleep_count}, "
        f"RELIAB={proposals[1].sleep_count}, COST={proposals[2].sleep_count} → final {final}."
    )

    # Try Gemini for richer reasoning
    prompt = (
        "You are arbitrating between three network-operations agents about how many cell towers to put in eco-sleep mode.\n\n"
        f"ECO agent ({proposals[0].confidence:.2f} confidence): sleep {proposals[0].sleep_count}. "
        f"Reasoning: {proposals[0].reasoning}\n"
        f"RELIABILITY agent ({proposals[1].confidence:.2f} confidence): sleep {proposals[1].sleep_count}. "
        f"Reasoning: {proposals[1].reasoning}\n"
        f"COST agent ({proposals[2].confidence:.2f} confidence): sleep {proposals[2].sleep_count}. "
        f"Reasoning: {proposals[2].reasoning}\n\n"
        f"Forecast peak demand: {max(req.forecast_6h)/1e6:.0f} MB/h\n"
        f"Total capacity: {req.capacity_mbph} MB/h ({req.num_nodes} nodes)\n\n"
        f"Pick a final sleep_count between 0 and {req.num_nodes - req.failed_nodes_count}. "
        "Output JSON only: {\"sleep_count\": N, \"reasoning\": \"one short sentence\"}"
    )

    try:
        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 200},
        }).encode("utf-8")
        req_obj = urllib.request.Request(GEMINI_URL, data=payload,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req_obj, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:].strip()
        parsed = json.loads(text)
        return int(parsed["sleep_count"]), parsed.get("reasoning", fallback_reason)
    except Exception as e:
        print(f"[autopilot/judge] LLM fallback: {e}")
        return final, fallback_reason


# ── LangGraph multi-agent orchestration (4 LLM agents: 3 specialists + judge) ─
from langgraph.graph import StateGraph, START, END
from typing import TypedDict


class _AutopilotGraphState(TypedDict, total=False):
    history_24h:        list
    forecast_6h:        list
    capacity_mbph:      float
    num_nodes:          int
    failed_nodes_count: int
    eco_proposal:        dict
    reliability_proposal: dict
    cost_proposal:       dict
    judge_decision:      int
    judge_reasoning:     str


def _state_to_request(state) -> DecideRequest:
    return DecideRequest(
        history_24h=state.get("history_24h", []),
        forecast_6h=state.get("forecast_6h", []),
        capacity_mbph=state.get("capacity_mbph", 500.0),
        num_nodes=state.get("num_nodes", 4),
        failed_nodes_count=state.get("failed_nodes_count", 0),
    )


def _node_eco(state):
    p = _eco_agent(_state_to_request(state))
    return {"eco_proposal": p.dict()}


def _node_reliability(state):
    p = _reliability_agent(_state_to_request(state))
    return {"reliability_proposal": p.dict()}


def _node_cost(state):
    p = _cost_agent(_state_to_request(state))
    return {"cost_proposal": p.dict()}


def _node_judge(state):
    proposals = [
        AgentProposal(**state["eco_proposal"]),
        AgentProposal(**state["reliability_proposal"]),
        AgentProposal(**state["cost_proposal"]),
    ]
    final, reason = _judge_with_gemini(proposals, _state_to_request(state))
    return {"judge_decision": final, "judge_reasoning": reason}


# Build the graph: 3 agents run in PARALLEL, then converge at JUDGE
_workflow = StateGraph(_AutopilotGraphState)
_workflow.add_node("eco",         _node_eco)
_workflow.add_node("reliability", _node_reliability)
_workflow.add_node("cost",        _node_cost)
_workflow.add_node("judge",       _node_judge)

# Fan-out: all three from START in parallel
_workflow.add_edge(START, "eco")
_workflow.add_edge(START, "reliability")
_workflow.add_edge(START, "cost")
# Fan-in: all three to JUDGE
_workflow.add_edge("eco",         "judge")
_workflow.add_edge("reliability", "judge")
_workflow.add_edge("cost",        "judge")
_workflow.add_edge("judge", END)

_AUTOPILOT_GRAPH = _workflow.compile()
print("[auto-pilot] LangGraph compiled — 3 LLM specialist agents (ECO/RELIABILITY/COST) + 1 LLM judge (Gemini 2.0 Flash)")


@app.post("/autopilot/decide", response_model=AutopilotDecision)
def autopilot_decide(req: DecideRequest):
    """
    Run the 4 agents through LangGraph.
    Three specialists execute in parallel, then the judge synthesizes.
    """
    state_in = {
        "history_24h":        req.history_24h,
        "forecast_6h":        req.forecast_6h,
        "capacity_mbph":      req.capacity_mbph,
        "num_nodes":          req.num_nodes,
        "failed_nodes_count": req.failed_nodes_count,
    }
    final_state = _AUTOPILOT_GRAPH.invoke(state_in)

    proposals = [
        AgentProposal(**final_state["eco_proposal"]),
        AgentProposal(**final_state["reliability_proposal"]),
        AgentProposal(**final_state["cost_proposal"]),
    ]
    cap_per_node_b = (req.capacity_mbph * 1_000_000) / max(req.num_nodes, 1)
    return AutopilotDecision(
        agents          = proposals,
        judge_choice    = final_state["judge_decision"],
        judge_reasoning = final_state["judge_reasoning"],
        forecast_6h     = req.forecast_6h,
        capacity_per_node_bytes = cap_per_node_b,
    )


# ── Sentinel — rule-based (cheap, runs every tick) ───────────────────────────

class SentinelRequest(BaseModel):
    actual_recent: List[float]    # last few measured values
    predicted_recent: List[float] # what we predicted those values would be
    threshold_pct: float = 30.0


@app.post("/autopilot/sentinel", response_model=SentinelStatus)
def autopilot_sentinel(req: SentinelRequest):
    if not req.actual_recent or not req.predicted_recent:
        return SentinelStatus(delta_pct=0, status="normal", consecutive_bad=0)
    n = min(len(req.actual_recent), len(req.predicted_recent))
    deltas = []
    for i in range(n):
        a = req.actual_recent[-(i + 1)]
        p = req.predicted_recent[-(i + 1)]
        if p > 0:
            deltas.append(abs(a - p) / p * 100)
    if not deltas:
        return SentinelStatus(delta_pct=0, status="normal", consecutive_bad=0)
    last_delta = deltas[0]
    consec = 0
    for d in deltas:
        if d > req.threshold_pct:
            consec += 1
        else:
            break
    if consec >= 2:
        status = "anomaly"
    elif last_delta > req.threshold_pct:
        status = "warning"
    else:
        status = "normal"
    return SentinelStatus(
        delta_pct=round(last_delta, 1),
        status=status,
        consecutive_bad=consec,
    )


# ── Medic — generates emergency recovery plan via Gemini ─────────────────────

class MedicRequest(BaseModel):
    current_load_pct: float
    forecast_peak_pct: float
    affected_segment: Optional[str] = None
    nodes_active: int
    nodes_total: int


@app.post("/autopilot/medic", response_model=MedicPlan)
def autopilot_medic(req: MedicRequest):
    fallback = MedicPlan(
        diagnosis=f"Load at {req.current_load_pct:.0f}% — exceeds forecast {req.forecast_peak_pct:.0f}%.",
        actions=[
            f"Wake all sleeping nodes (target: {req.nodes_total} active)",
            "Throttle low-priority segments to 50%",
            "Notify on-call ops engineer",
        ],
        eta_seconds=90,
    )

    seg_msg = f" affecting {req.affected_segment}" if req.affected_segment else ""
    prompt = (
        f"Network anomaly detected{seg_msg}.\n"
        f"Current load: {req.current_load_pct:.0f}%, forecast was {req.forecast_peak_pct:.0f}%.\n"
        f"Active nodes: {req.nodes_active}/{req.nodes_total}.\n\n"
        "Provide a JSON emergency response: {\"diagnosis\": \"one sentence\", "
        "\"actions\": [\"action 1\", \"action 2\", \"action 3\"], \"eta_seconds\": int}\n"
        "Be terse and tactical. JSON only."
    )

    try:
        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 250},
        }).encode("utf-8")
        req_obj = urllib.request.Request(GEMINI_URL, data=payload,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req_obj, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:].strip()
        parsed = json.loads(text)
        return MedicPlan(
            diagnosis=parsed.get("diagnosis", fallback.diagnosis),
            actions=parsed.get("actions", fallback.actions)[:5],
            eta_seconds=int(parsed.get("eta_seconds", 90)),
        )
    except Exception as e:
        print(f"[autopilot/medic] LLM fallback: {e}")
        return fallback


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
