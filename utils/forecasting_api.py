# ─────────────────────────────────────────────────────────────────────────────
# utils/forecasting_api.py — Traffic Forecasting FastAPI
#
# Run:
#   uvicorn utils.forecasting_api:app --port 8004 --reload
# ─────────────────────────────────────────────────────────────────────────────

import os
import pickle
import numpy as np
import urllib.request
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

GEMINI_KEY = "AIzaSyCeGy3r_wrnWKKXNrFnjzY2BJRwnTUFQvw"
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
        with urllib.request.urlopen(req_obj, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        explanation = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        explanation = f"AI explanation unavailable ({e})."

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
