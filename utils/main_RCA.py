import os
import json
import joblib
import numpy as np
import pandas as pd
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# UPDATE THIS PATH to wherever model.py saved your artifacts
# ─────────────────────────────────────────────────────────────────────────────
ARTIFACTS_DIR = "C:/Users/muaad/Documents/Lists/esprit/4ds1/QoSBuddy/qosbuddy_RCA/dashboard/artifacts"


# ── Load all artifacts once at startup ───────────────────────────────────────

print("Loading artifacts...")
km_model       = joblib.load(os.path.join(ARTIFACTS_DIR, "kmeans_model.pkl"))
scaler         = joblib.load(os.path.join(ARTIFACTS_DIR, "scaler.pkl"))
ip_profiles    = pd.read_parquet(os.path.join(ARTIFACTS_DIR, "ip_profiles.parquet"))
df_slim        = pd.read_parquet(os.path.join(ARTIFACTS_DIR, "df_slim.parquet"))
df_slim["time"] = pd.to_datetime(df_slim["time"], utc=True)

with open(os.path.join(ARTIFACTS_DIR, "profile_features.json")) as f:
    PROFILE_FEATURES = json.load(f)

# Set id_ip as index for fast lookup
ip_profiles = ip_profiles.set_index("id_ip")
print("All artifacts loaded. API is ready.")


# ── Cause definitions ─────────────────────────────────────────────────────────
# Same as in the notebook Section 15 — plain English, no jargon, no actions.

CAUSE_DESCRIPTIONS = {
    "extreme_scanner": {
        "title": "Extreme Traffic Scanner",
        "what_it_means": (
            "This device is reaching out to an extraordinarily large number of "
            "different destinations and ports every hour — far beyond what any "
            "normal computer, phone, or server would ever do. It is behaving "
            "like something that is deliberately trying to map or probe the "
            "network, or it is part of a larger attack originating from this IP."
        ),
        "evidence_template": [
            "contacts_destinations", "protocol_mix", "direction",
            "burstiness", "persistence", "peer_comparison",
        ],
    },
    "udp_suspicious": {
        "title": "Unusual Outbound UDP Traffic",
        "what_it_means": (
            "This device is sending a higher-than-normal amount of UDP traffic "
            "outward into the network. UDP is a protocol that does not require "
            "a formal connection — it just sends data without checking if anyone "
            "is listening. While UDP has normal uses like video calls and DNS, "
            "the pattern here is tilted enough away from the norm to stand out "
            "from the rest of the network population."
        ),
        "evidence_template": [
            "protocol_mix", "direction", "contacts_destinations",
            "burstiness", "persistence", "peer_comparison",
        ],
    },
    "congestion": {
        "title": "High Volume — Likely Congestion Source",
        "what_it_means": (
            "This device is consistently one of the heaviest traffic generators "
            "on the network. There is nothing suspicious about how it communicates "
            "— the protocol mix and direction look completely normal — but the "
            "sheer amount of data it moves every hour puts it in a different "
            "category from most other devices. When multiple IPs like this are "
            "active at the same time, they can slow down the network for everyone."
        ),
        "evidence_template": [
            "volume", "protocol_mix", "direction",
            "burstiness", "persistence", "peer_comparison",
        ],
    },
    "normal": {
        "title": "Normal Baseline Behaviour",
        "what_it_means": (
            "This device behaves exactly as expected for a standard user on this "
            "network. Its traffic volume, the mix of protocols it uses, and the "
            "range of destinations it contacts are all within the normal range "
            "observed across this network. If an anomaly was flagged for this IP, "
            "it was most likely a short-lived and isolated event rather than a "
            "persistent underlying problem."
        ),
        "evidence_template": [
            "volume", "protocol_mix", "direction",
            "contacts_destinations", "burstiness", "peer_comparison",
        ],
    },
}


# ── Input schema ──────────────────────────────────────────────────────────────
# This defines what the API expects as input.
# These are the raw features from one row of your CSV files.
# Every field has a default of None so you can send partial rows —
# missing fields will be handled gracefully.

