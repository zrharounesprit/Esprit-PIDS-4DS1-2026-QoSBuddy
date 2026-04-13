# ─────────────────────────────────────────────────────────────────────────────
# pages/forecasting.py — Traffic Forecasting Page
#
# Reads the shared dataframe from st.session_state["df"], lets the user
# pick a 24-hour lookback window, sends it to the forecasting API on
# port 8003, and visualises the 6-hour forecast alongside historical data.
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go


# ── Constants ─────────────────────────────────────────────────────────────────
API_URL  = "http://127.0.0.1:8003"
SEQ_LEN  = 24
HORIZON  = 6

FEATURES = [
    "n_flows", "n_packets", "n_bytes",
    "sum_n_dest_asn", "average_n_dest_asn",
    "sum_n_dest_ports", "average_n_dest_ports",
    "sum_n_dest_ip", "average_n_dest_ip",
    "tcp_udp_ratio_packets", "tcp_udp_ratio_bytes",
    "dir_ratio_packets", "dir_ratio_bytes",
    "avg_duration", "avg_ttl",
]

ACCENT = "#2196F3"


# ── Helper: call FastAPI ──────────────────────────────────────────────────────
def run_forecast(rows: list, ip_id: int = 0):
    try:
        r = requests.post(
            f"{API_URL}/forecast",
            json={"rows": rows, "ip_id": ip_id},
            timeout=30,
        )
        if r.status_code == 200:
            return r.json(), None
        return None, f"API error {r.status_code}: {r.text}"
    except requests.exceptions.ConnectionError:
        return None, (
            "Cannot connect to the forecasting API. "
            "Make sure `forecasting_api.py` is running on port 8003."
        )
    except Exception as e:
        return None, f"Unexpected error: {e}"


# ── Helper: detect time column ────────────────────────────────────────────────
def detect_time_col(df):
    for col in ("time", "timestamp", "date", "datetime"):
        if col in df.columns:
            return col
    return None


# ── Helper: build Plotly chart ────────────────────────────────────────────────
def build_chart(hist_times, hist_values, fc_times, fc_values, time_label):
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=hist_times, y=hist_values,
        mode="lines+markers", name="Historical",
        line=dict(color="#1f77b4", width=2),
        marker=dict(size=4),
    ))

    fig.add_trace(go.Scatter(
        x=[hist_times[-1], fc_times[0]],
        y=[hist_values[-1], fc_values[0]],
        mode="lines", showlegend=False,
        line=dict(color=ACCENT, width=2, dash="dot"),
    ))

    fig.add_trace(go.Scatter(
        x=fc_times, y=fc_values,
        mode="lines+markers", name="Forecast",
        line=dict(color=ACCENT, width=2),
        marker=dict(size=8, symbol="diamond"),
    ))

    fig.update_layout(
        title="Network Traffic (n_bytes): Historical → Forecast",
        xaxis_title=time_label,
        yaxis_title="n_bytes",
        template="plotly_dark",
        height=460,
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1),
    )
    return fig


# ═════════════════════════════════════════════════════════════════════════════
# PAGE LAYOUT
# ═════════════════════════════════════════════════════════════════════════════

st.title("Traffic Forecasting")
st.caption(
    "Predict future network traffic volumes using an LSTM time-series model. "
    "The model uses a 24-hour lookback window to forecast the next 6 hours."
)

st.divider()

# ── Dataset check ─────────────────────────────────────────────────────────────
if "df" not in st.session_state:
    st.warning(
        "No dataset loaded. "
        "Please go to the **Upload** page first and upload a CSV file."
    )
    st.stop()

df = st.session_state["df"].copy()
st.success(
    f"Using **{st.session_state['file_name']}** — {len(df)} rows loaded."
)

# validate required columns
missing = [f for f in FEATURES if f not in df.columns]
if missing:
    st.error(f"Missing required columns: {', '.join(missing)}")
    st.stop()

if len(df) < SEQ_LEN:
    st.error(
        f"Need at least {SEQ_LEN} rows for forecasting. "
        f"Dataset has only {len(df)} rows."
    )
    st.stop()

# sort by time if possible
time_col = detect_time_col(df)
if time_col:
    df[time_col] = pd.to_datetime(df[time_col])
    df = df.sort_values(time_col).reset_index(drop=True)

st.divider()

# ── Window selection ──────────────────────────────────────────────────────────
max_start = len(df) - SEQ_LEN

start_idx = st.slider(
    "Start of the 24-hour lookback window",
    min_value=0, max_value=max_start, value=max_start,
    help=(
        f"Select which {SEQ_LEN} consecutive rows to feed into the model. "
        f"The model will forecast the next {HORIZON} hours."
    ),
)

window = df.iloc[start_idx : start_idx + SEQ_LEN]

with st.expander("View selected window"):
    st.dataframe(window, use_container_width=True)

# ── Advanced: IP embedding ────────────────────────────────────────────────────
with st.expander("Advanced: IP profile selection"):
    ip_id = st.number_input(
        "IP Embedding ID (0–999, 0 = default)",
        min_value=0, max_value=999, value=0,
    )

st.divider()

# ── Run Forecast ──────────────────────────────────────────────────────────────
if st.button("Run Forecast", use_container_width=True, type="primary"):
    rows = window[FEATURES].to_dict(orient="records")

    with st.spinner("Running LSTM forecast…"):
        result, error = run_forecast(rows, ip_id)

    if error:
        st.error(error)
    else:
        st.session_state["forecast_result"] = {
            "values": result["forecast"],
            "start_idx": start_idx,
        }

# ── Display results ───────────────────────────────────────────────────────────
if "forecast_result" in st.session_state:
    res = st.session_state["forecast_result"]
    fc_values = res["values"]

    win = df.iloc[res["start_idx"] : res["start_idx"] + SEQ_LEN]
    hist_bytes = win["n_bytes"].tolist()

    st.subheader("Forecast Results")

    # metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Avg Predicted", f"{np.mean(fc_values):,.0f} bytes")
    col2.metric("Peak Hour", f"{np.max(fc_values):,.0f} bytes")
    col3.metric("Min Hour", f"{np.min(fc_values):,.0f} bytes")

    last_actual = hist_bytes[-1]
    trend_pct = ((fc_values[0] - last_actual) / max(last_actual, 1)) * 100
    col4.metric("Next-Hour Trend", f"{trend_pct:+.1f}%")

    # build time axes
    if time_col and time_col in win.columns:
        hist_times = win[time_col].tolist()
        last_t = hist_times[-1]
        fc_times = [last_t + pd.Timedelta(hours=i + 1) for i in range(HORIZON)]
        time_label = "Time"
    else:
        hist_times = list(range(SEQ_LEN))
        fc_times = list(range(SEQ_LEN, SEQ_LEN + HORIZON))
        time_label = "Timestep"

    fig = build_chart(hist_times, hist_bytes, fc_times, fc_values, time_label)
    st.plotly_chart(fig, use_container_width=True)

    # forecast table
    if time_col and time_col in win.columns:
        fc_df = pd.DataFrame({
            "Time": fc_times,
            "Predicted n_bytes": [f"{v:,.0f}" for v in fc_values],
        })
    else:
        fc_df = pd.DataFrame({
            "Hour": [f"+{i + 1}h" for i in range(HORIZON)],
            "Predicted n_bytes": [f"{v:,.0f}" for v in fc_values],
        })

    st.dataframe(fc_df, use_container_width=True, hide_index=True)

    # download
    csv_data = fc_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download Forecast CSV", csv_data,
        "forecast_results.csv", "text/csv",
    )
