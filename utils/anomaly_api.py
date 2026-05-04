import os
import warnings
import shap
import joblib
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

warnings.filterwarnings("ignore")

# ── Absolute artifact paths — works regardless of working directory ───────────
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ARTIFACTS = os.path.join(_ROOT, "artifacts")

app = FastAPI(title="QoSBuddy Anomaly API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Observation(BaseModel):
    n_bytes: float
    n_packets: float
    n_flows: float
    tcp_udp_ratio_packets: float
    dir_ratio_packets: float


# ── Load model artifacts at startup ──────────────────────────────────────────
try:
    model  = joblib.load(os.path.join(_ARTIFACTS, "anomaly_model.pkl"))
    scaler = joblib.load(os.path.join(_ARTIFACTS, "anomaly_scaler.pkl"))
    explainer = shap.TreeExplainer(model)
    print("✅ Anomaly model + scaler loaded.")
except FileNotFoundError as e:
    model = scaler = explainer = None
    print(f"❌ Anomaly artifact missing: {e}")
except Exception as e:
    model = scaler = explainer = None
    print(f"❌ Anomaly load error: {e}")


def _require_ready():
    if model is None:
        raise HTTPException(503, detail="Anomaly model not loaded. Check artifacts/anomaly_model.pkl")


def process_observation(obs_dict):
    import pandas as pd
    df = pd.DataFrame([obs_dict])
    X_scaled = scaler.transform(df)
    score = model.decision_function(X_scaled)[0]
    label = model.predict(X_scaled)[0]
    return score, label, df


def get_explanation(df):
    X_scaled = scaler.transform(df)
    shap_values = explainer.shap_values(X_scaled)
    return dict(zip(df.columns, shap_values[0]))


def compute_severity(score, obs):
    severity = abs(score) * 10 + obs["n_bytes"] / 1e7
    if severity > 15:
        return "HIGH"
    elif severity > 8:
        return "MEDIUM"
    return "LOW"


def generate_recommendation(contributions):
    findings = []
    top_feature = max(contributions, key=lambda k: abs(contributions[k]))

    if top_feature in ["n_bytes", "n_packets"]:
        findings.append("Consider load balancing or rate limiting")
    if top_feature == "dir_ratio_packets":
        findings.append("Investigate flow imbalance")
    if top_feature == "tcp_udp_ratio_packets":
        findings.append("Check for unusual UDP/TCP behavior")
    if not findings:
        findings.append("Monitor the situation")

    return "\n".join(findings)


def generate_report(anomaly, severity, contributions, recommendation):
    if not anomaly:
        return "No anomaly detected. Network behavior is normal."

    top_features = sorted(contributions.items(), key=lambda x: abs(x[1]), reverse=True)[:2]
    explanation = ", ".join([f"{f}" for f, _ in top_features])

    return (
        f"An anomaly has been detected.\n\n"
        f"Severity: {severity}\n\n"
        f"Main contributing factors: {explanation}\n\n"
        f"Recommended action: {recommendation}"
    )


@app.get("/health")
def health():
    return {"ready": model is not None}


@app.post("/predict_anomaly")
def predict(obs: Observation):
    _require_ready()
    obs_dict = obs.model_dump()

    score, label, df = process_observation(obs_dict)
    anomaly = (label == -1)

    if not anomaly:
        return {"anomaly": False, "message": "Normal behavior"}

    contributions  = get_explanation(df)
    severity       = compute_severity(score, obs_dict)
    recommendation = generate_recommendation(contributions)
    report         = generate_report(anomaly, severity, contributions, recommendation)

    return {
        "anomaly": True,
        "severity": severity,
        "score": float(score),
        "contributions": {k: float(v) for k, v in contributions.items()},
        "recommendation": recommendation,
        "report": report,
    }
