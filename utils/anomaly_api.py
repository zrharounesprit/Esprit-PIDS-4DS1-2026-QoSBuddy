from pydantic import BaseModel
import joblib
import warnings 
import shap
warnings.filterwarnings("ignore")
from pathlib import Path

from fastapi import FastAPI

app = FastAPI()
model = None
scaler = None
explainer = None

class Observation(BaseModel):
    n_bytes: float
    n_packets: float
    n_flows: float
    tcp_udp_ratio_packets: float
    dir_ratio_packets: float

@app.on_event("startup")
def _load_artifacts():
    global model, scaler, explainer
    artifacts_dir = Path(__file__).resolve().parents[1] / "artifacts"
    model = joblib.load(artifacts_dir / "anomaly_model.pkl")
    scaler = joblib.load(artifacts_dir / "anomaly_scaler.pkl")
    explainer = shap.TreeExplainer(model)

def process_observation(obs_dict):
    import pandas as pd
    
    df = pd.DataFrame([obs_dict])
    
    # Scale
    X_scaled = scaler.transform(df)
    
    # Predict
    score = model.decision_function(X_scaled)[0]
    label = model.predict(X_scaled)[0]
    
    return score, label, df

def get_explanation(df):
    X_scaled = scaler.transform(df)
    shap_values = explainer.shap_values(X_scaled)
    
    contributions = dict(zip(df.columns, shap_values[0]))
    
    return contributions

def compute_severity(score, obs):
    severity = abs(score) * 10 + obs["n_bytes"] / 1e7
    
    if severity > 15:
        return "HIGH"
    elif severity > 8:
        return "MEDIUM"
    else:
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
    return "\n".join(f"{f}" for f in findings)

def generate_report(anomaly, severity, contributions, recommendation):
    if not anomaly:
        return "No anomaly detected. Network behavior is normal."
    
    top_features = sorted(contributions.items(), key=lambda x: abs(x[1]), reverse=True)[:2]
    
    explanation = ", ".join([f"{f}" for f, _ in top_features])
    
    return f"""
    An anomaly has been detected.

    Severity: {severity}

    Main contributing factors: {explanation}

    Recommended action: {recommendation}
    """

@app.post("/predict_anomaly")
def predict(obs: Observation):
    obs_dict = obs.model_dump()
    
    score, label, df = process_observation(obs_dict)
    
    anomaly = (label == -1)
    
    if not anomaly:
        return {
            "anomaly": False,
            "message": "Normal behavior"
        }
    
    contributions = get_explanation(df)
    severity = compute_severity(score, obs_dict)
    recommendation = generate_recommendation(contributions)
    report = generate_report(anomaly, severity, contributions, recommendation)
    
    return {
        "anomaly": True,
        "severity": severity,
        "score": score,
        "contributions": contributions,
        "recommendation": recommendation,
        "report": report
    }

#Testing : Works
#row= {"n_bytes":61174854, "n_packets":54760, "n_flows":4, "tcp_udp_ratio_packets":1.0, "dir_ratio_packets":0.22}
#result= process_observation(row)
#print(generate_report(result[0],compute_severity(result[1],row),get_explanation(result[2]),generate_recommendation(get_explanation(result[2]))))
