import joblib
import pandas as pd
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Any
import uvicorn
import traceback
# Traffic Classification Update
app = FastAPI(title="QoSBuddy Engine")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 1. ASSET LOADING ---
try:
    # Add 'artifacts/' before each filename
    model = joblib.load('artifacts/persona_model.pkl')
    scaler = joblib.load('artifacts/scaler.joblib')
    le = joblib.load('artifacts/label_encoder.joblib')
    print("Assets Loaded.")
except Exception as e:
    print(f"Load Error: {e}")
class TrafficPoint(BaseModel):
    n_bytes: Any = 0
    tcp_udp_ratio_packets: Any = 0
    avg_duration: Any = 0
    sum_n_dest_ip: Any = 0

@app.post("/classify_content")
async def classify_content(data: List[TrafficPoint]):
    try:
        df = pd.DataFrame([item.dict() for item in data])
        for col in ['n_bytes', 'tcp_udp_ratio_packets', 'avg_duration', 'sum_n_dest_ip']:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # Feature Aggregation
        avg_vol = float(df['n_bytes'].mean())
        peak_vol = float(df['n_bytes'].max())
        tcp_udp = float(df['tcp_udp_ratio_packets'].mean())
        duration = float(df['avg_duration'].mean())
        n_dest = float(df['sum_n_dest_ip'].mean())

        # Logic for 1-row files
        num_rows = len(df)
        if num_rows > 1:
            burst_idx = float(df['n_bytes'].std() / (avg_vol + 1e-9))
            subset_size = max(1, int(num_rows * 0.3))
            evening_vol = df['n_bytes'].tail(subset_size).mean()
            evening_ratio = float(evening_vol / (avg_vol + 1e-9))
        else:
            burst_idx = 0.0
            evening_ratio = 1.0

        # Features array
        features = np.nan_to_num(np.array([[avg_vol, burst_idx, peak_vol, evening_ratio, tcp_udp, duration, n_dest]]))

        # Inference
        features_scaled = scaler.transform(features)
        prediction = model.predict(features_scaled)
        category = le.inverse_transform([int(prediction[0])])[0]

        # --- IMPORTANT: KEY NAMES MUST MATCH THE FRONTEND ---
        return {
            "classification": str(category),
            "profile": {
                "avg_traffic_bytes": round(avg_vol, 2),
                "burstiness_score": round(burst_idx, 4),
                "evening_intensity": f"{round(evening_ratio * 100, 1)}%",
                "avg_duration": round(duration, 2),
                "destinations_contacted": int(n_dest),
                "protocol_ratio": round(tcp_udp, 3)
            }
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