class IPRow(BaseModel):
    id_ip: int = Field(..., description="The IP identifier from the dataset")

    # Volume features
    n_flows:   Optional[float] = Field(None, description="Number of flows in the hour")
    n_packets: Optional[float] = Field(None, description="Number of packets")
    n_bytes:   Optional[float] = Field(None, description="Number of bytes transmitted")

    # Destination diversity
    sum_n_dest_ip:    Optional[float] = Field(None, description="Total unique destination IPs")
    sum_n_dest_ports: Optional[float] = Field(None, description="Total unique destination ports")
    std_n_dest_ip:    Optional[float] = Field(None, description="Std dev of destination IPs")

    # Protocol ratios
    tcp_udp_ratio_packets: Optional[float] = Field(None, description="TCP/UDP ratio (1=all TCP, 0=all UDP)")
    tcp_udp_ratio_bytes:   Optional[float] = Field(None, description="TCP/UDP byte ratio")

    # Direction ratios
    dir_ratio_packets: Optional[float] = Field(None, description="Direction ratio (1=all outgoing)")
    dir_ratio_bytes:   Optional[float] = Field(None, description="Direction byte ratio")

    # Flow behaviour
    avg_duration: Optional[float] = Field(None, description="Average flow duration")
    avg_ttl:      Optional[float] = Field(None, description="Average Time To Live")

    class Config:
        json_schema_extra = {
            "example": {
                "id_ip": 95923,
                "n_flows": 82,
                "n_packets": 1289,
                "n_bytes": 248592,
                "sum_n_dest_ip": 68,
                "sum_n_dest_ports": 70,
                "std_n_dest_ip": 1.51,
                "tcp_udp_ratio_packets": 0.94,
                "tcp_udp_ratio_bytes": 0.96,
                "dir_ratio_packets": 0.52,
                "dir_ratio_bytes": 0.58,
                "avg_duration": 1.88,
                "avg_ttl": 123.72
            }
        }


# ── Feature engineering (mirrors the notebook exactly) ───────────────────────

def engineer_single_row(row: IPRow) -> dict:
    """
    Apply the same feature engineering from the notebook to a single input row.
    Returns a dict of engineered features ready for the scaler.
    """
    n_bytes   = row.n_bytes   or 0
    n_packets = row.n_packets or 0
    n_flows   = row.n_flows   or 0

    throughput_bps = (n_bytes * 8) / 3600

    # dest_spread — same logic as notebook Section 5c
    if row.sum_n_dest_ip is not None and row.sum_n_dest_ports is not None:
        dest_spread = row.sum_n_dest_ip + row.sum_n_dest_ports
    else:
        dest_spread = 0

    # udp_outgoing — same logic as notebook Section 5d
    tcp_ratio = row.tcp_udp_ratio_packets if row.tcp_udp_ratio_packets is not None else 1.0
    dir_ratio = row.dir_ratio_packets     if row.dir_ratio_packets     is not None else 0.5
    udp_outgoing = (1 - tcp_ratio) * dir_ratio

    # Log normalization — same as notebook Section 5e
    features = {
        "log_n_bytes":        np.log1p(n_bytes),
        "log_n_packets":      np.log1p(n_packets),
        "log_n_flows":        np.log1p(n_flows),
        "log_throughput_bps": np.log1p(throughput_bps),
        "tcp_udp_ratio_packets": tcp_ratio,
        "tcp_udp_ratio_bytes":   row.tcp_udp_ratio_bytes   or 1.0,
        "dir_ratio_packets":     dir_ratio,
        "dir_ratio_bytes":       row.dir_ratio_bytes        or 0.5,
        "log_dest_spread":    np.log1p(dest_spread),
        "udp_outgoing":       udp_outgoing,
        "burst_ratio":        1.0,        # cannot compute from a single row
        "std_n_dest_ip":      row.std_n_dest_ip or 0.0,
        "avg_ttl":            row.avg_ttl        or 0.0,
    }

    return features


# ── Helper functions (same as notebook Section 15) ────────────────────────────

