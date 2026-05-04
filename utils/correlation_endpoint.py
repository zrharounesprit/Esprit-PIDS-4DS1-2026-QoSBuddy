from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import pandas as pd
import numpy as np
import pickle
import os

app = FastAPI(
    title="QOSBuddy — Correlation API",
    description=(
        "Correlation impact prediction "
        "for network KPIs"
    ),
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

BASE = os.path.join(
    os.path.dirname(__file__), '..', 'artifacts'
)

# ── Load single bundled artifact file ─────────────────────
with open(os.path.join(
    BASE, 'correlation_artifacts.pkl'
), 'rb') as f:
    _artifacts = pickle.load(f)

model          = _artifacts['model']
scaler         = _artifacts['scaler']
baseline_stats = _artifacts['baseline_stats']
raw_baseline   = _artifacts['raw_baseline']
cluster_data   = _artifacts['cluster_model']
risk_config    = _artifacts['risk_config']
explainer      = _artifacts['shap_explainer']
shap_columns   = _artifacts['shap_columns']
model_features = _artifacts['model_features']
pearson_corr   = _artifacts['pearson_corr']

# ── Fix ratio caps ─────────────────────────────────────────
for feat in ['tcp_udp_ratio_packets',
             'tcp_udp_ratio_bytes',
             'dir_ratio_packets',
             'dir_ratio_bytes']:
    if feat in baseline_stats.index:
        baseline_stats.loc[feat, 'normal_max'] = min(
            float(baseline_stats.loc[
                feat, 'normal_max']), 1.0
        )
        baseline_stats.loc[feat, 'normal_min'] = max(
            float(baseline_stats.loc[
                feat, 'normal_min']), 0.0
        )

# ── Strong pairs ───────────────────────────────────────────
STRONG_PAIRS = []
cols = pearson_corr.columns.tolist()
for i in range(len(cols)):
    for j in range(i + 1, len(cols)):
        v = float(pearson_corr.iloc[i, j])
        if abs(v) > 0.65:
            STRONG_PAIRS.append((cols[i], cols[j], v))

TOTAL_STRONG_PAIRS = max(len(STRONG_PAIRS), 1)

# ── Risk config ────────────────────────────────────────────
SUMABSZ_NORM    = risk_config['sumabsz_norm']
LOW_THRESH      = risk_config['low_threshold']
MED_THRESH      = risk_config['medium_threshold']
HIGH_THRESH     = risk_config['high_threshold']
W_SUMABSZ       = risk_config['w_sumabsz']
W_ANOMALY       = risk_config['w_anomaly']
W_BROKEN        = risk_config['w_broken']
BROKEN_Z_THRESH = risk_config['broken_z_thresh']

RAW_KPI_COLS = [
    'n_flows', 'n_packets', 'n_bytes',
    'sum_n_dest_ip', 'average_n_dest_ip',
    'sum_n_dest_ports', 'average_n_dest_ports',
    'sum_n_dest_asn', 'average_n_dest_asn',
    'tcp_udp_ratio_packets', 'tcp_udp_ratio_bytes',
    'dir_ratio_packets', 'dir_ratio_bytes',
    'avg_duration', 'avg_ttl'
]

print(f"API ready — "
      f"strong pairs: {TOTAL_STRONG_PAIRS}, "
      f"features: {len(model_features)}")

# ── Request model ──────────────────────────────────────────
class NetworkRow(BaseModel):
    scenario:               Optional[str]   = "unnamed"
    n_flows:                float
    n_packets:              float
    n_bytes:                float
    sum_n_dest_ip:          float
    average_n_dest_ip:      float
    sum_n_dest_ports:       float
    average_n_dest_ports:   float
    sum_n_dest_asn:         float
    average_n_dest_asn:     float
    tcp_udp_ratio_packets:  float
    tcp_udp_ratio_bytes:    float
    dir_ratio_packets:      float
    dir_ratio_bytes:        float
    avg_duration:           float
    avg_ttl:                float
    hour:                   Optional[float] = 12.0
    dayofweek:              Optional[float] = 0.0
    is_weekend:             Optional[float] = 0.0

class PredictionRequest(BaseModel):
    rows: List[NetworkRow]

# ── Helpers ────────────────────────────────────────────────
def raw_to_log(row_dict):
    result = {}
    for feat in model_features:
        if feat.startswith('log_'):
            raw_val = float(
                row_dict.get(feat[4:], 0)
            )
            result[feat] = float(
                np.log1p(max(raw_val, 0))
            )
        else:
            result[feat] = float(
                row_dict.get(feat, 0)
            )
    return result

def get_z(log_val, feat):
    # baseline_stats uses log_ prefixed names
    # if feat doesn't have log_ prefix, add it
    lookup = feat if feat in baseline_stats.index \
             else f'log_{feat}'
    if lookup not in baseline_stats.index:
        return 0.0
    m = float(baseline_stats.loc[lookup, 'mean'])
    s = float(baseline_stats.loc[lookup, 'std'])
    return round((log_val - m) / s, 3) if s > 0 \
           else 0.0

def compute_risk(sum_abs_z, n_anomalous,
                 n_broken, n_features,
                 total_pairs):
    """
    Three-component risk score:
    1. SumAbsZ component — total deviation energy
       Normalized against SUMABSZ_NORM (45.0)
    2. Anomaly rate — fraction of KPIs anomalous
    3. Broken correlation rate

    All three combined give a smooth 0-100 score.
    Thresholds: LOW<8, MEDIUM<18, HIGH<32, CRITICAL>=32
    """
    # Component 1: normalized total deviation
    sumabsz_score = min(
        sum_abs_z / SUMABSZ_NORM, 1.0
    )

    # Component 2: anomaly rate
    anomaly_score = min(
        n_anomalous / max(n_features, 1), 1.0
    )

    # Component 3: broken correlation rate
    broken_score = min(
        n_broken / max(total_pairs, 1), 1.0
    )

    # Weighted combination → 0 to 100
    raw = (
        sumabsz_score * W_SUMABSZ +
        anomaly_score * W_ANOMALY +
        broken_score  * W_BROKEN
    ) * 100.0

    return round(min(raw, 100.0), 1)

def risk_level(score):
    if score >= HIGH_THRESH:   return "CRITICAL"
    elif score >= MED_THRESH:  return "HIGH"
    elif score >= LOW_THRESH:  return "MEDIUM"
    return "LOW"

def risk_color(level):
    return {
        "CRITICAL": "#E74C3C",
        "HIGH":     "#E67E22",
        "MEDIUM":   "#F1C40F",
        "LOW":      "#5DCAA5"
    }.get(level, "#888")

# ── Endpoints ──────────────────────────────────────────────
@app.get("/health")
def health():
    return {
        "status":       "operational",
        "version":      "3.0.0",
        "strong_pairs": TOTAL_STRONG_PAIRS,
        "features":     len(model_features),
        "thresholds": {
            "low":      LOW_THRESH,
            "medium":   MED_THRESH,
            "high":     HIGH_THRESH
        }
    }

@app.get("/baseline")
def get_baseline():
    result = {}
    for col in RAW_KPI_COLS:
        if col not in raw_baseline.index:
            continue
        result[col] = {
            "mean":       round(float(
                raw_baseline.loc[col, 'mean']
            ), 4),
            "median":     round(float(
                raw_baseline.loc[col, '50%']
            ), 4),
            "std":        round(float(
                raw_baseline.loc[col, 'std']
            ), 4),
            "normal_min": round(float(
                raw_baseline.loc[col, 'normal_min']
            ), 4),
            "normal_max": round(float(
                raw_baseline.loc[col, 'normal_max']
            ), 4)
        }
    return {"kpis": result}

@app.get("/correlations")
def get_correlations(threshold: float = 0.65):
    pairs = []
    for feat_i, feat_j, val in STRONG_PAIRS:
        if abs(val) >= threshold:
            pairs.append({
                "kpi_1":      feat_i.replace(
                                  'log_', ''
                              ),
                "kpi_2":      feat_j.replace(
                                  'log_', ''
                              ),
                "pearson_r":  round(val, 4),
                "direction":  "positive"
                              if val > 0
                              else "negative",
                "strength":   "strong"
                              if abs(val) > 0.85
                              else "moderate",
                "confidence": min(99,
                    int(abs(val) * 100))
            })
    pairs.sort(
        key=lambda x: abs(x['pearson_r']),
        reverse=True
    )
    return {
        "total_pairs": len(pairs),
        "pairs":       pairs
    }

@app.post("/predict")
def predict(request: PredictionRequest):
    results = []

    for row in request.rows:
        row_dict = row.model_dump()
        scenario = row_dict.pop('scenario', 'unnamed')

        # ── Transform to log features ──────────────────────
        log_row = raw_to_log(row_dict)

        # ── 1. Deviation check ─────────────────────────────
        deviations     = {}
        anomalous_kpis = []
        sum_abs_z      = 0.0

        for feat in model_features:
            log_val = log_row[feat]
            z       = get_z(log_val, feat)
            nmin    = float(
                baseline_stats.loc[feat, 'normal_min']
            )
            nmax    = float(
                baseline_stats.loc[feat, 'normal_max']
            )
            is_anom = bool(
                log_val < nmin or log_val > nmax
            )

            # Raw value for display
            raw_val = float(
                row_dict.get(
                    feat[4:] if feat.startswith(
                        'log_'
                    ) else feat,
                    0
                )
            )

            sum_abs_z += abs(z)

            deviations[feat] = {
                "display_name": feat.replace(
                                     'log_', ''
                                 ),
                "raw_value":    round(raw_val, 4),
                "log_value":    round(log_val, 4),
                "z_score":      round(z, 3),
                "is_anomalous": is_anom,
                "normal_range": [
                    round(nmin, 3),
                    round(nmax, 3)
                ]
            }

            if is_anom:
                anomalous_kpis.append({
                    "kpi":       feat.replace(
                                     'log_', ''
                                 ),
                    "z_score":   round(z, 3),
                    "raw_value": round(raw_val, 4)
                })

        anomalous_kpis.sort(
            key=lambda x: abs(x['z_score']),
            reverse=True
        )

        # ── 2. Predict log_n_bytes ─────────────────────────
        feat_vals = np.array([
            log_row[f] for f in model_features
            if f != 'log_n_bytes'
        ]).reshape(1, -1)

        feat_scaled    = scaler.transform(feat_vals)
        pred_log_bytes = float(
            model.predict(feat_scaled)[0]
        )
        pred_bytes  = float(np.expm1(pred_log_bytes))
        actual_bytes = float(
            row_dict.get('n_bytes', 0)
        )
        actual_log  = float(
            np.log1p(max(actual_bytes, 0))
        )

        # ── 3. SHAP ────────────────────────────────────────
        shap_vals   = explainer.shap_values(
            feat_scaled
        )[0]
        shap_impact = sorted([
            {
                "kpi":       shap_columns[i].replace(
                                 'log_', ''
                             ),
                "impact":    round(
                                 float(shap_vals[i]),
                                 4
                             ),
                "direction": "pushes bytes UP"
                             if shap_vals[i] > 0
                             else "pushes bytes DOWN"
            }
            for i in range(len(shap_columns))
        ], key=lambda x: abs(x['impact']),
           reverse=True)

        # ── 4. Broken correlations ─────────────────────────
        # Threshold = 0.3 based on your data
        # Both z-scores must exceed threshold AND
        # point in opposite directions
        broken_correlations = []

        for feat_i, feat_j, expected_r in STRONG_PAIRS:
            if expected_r <= 0:
                continue

            zi = get_z(log_row.get(feat_i, log_row.get( f'log_{feat_i}', 0)), feat_i)
            zj = get_z(log_row.get(feat_j, log_row.get(f'log_{feat_j}', 0)), feat_j)

            if abs(zi) < BROKEN_Z_THRESH:
                continue
            if abs(zj) < BROKEN_Z_THRESH:
                continue
            if np.sign(zi) == np.sign(zj):
                continue

            severity = round(
                (abs(zi) + abs(zj)) / 2, 2
            )
            broken_correlations.append({
                "kpi_1":      feat_i.replace(
                                  'log_', ''
                              ),
                "kpi_2":      feat_j.replace(
                                  'log_', ''
                              ),
                "expected_r": round(expected_r, 3),
                "z_score_1":  round(zi, 2),
                "z_score_2":  round(zj, 2),
                "severity":   severity,
                "message": (
                    f"{feat_i.replace('log_','')} "
                    f"(z={zi:+.1f}σ) and "
                    f"{feat_j.replace('log_','')} "
                    f"(z={zj:+.1f}σ) should move "
                    f"together (r={expected_r:.2f})"
                    f" but are diverging"
                )
            })

        broken_correlations.sort(
            key=lambda x: x['severity'],
            reverse=True
        )

        # ── 5. Cluster ─────────────────────────────────────
        c_features = cluster_data['features']
        c_scaler   = cluster_data['scaler']
        c_model    = cluster_data['model']

        c_vals = []
        for f in c_features:
            if f in ['hour', 'dayofweek',
                     'is_weekend']:
                c_vals.append(
                    float(row_dict.get(f, 0))
                )
            elif f in log_row:
                c_vals.append(float(log_row[f]))
            else:
                c_vals.append(0.0)

        c_arr      = np.array(c_vals).reshape(1, -1)
        c_scaled   = c_scaler.transform(c_arr)
        cluster_id = int(
            c_model.predict(c_scaled)[0]
        )
        distances  = c_model.transform(c_scaled)[0]
        min_dist   = float(distances[cluster_id])
        confidence = round(
            float(1 / (1 + min_dist)) * 100, 1
        )

        # ── 6. Risk score using SumAbsZ ────────────────────
        risk_score = compute_risk(
            sum_abs_z      = round(sum_abs_z, 3),
            n_anomalous    = len(anomalous_kpis),
            n_broken       = len(broken_correlations),
            n_features     = len(model_features),
            total_pairs    = TOTAL_STRONG_PAIRS
        )
        level = risk_level(risk_score)

        results.append({
            "scenario":            scenario,
            "risk_score":          risk_score,
            "risk_level":          level,
            "risk_color":          risk_color(level),
            "cluster":             cluster_id,
            "cluster_confidence":  confidence,
            "predicted_n_bytes":   round(pred_bytes, 0),
            "actual_n_bytes":      actual_bytes,
            "pred_log_bytes":      round(
                                       pred_log_bytes,
                                       4
                                   ),
            "actual_log_bytes":    round(actual_log, 4),
            "sum_abs_z":           round(sum_abs_z, 2),
            "anomalous_kpis":      anomalous_kpis,
            "broken_correlations": broken_correlations,
            "top_shap_drivers":    shap_impact[:5],
            "kpi_deviations":      deviations,
            "debug": {
                "sum_abs_z":     round(sum_abs_z, 3),
                "n_anomalous":   len(anomalous_kpis),
                "n_broken":      len(broken_correlations),
                "n_features":    len(model_features),
                "total_pairs":   TOTAL_STRONG_PAIRS,
                "thresholds": {
                    "low":    LOW_THRESH,
                    "medium": MED_THRESH,
                    "high":   HIGH_THRESH
                }
            }
        })

    return {
        "total_rows":     len(results),
        "critical_count": sum(
            1 for r in results
            if r['risk_level'] == 'CRITICAL'
        ),
        "high_count": sum(
            1 for r in results
            if r['risk_level'] == 'HIGH'
        ),
        "results": results
    }

from typing import List, Dict, Any

@app.post("/anomaly")
async def anomaly_endpoint(data: List[Dict[str, Any]]):
    """
    Accepts a list of CSV rows (as dictionaries) and returns anomaly results.
    This endpoint is designed for the Streamlit frontend (member1_model.py).
    """
    # Convert each dict to a NetworkRow object, providing defaults for missing fields
    rows = []
    for row_dict in data:
        # Provide defaults for optional fields if not present
        row_dict.setdefault("scenario", "unnamed")
        row_dict.setdefault("hour", 12.0)
        row_dict.setdefault("dayofweek", 0.0)
        row_dict.setdefault("is_weekend", 0.0)
        
        # Ensure all required numeric fields exist (if missing, default to 0)
        required_fields = [
            "n_flows", "n_packets", "n_bytes", "sum_n_dest_ip", "average_n_dest_ip",
            "sum_n_dest_ports", "average_n_dest_ports", "sum_n_dest_asn", "average_n_dest_asn",
            "tcp_udp_ratio_packets", "tcp_udp_ratio_bytes", "dir_ratio_packets", "dir_ratio_bytes",
            "avg_duration", "avg_ttl"
        ]
        for field in required_fields:
            if field not in row_dict:
                row_dict[field] = 0.0
        
        # Create a NetworkRow object (Pydantic model)
        rows.append(NetworkRow(**row_dict))
    
    # Wrap into a PredictionRequest and call the existing predict logic
    request = PredictionRequest(rows=rows)
    return await predict(request)   # re-use existing /predict handler