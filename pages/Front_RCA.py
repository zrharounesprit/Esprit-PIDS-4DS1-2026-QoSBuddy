# ─────────────────────────────────────────────────────────────────────────────
# pages/Front_RCA.py — Root Cause Analysis Page
#
# This page reads the dataframe from st.session_state["df"] which was
# uploaded on the Upload page. It no longer has its own file uploader.
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
import requests


# ── Constants ─────────────────────────────────────────────────────────────────
API_URL = "http://127.0.0.1:8002"

SEVERITY_COLORS = {
    "extreme_scanner": "#e53935",
    "udp_suspicious" : "#f57c00",
    "congestion"     : "#f9a825",
    "normal"         : "#43a047",
}
SEVERITY_LABELS = {
    "extreme_scanner": "CRITICAL",
    "udp_suspicious" : "HIGH",
    "congestion"     : "MEDIUM",
    "normal"         : "LOW",
}


# ── Helper: send one row to FastAPI ──────────────────────────────────────────
def get_rca_report(input_data: dict):
    try:
        r = requests.post(f"{API_URL}/rca", json=input_data, timeout=10)
        if r.status_code == 200:
            return r.json(), None
        else:
            return None, f"API error {r.status_code}: {r.text}"
    except requests.exceptions.ConnectionError:
        return None, "Cannot connect to FastAPI. Make sure main_RCA.py is running."
    except Exception as e:
        return None, f"Unexpected error: {str(e)}"


# ── Helper: render the RCA report ────────────────────────────────────────────
def display_report(report: dict):
    cause    = report.get("cause_label", "unknown")
    title    = report.get("cause_title", cause)
    color    = SEVERITY_COLORS.get(cause, "#888")
    severity = SEVERITY_LABELS.get(cause, "UNKNOWN")

    st.markdown(f"""
    <div style="
        background:{color}18;
        border-left:5px solid {color};
        border-radius:6px;
        padding:16px 20px;
        margin-bottom:20px;
    ">
        <p style="margin:0;font-size:11px;color:{color};
                  font-weight:600;letter-spacing:2px;">
            ROOT CAUSE ANALYSIS REPORT
        </p>
        <h2 style="margin:6px 0 6px 0;color:{color};">{title}</h2>
        <span style="background:{color};color:white;padding:3px 12px;
                     border-radius:12px;font-size:12px;font-weight:600;">
            {severity}
        </span>
        <span style="margin-left:12px;font-size:13px;color:#888;">
            IP: {report.get("id_ip")} &nbsp;|&nbsp;
            {report.get("generated_at")}
        </span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("#### What This Means")
    st.info(report.get("what_it_means", "—"))

    st.markdown("#### Why We Think This")
    for i, obs in enumerate(report.get("why_we_think_this", []), 1):
        st.markdown(f"""
        <div style="background:#000000;border-radius:6px;
                    padding:10px 14px;margin-bottom:8px;
                    border-left:3px solid {color};">
            <span style="color:{color};font-weight:600;">{i}.</span> {obs}
        </div>
        """, unsafe_allow_html=True)

    # st.markdown("#### Chronic or New?")
    # chronic = report.get("chronic_or_new", "—")
    # if "NEW" in chronic.upper():
    #     st.warning(chronic)
    # elif "CHRONIC" in chronic.upper():
    #     st.error(chronic)
    # else:
    #     st.info(chronic)

    # st.markdown("#### Network Context")
    # st.success(report.get("peer_context", "—"))

    with st.expander("View raw JSON"):
        st.json(report)


# ═════════════════════════════════════════════════════════════════════════════
# PAGE LAYOUT
# ═════════════════════════════════════════════════════════════════════════════

st.title(" Root Cause Analysis")
st.caption("Diagnose the root cause of a network issue from your uploaded dataset.")

st.divider()

# ── Check if a dataset has been uploaded ─────────────────────────────────────
# Instead of uploading here, we read from session_state.
# If the user hasn't uploaded yet, we send them to the Upload page.

if "df" not in st.session_state:
    st.warning(
        "No dataset loaded. "
        "Please go to the **Upload** page first and upload a CSV file."
    )
    # st.stop() prevents the rest of the page from rendering
    st.stop()

# pull the dataframe out of session_state
df = st.session_state["df"]

st.success(
    f"Using **{st.session_state['file_name']}** "
    f"— {len(df)} rows loaded."
)

st.divider()

# ── Row selector ──────────────────────────────────────────────────────────────
# the user picks which row to analyse from a dropdown
row_index = st.selectbox(
    "Select a row to analyse",
    options=list(range(len(df))),
    format_func=lambda i: f"Row {i}",
)

# pull the selected row as a dictionary
selected_row = df.iloc[row_index].to_dict()

# show what is being sent so the user can verify
with st.expander("View selected row values"):
    st.json(selected_row)
st.divider()

# ── Analyse button ────────────────────────────────────────────────────────────
if st.button("Analyse Root Cause", use_container_width=True, type="primary"):

    # map CSV column names to what the FastAPI expects
    input_data = {
        "id_ip"                : int(selected_row.get("id_ip", 0)),
        "n_flows"              : float(selected_row.get("n_flows", 0)),
        "n_packets"            : float(selected_row.get("n_packets", 0)),
        "n_bytes"              : float(selected_row.get("n_bytes", 0)),
        "sum_n_dest_ip"        : float(selected_row.get("sum_n_dest_ip", 0)),
        "sum_n_dest_ports"     : float(selected_row.get("sum_n_dest_ports", 0)),
        "std_n_dest_ip"        : float(selected_row.get("std_n_dest_ip", 0)),
        "tcp_udp_ratio_packets": float(selected_row.get("tcp_udp_ratio_packets", 1)),
        "tcp_udp_ratio_bytes"  : float(selected_row.get("tcp_udp_ratio_bytes", 1)),
        "dir_ratio_packets"    : float(selected_row.get("dir_ratio_packets", 0.5)),
        "dir_ratio_bytes"      : float(selected_row.get("dir_ratio_bytes", 0.5)),
        "avg_duration"         : float(selected_row.get("avg_duration", 0)),
        "avg_ttl"              : float(selected_row.get("avg_ttl", 0)),
    }

    with st.spinner("Analysing..."):
        report, error = get_rca_report(input_data)

    if error:
        st.error(f"Error: {error}")
    else:
        st.subheader("Root Cause Analysis Report")
        display_report(report)
