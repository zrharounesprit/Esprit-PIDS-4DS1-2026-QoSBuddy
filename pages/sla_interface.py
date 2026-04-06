# ─────────────────────────────────────────────────────────────────────────────
# pages/sla_interface.py — SLA risk / violation view
#
# Reads st.session_state["df"] from Upload. Requires sla_api running on :8003.
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
import pandas as pd
import requests

st.title("SLA Detection")

features = [
    "n_bytes",
    "n_packets",
    "n_flows",
    "tcp_udp_ratio_packets",
    "dir_ratio_packets",
]

API_URL = "http://127.0.0.1:8003/predict_sla"


def highlight_violations(row):
    if row["SLA violation"]:
        sev = row.get("Severity")
        if sev == "LOW":
            return ["background-color: #FFA500"] * len(row)
        if sev == "MEDIUM":
            return ["background-color: #FF4500"] * len(row)
        if sev == "HIGH":
            return ["background-color: #FF0000"] * len(row)
    return [""] * len(row)


def show_stats(sla_df: pd.DataFrame):
    total_rows = len(sla_df)
    violation_count = sla_df["SLA violation"].sum()
    violation_rate = (violation_count / total_rows) * 100 if total_rows > 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Rows", total_rows)
    col2.metric("SLA signals", int(violation_count))
    col3.metric("Signal rate (%)", f"{violation_rate:.2f}")


def filter_rows(sla_df: pd.DataFrame) -> pd.DataFrame:
    show_only = st.toggle("Show only SLA signals")
    out = sla_df.copy()
    if show_only:
        out = out[out["SLA violation"] == True]  # noqa: E712
        severity_options = ["LOW", "MEDIUM", "HIGH"]
        selected = st.multiselect(
            "Filter by severity",
            severity_options,
            default=severity_options,
        )
        return out[out["Severity"].isin(selected)]
    return sla_df


def download_csv(sla_df: pd.DataFrame):
    csv = sla_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download results as CSV",
        data=csv,
        file_name="sla_results.csv",
        mime="text/csv",
    )


def download_report(sla_df: pd.DataFrame, selection):
    if (
        selection.selection.rows
        and sla_df.iloc[selection.selection.rows[0]]["SLA violation"] == True  # noqa: E712
    ):
        idx = selection.selection.rows[0]
        report = sla_df.iloc[idx]["Report"]
        st.download_button(
            label="Download report (text)",
            data=report,
            file_name="sla_report.txt",
            mime="text/plain",
        )
    else:
        st.button("Select a flagged row to download report", disabled=True)


results: list[dict] = []

if "df" in st.session_state and st.button("Run SLA analysis"):
    for _, row in st.session_state["df"].iterrows():
        payload = {f: row[f] for f in features}
        try:
            response = requests.post(API_URL, json=payload, timeout=30)
        except requests.exceptions.ConnectionError:
            st.error(
                "Cannot connect to the SLA API. Start it with:\n\n"
                "`uvicorn utils.sla_api:app --host 127.0.0.1 --port 8003`"
            )
            break

        if response.status_code != 200:
            st.error(f"SLA API error {response.status_code}: {response.text}")
            break

        data = response.json()
        if data.get("sla_violation"):
            results.append(
                {
                    "Timestamp": row.get("timestamp", None),
                    "SLA violation": bool(data.get("sla_violation")),
                    "Severity": data.get("severity"),
                    "Recommendation": data.get("recommendation"),
                    "Score": float(data.get("score", 0)),
                    "Report": data.get("report"),
                }
            )
        else:
            results.append(
                {
                    "Timestamp": row.get("timestamp", None),
                    "SLA violation": data.get("sla_violation"),
                }
            )

    if results:
        st.session_state["sla_results_df"] = pd.DataFrame(results)

if "df" not in st.session_state:
    st.info("Upload a dataset from **Upload Dataset**, then run analysis here.")

if "sla_results_df" in st.session_state:
    sla_results_df = st.session_state["sla_results_df"]

    show_stats(sla_results_df)
    filtered = filter_rows(sla_results_df)

    display_df = filtered.drop(columns=["Report"], errors="ignore")
    selection = st.dataframe(
        display_df.style.apply(highlight_violations, axis=1),
        on_select="rerun",
        selection_mode="single-row",
    )

    d_csv, _, _, d_pdf = st.columns(4)
    with d_csv:
        download_csv(filtered)
    with d_pdf:
        download_report(filtered, selection)

    selected_index = st.selectbox("Select row for details", sla_results_df.index)
    if selected_index is not None:
        st.write(sla_results_df.drop(columns=["Report"], errors="ignore").loc[selected_index])