def build_observations(feature_dict: dict, evidence_template: list) -> list:
    obs = {}

    log_bytes = feature_dict.get("log_n_bytes", 0)
    if log_bytes > 14:
        obs["volume"] = "It moves an extremely large amount of data — among the very heaviest users on this network."
    elif log_bytes > 11:
        obs["volume"] = "It moves a high amount of data — well above what most devices on this network do."
    elif log_bytes < 8:
        obs["volume"] = "It moves a relatively small amount of data — consistent with a light-use device."
    else:
        obs["volume"] = "Its data volume is moderate and sits within the expected range for a typical device."

    tcp_ratio = feature_dict.get("tcp_udp_ratio_packets", 1.0)
    if tcp_ratio < 0.2:
        obs["protocol_mix"] = "Almost all of its traffic uses UDP — highly unusual for a standard device and one of the strongest signals in its profile."
    elif tcp_ratio < 0.5:
        obs["protocol_mix"] = "A significant portion of its traffic uses UDP — more than what most normal devices send."
    elif tcp_ratio < 0.8:
        obs["protocol_mix"] = "It uses a mix of TCP and UDP, with slightly more UDP than a typical device."
    else:
        obs["protocol_mix"] = "It communicates almost entirely over TCP — standard for web browsing, email, and everyday applications."

    dir_ratio = feature_dict.get("dir_ratio_packets", 0.5)
    if dir_ratio > 0.75:
        obs["direction"] = "The vast majority of its traffic is outgoing — it sends much more than it receives, unusual for a client device."
    elif dir_ratio > 0.6:
        obs["direction"] = "Its traffic leans outbound — it sends noticeably more than it receives."
    elif dir_ratio < 0.25:
        obs["direction"] = "The vast majority of its traffic is incoming — it receives far more than it sends."
    elif dir_ratio < 0.4:
        obs["direction"] = "Its traffic leans inbound — it receives noticeably more than it sends."
    else:
        obs["direction"] = "Its traffic is well balanced between sending and receiving — consistent with normal two-way communication."

    log_dest = feature_dict.get("log_dest_spread", 0)
    if log_dest > 8:
        obs["contacts_destinations"] = "It contacts a massive number of unique destinations and ports — far beyond what any normal device would reach."
    elif log_dest > 5:
        obs["contacts_destinations"] = "It reaches a wider-than-average range of destinations, which is worth noting."
    else:
        obs["contacts_destinations"] = "It communicates with a small and consistent set of destinations — normal for a device with predictable usage."

    burst = feature_dict.get("burst_ratio", 1.0)
    if burst > 3.0:
        obs["burstiness"] = "Its traffic spikes dramatically at times — several times higher than its own average."
    elif burst > 1.8:
        obs["burstiness"] = "Its traffic volume shows noticeable spikes above its own baseline."
    else:
        obs["burstiness"] = "Its traffic volume is relatively steady over time, without dramatic spikes or drops."

    obs["persistence"] = "Persistence analysis requires historical data — use the /rca/ip/{id_ip} endpoint for full report."
    obs["peer_comparison"] = "Peer comparison is available in the full profile endpoint."

    return [obs[key] for key in evidence_template if key in obs]


def build_peer_context(id_ip: int, cause_label: str) -> str:
    if id_ip in ip_profiles.index:
        group = ip_profiles[ip_profiles["cause_label"] == cause_label]
        total = len(ip_profiles)
        pct   = round(len(group) / total * 100, 1)
        group_mean = group["log_n_bytes"].mean()
        this_val   = ip_profiles.loc[id_ip, "log_n_bytes"]
        if this_val > group_mean + 1.5:
            position = "and is one of the more extreme examples within this group"
        elif this_val < group_mean - 1.5:
            position = "and sits on the milder end of this group"
        else:
            position = "and is a fairly typical representative of this group"
        return (
            f"{len(group)} out of {total} IPs ({pct}%) share the same "
            f"root cause classification, {position}."
        )
    return "This IP is not in the pre-computed profile — peer context is unavailable for new IPs."


def build_chronicity(id_ip: int) -> str:
    ip_data = df_slim[df_slim["id_ip"] == id_ip].sort_values("time")
    if len(ip_data) < 20:
        return "There is not enough historical data for this IP to determine whether this is a new or long-standing pattern."

    cutoff  = ip_data["time"].max() - pd.Timedelta(weeks=2)
    recent  = ip_data[ip_data["time"] >= cutoff]
    historic = ip_data[ip_data["time"] < cutoff]

    if len(recent) < 5 or len(historic) < 5:
        return "Insufficient data in one of the time windows to make a reliable comparison."

    change_pct = ((recent["n_bytes"].mean() - historic["n_bytes"].mean())
                  / (historic["n_bytes"].mean() + 1)) * 100

    if change_pct > 80:
        return (
            f"This behaviour appears to be NEW. Traffic in the past two weeks is "
            f"roughly {abs(round(change_pct))}% higher than the device's historical "
            f"average — something changed recently."
        )
    elif change_pct < -60:
        return (
            f"This device has become significantly quieter recently — traffic dropped "
            f"roughly {abs(round(change_pct))}% compared to its historical average."
        )
    else:
        return (
            f"This behaviour is CHRONIC. Traffic levels are broadly consistent with "
            f"the device's long-term average (within {abs(round(change_pct))}%), "
            f"meaning this pattern has been present for an extended period."
        )


