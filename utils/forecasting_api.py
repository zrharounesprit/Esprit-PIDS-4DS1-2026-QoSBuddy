# ─────────────────────────────────────────────────────────────────────────────
# utils/forecasting_api.py — Traffic Forecasting FastAPI
#
# Run:
#   uvicorn utils.forecasting_api:app --port 8004 --reload
# ─────────────────────────────────────────────────────────────────────────────

import os
import pickle
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

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

# Features whose raw values must be log-transformed before standardisation.
# Determined by comparing scaler means against raw data magnitudes.
LOG_INDICES = {0, 1, 2, 3, 4, 5, 6, 7, 8, 14}

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(title="QoSBuddy Forecasting API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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

    raw = np.zeros((SEQ_LEN, len(FEATURES)))
    for t, row in enumerate(req.rows):
        for j, feat in enumerate(FEATURES):
            val = float(row.get(feat, 0.0))
            if j in LOG_INDICES:
                val = np.log(max(val, 1e-9))
            raw[t, j] = val

    X = (raw - feat_mean) / (feat_std + 1e-9)

    ts_input = X.reshape(1, SEQ_LEN, len(FEATURES)).astype(np.float32)
    id_input = np.array([[req.ip_id]], dtype=np.int32)

    pred_std = model.predict([ts_input, id_input], verbose=0)

    pred_log  = pred_std[0] * tgt_std + tgt_mean
    pred_real = np.exp(pred_log)

    return ForecastResponse(
        forecast=[round(float(v), 2) for v in pred_real],
        horizon=HORIZON,
        unit="n_bytes",
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
