# ─────────────────────────────────────────────────────────────────────────────
# pages/forecasting_interface.py — Traffic Forecasting Page (Dashboard)
#
# Reads the CSV from st.session_state["df"] (uploaded on the Upload page).
# Sends the last 24 hourly rows to the forecasting FastAPI on port 8002.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import os
import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go


# ── Constants ─────────────────────────────────────────────────────────────────

API_URL = "http://127.0.0.1:8002"

FEATURES = [
    "n_flows", "n_packets", "n_bytes",
    "sum_n_dest_asn", "average_n_dest_asn",
    "sum_n_dest_ports", "average_n_dest_ports",
    "sum_n_dest_ip", "average_n_dest_ip",
    "tcp_udp_ratio_packets", "tcp_udp_ratio_bytes",
    "dir_ratio_packets", "dir_ratio_bytes",
    "avg_duration", "avg_ttl",
]

TIMES_CSV_CANDIDATES = [
    os.path.join(os.getcwd(), "..", "times", "times", "times_1_hour.csv"),
    os.path.join(os.getcwd(), "times", "times", "times_1_hour.csv"),
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def find_times_csv() -> str | None:
    for path in TIMES_CSV_CANDIDATES:
        full = os.path.abspath(path)
        if os.path.exists(full):
            return full
    return None


def call_predict(ip_filename: str, raw_data: list):
    try:
        r = requests.post(
            f"{API_URL}/predict",
            json={"ip_filename": ip_filename, "last_24h_data": raw_data},
            timeout=30,
        )
        if r.status_code == 200:
            return r.json(), None
        return None, f"API error {r.status_code}: {r.text}"
    except requests.exceptions.ConnectionError:
        return None, (
            "Cannot connect to the forecasting API. "
            "Make sure it is running: `uvicorn utils.forecasting_api:app --port 8002`"
        )
    except Exception as e:
        return None, f"Unexpected error: {str(e)}"


def call_model_info():
    try:
        r = requests.get(f"{API_URL}/model-info", timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


# ═════════════════════════════════════════════════════════════════════════════
# PAGE LAYOUT
# ═════════════════════════════════════════════════════════════════════════════

st.title("Traffic Forecasting")
st.caption(
    "Predict the next 6 hours of network traffic using LSTM + IP Embedding"
)
st.divider()


# ── Guard: dataset must be uploaded first ─────────────────────────────────────

if "df" not in st.session_state:
    st.warning(
        "No dataset loaded. "
        "Please go to the **Upload** page first and upload a per-IP CSV file."
    )
    st.stop()

df = st.session_state["df"]
file_name = st.session_state.get("file_name", "unknown.csv")

# validate that this CSV has the columns the model expects
missing = [f for f in FEATURES if f not in df.columns]
if missing:
    st.error(
        f"The uploaded CSV is missing features needed for forecasting: "
        f"`{', '.join(missing)}`. "
        f"Please upload a per-IP hourly CSV from `agg_1_hour/`."
    )
    st.stop()

if "id_time" not in df.columns:
    st.error(
        "Missing `id_time` column. "
        "Please upload a per-IP hourly CSV from `agg_1_hour/`."
    )
    st.stop()

st.success(
    f"Using **{file_name}** — {len(df)} rows loaded."
)


# ── Merge with timestamps ────────────────────────────────────────────────────

times_path = find_times_csv()
has_time = False

if times_path:
    times_df = pd.read_csv(times_path)
    times_df["time"] = pd.to_datetime(times_df["time"])
    df = df.merge(times_df, on="id_time", how="left")
    df = df.sort_values("time").reset_index(drop=True)
    has_time = True
else:
    df = df.sort_values("id_time").reset_index(drop=True)

if len(df) < 24:
    st.error(f"Need at least 24 hourly rows for a forecast, got {len(df)}.")
    st.stop()


# ── Prepare input ─────────────────────────────────────────────────────────────

df_last24 = df.tail(24).reset_index(drop=True)
raw_data = df_last24[FEATURES].values.tolist()
ip_filename = file_name.replace(".csv", "")

n_bytes_log = np.log1p(df_last24["n_bytes"].values)
smoothed_actual = (
    pd.Series(n_bytes_log).rolling(6, min_periods=1).mean().values
)

if has_time:
    timestamps = pd.to_datetime(df_last24["time"]).tolist()
    last_ts = timestamps[-1]
    forecast_times = pd.date_range(
        start=last_ts + pd.Timedelta(hours=1), periods=6, freq="h"
    ).tolist()
else:
    timestamps = list(range(-24, 0))
    forecast_times = list(range(0, 6))

st.divider()


# ── Run forecast ──────────────────────────────────────────────────────────────

if st.button("Run Forecast", use_container_width=True, type="primary"):

    with st.spinner("Running 6-hour forecast…"):
        result, error = call_predict(ip_filename, raw_data)

    if error:
        st.error(f"Error: {error}")
        st.stop()

    # save result to session state so it persists across reruns
    st.session_state["forecast_result"] = result


# ── Display results if available ──────────────────────────────────────────────

if "forecast_result" in st.session_state:
    result = st.session_state["forecast_result"]
    predictions = result["predictions"]

    if not result.get("ip_known", True):
        st.warning(
            f"⚠️ IP '{ip_filename}' was not seen during training. "
            "Using fallback embedding (ID=0). Predictions may be less accurate."
        )

    # ── Chart ─────────────────────────────────────────────────────────────

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=timestamps, y=smoothed_actual.tolist(),
        mode="lines+markers",
        name="Actual (smoothed)",
        line=dict(color="#2196F3", width=2),
        marker=dict(size=4),
    ))

    fig.add_trace(go.Scatter(
        x=forecast_times, y=predictions,
        mode="lines+markers",
        name="Forecast",
        line=dict(color="#FF5722", width=2.5, dash="dash"),
        marker=dict(size=6, symbol="diamond"),
    ))

    fig.add_trace(go.Scatter(
        x=[timestamps[-1], forecast_times[0]],
        y=[float(smoothed_actual[-1]), predictions[0]],
        mode="lines",
        line=dict(color="#888", width=1, dash="dot"),
        showlegend=False,
    ))

    fig.update_layout(
        title="Network Traffic: Last 24h Actual + 6h Forecast",
        xaxis_title="Time" if has_time else "Hour (relative)",
        yaxis_title="log1p(n_bytes) — smoothed",
        template="plotly_dark",
        height=460,
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="center", x=0.5,
        ),
        margin=dict(l=60, r=20, t=60, b=40),
    )

    st.plotly_chart(fig, use_container_width=True)

    # ── Metrics + Table ───────────────────────────────────────────────────

    col_left, col_right = st.columns([1, 2])

    with col_left:
        st.markdown("### Metrics")
        st.metric("Model MAPE", f"{result['mape']}%")
        st.metric("Horizon", f"{len(predictions)} hours")
        st.metric(
            "IP Status",
            "Known" if result.get("ip_known", True) else "Unseen (fallback)",
        )

    with col_right:
        st.markdown("### Predictions per Hour")
        pred_df = pd.DataFrame({
            "Hour Ahead": result["horizon_hours"],
            "Predicted (log scale)": [f"{v:.4f}" for v in predictions],
            "≈ n_bytes (expm1)": [f"{np.expm1(v):,.0f}" for v in predictions],
        })
        st.dataframe(pred_df, use_container_width=True, hide_index=True)

    # ── Input data ────────────────────────────────────────────────────────

    with st.expander("View input data (last 24 hours)"):
        st.dataframe(df_last24, use_container_width=True)

    with st.expander("View raw API response"):
        st.json(result)

else:
    st.info("Click **Run Forecast** above to generate a 6-hour prediction.")

    # show model info while waiting
    model_info = call_model_info()
    if model_info:
        st.divider()
        st.subheader("Model Information")

        color = "#1D9E75"
        st.markdown(f"""
        <div style="
            background:{color}12; border-left:4px solid {color};
            border-radius:8px; padding:18px 20px; margin-bottom:12px;">
            <h4 style="margin:0 0 8px 0;color:{color};">
                {model_info.get("model_name", "LSTM + IP Embedding")}
            </h4>
            <p style="margin:0;color:#aaa;font-size:13px;">
                {model_info.get("task", "")} · Dataset: {model_info.get("dataset", "")}
            </p>
        </div>
        """, unsafe_allow_html=True)

        arch = model_info.get("architecture", {})
        metrics = model_info.get("metrics", {})
        c1, c2, c3 = st.columns(3)
        c1.metric("Input", f"{arch.get('seq_len', 24)}h × {arch.get('n_features', 15)} feat")
        c2.metric("Output", f"{arch.get('horizon', 6)}h forecast")
        c3.metric("MAPE", metrics.get("mape", "12.22%"))