# ── Report builder ────────────────────────────────────────────────────────────

def build_report(id_ip: int, cause_label: str, feature_dict: dict) -> dict:
    definition = CAUSE_DESCRIPTIONS.get(cause_label, {})
    template   = definition.get("evidence_template", [])

    return {
        "id_ip"             : id_ip,
        "report_type"       : "Root Cause Analysis",
        "generated_at"      : datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "cause_label"       : cause_label,
        "cause_title"       : definition.get("title", cause_label),
        "what_it_means"     : definition.get("what_it_means", ""),
        "why_we_think_this" : build_observations(feature_dict, template),
        "chronic_or_new"    : build_chronicity(id_ip),
        "peer_context"      : build_peer_context(id_ip, cause_label),
    }


# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="QoSBuddy — Root Cause Analysis API",
    description=(
        "Takes a row of network traffic data and returns a human-readable "
        "root cause analysis report. Does not include anomaly detection — "
        "that is handled by a separate service."
    ),
    version="1.0.0",
)


# ── Endpoint 1: POST /rca ─────────────────────────────────────────────────────
# The main endpoint. You give it one row of raw features, it returns the report.
# Later, your friend's anomaly detection API will call this automatically
# whenever it flags an IP.

@app.post("/rca", summary="Classify root cause from a single data row")
def classify_root_cause(row: IPRow):
    """
    Send one row of raw network traffic features for a single IP.
    The API will:
    1. Engineer the same features used during training
    2. Scale them with the saved scaler
    3. Assign a cluster using the saved K-Means model
    4. Return a full human-readable RCA report
    """
    # Step 1: engineer features from the raw input row
    feature_dict = engineer_single_row(row)

    f# Step 2: build the full 26-column vector the scaler expects
    # The scaler was trained on mean + std columns combined.
    # For a single incoming row we have no std, so we fill those with 0.
    all_columns = list(ip_profiles.columns)
    all_columns = [c for c in all_columns
                   if c not in ("cluster", "cause_label")]

    row_values = {}
    for col in all_columns:
        if col in feature_dict:
            row_values[col] = feature_dict[col]
        else:
            row_values[col] = 0.0   # std columns default to 0

    feature_vector = pd.DataFrame([row_values], columns=all_columns)

    # Step 3: scale using the saved scaler
    scaled = scaler.transform(feature_vector)

    # Step 4: predict cluster
    cluster_id = int(km_model.predict(scaled)[0])

    # Step 5: map cluster to cause label
    # This uses the same CAUSE_LABELS from your notebook
    CAUSE_LABELS = {0: "extreme_scanner", 1: "udp_suspicious",
                    2: "normal", 3: "congestion"}
    cause_label = CAUSE_LABELS.get(cluster_id, "unknown")

    # Step 6: build and return the report
    return build_report(row.id_ip, cause_label, feature_dict)


# ── Endpoint 2: GET /rca/ip/{id_ip} ──────────────────────────────────────────
# Looks up a known IP from the pre-computed profiles.
# Power BI will call this when the user clicks "View Root Cause" on the dashboard.
# No feature input needed — the profile is already saved from training.

@app.get("/rca/ip/{id_ip}", summary="Get RCA report for a known IP by ID")
def get_rca_by_ip(id_ip: int):
    """
    Returns the full RCA report for an IP that was part of the training dataset.
    The cluster label and profile are loaded directly from the saved profiles file.
    No feature input required.
    """
    if id_ip not in ip_profiles.index:
        raise HTTPException(
            status_code=404,
            detail=f"IP {id_ip} was not found in the pre-computed profiles. "
                   f"Use POST /rca with raw features to classify a new IP."
        )

    row         = ip_profiles.loc[id_ip]
    cause_label = row["cause_label"]
    feature_dict = {col: row[col] for col in PROFILE_FEATURES if col in row.index}

    return build_report(id_ip, cause_label, feature_dict)


# ── Endpoint 3: GET /health ───────────────────────────────────────────────────
# Simple check to confirm the API is running and artifacts loaded correctly.

@app.get("/health", summary="Check API status")
def health_check():
    return {
        "status"           : "running",
        "model"            : "K-Means RCA Clustering",
        "ips_in_profiles"  : len(ip_profiles),
        "cause_types"      : list(CAUSE_DESCRIPTIONS.keys()),
        "features_expected": PROFILE_FEATURES,
    }
