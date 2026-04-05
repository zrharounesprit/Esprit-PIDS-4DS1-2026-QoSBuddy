import streamlit as st
import pandas as pd
import requests

st.title("Anomaly Detection")


features = [
    "n_bytes",
    "n_packets",
    "n_flows",
    "tcp_udp_ratio_packets",
    "dir_ratio_packets"
]

API_URL = "http://127.0.0.1:8000/predict_anomaly"

def highlight_anomalies(row):
    if row["Anomaly"]:
        match row["Severity"]:
            case "LOW":
                return ["background-color: #FFA500"] * len(row)
            case "MEDIUM":
                return ["background-color: #FF4500"] * len(row)
            case "HIGH":
                return ["background-color: #FF0000"] * len(row)
    return [""] * len(row)

def show_stats(anomaly_results_df):
    total_rows = len(anomaly_results_df)
    anomaly_count = anomaly_results_df["Anomaly"].sum()
    anomaly_rate = (anomaly_count / total_rows) * 100 if total_rows > 0 else 0

    col1, col2, col3 = st.columns(3)

    col1.metric("Total Rows", total_rows)
    col2.metric("Anomalies", int(anomaly_count))
    col3.metric("Anomaly Rate (%)", f"{anomaly_rate:.2f}")

def filter_anomalies(anomaly_results_df):
    show_only_anomalies = st.toggle("Show only anomalies")
    anomaly_filtered_df = anomaly_results_df.copy()

    if show_only_anomalies:
        anomaly_filtered_df = anomaly_filtered_df[anomaly_filtered_df["Anomaly"] == True]
        severity_options = ["LOW", "MEDIUM", "HIGH"]

        selected_severity = st.multiselect(
            "Filter by Severity",
            severity_options,
            default=severity_options
        )
        return anomaly_filtered_df[anomaly_filtered_df["Severity"].isin(selected_severity)]
    return anomaly_results_df

def download_csv(anomaly_results_df):
    csv = anomaly_results_df.to_csv(index=False).encode("utf-8")

    st.download_button(
        label="Download Results as CSV",
        data=csv,
        file_name="anomaly_results.csv",
        mime="text/csv"
    )
def download_pdf(anomaly_results_df, selection):
    if selection.selection.rows and anomaly_results_df.iloc[selection.selection.rows[0]]["Anomaly"] == True:
        idx = selection.selection.rows[0]
        report = anomaly_results_df.iloc[idx]["Report"]
        st.download_button(
            label="Download PDF Report",
            data=report,
            file_name="anomaly_report.txt",
            mime="text/plain"
        )
    else:
        st.button("Select an anomalous row to download report", disabled=True)
results = []

if "df" in st.session_state and st.button("Run Analysis"):
    
    for _, row in st.session_state['df'].iterrows():
        payload = {f: row[f] for f in features}
        
        response = requests.post(API_URL, json=payload)
        
        if response.status_code == 200:
            result = response.json()
            print(result)
            if(result.get("anomaly")==True):
                results.append({
                    "Timestamp": row.get("timestamp", None),
                    "Anomaly": bool(result.get("anomaly")),
                    "Severity": result.get("severity"),
                    "Recommendation": result.get("recommendation"),
                    "Score": float(result.get("score")),
                    "Report": result.get("report")
                })
            else:
                results.append({
                    "Timestamp": row.get("timestamp", None),
                    "Anomaly":result.get("anomaly")
                    })
            st.session_state["anomaly_results_df"] = pd.DataFrame(results)
if "df" not in st.session_state:
    st.info("Upload a dataset and click 'Run Analysis' to see results here.")

if "anomaly_results_df" in st.session_state:
    anomaly_results_df = st.session_state["anomaly_results_df"]


    show_stats(anomaly_results_df)

    anomaly_filtered_df = filter_anomalies(anomaly_results_df)

    selection =st.dataframe(anomaly_filtered_df.drop(columns=["Report"]).style.apply(highlight_anomalies, axis=1), on_select="rerun", selection_mode="single-row")

    d_csv, _, _, d_pdf = st.columns(4)
    with d_csv:
        download_csv(anomaly_filtered_df)
    with d_pdf:
        download_pdf(anomaly_filtered_df, selection)

    selected_index = st.selectbox("Select row for details", anomaly_results_df.index)
    if selected_index is not None:
        st.write(anomaly_results_df.drop(columns=["Report"]).loc[selected_index])




