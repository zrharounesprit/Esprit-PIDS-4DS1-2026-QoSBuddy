from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from utils.sla_pipeline import engineer_sla_features  # noqa: E402
from utils.sla_preprocess import (  # noqa: E402
    df_has_resolvable_clock,
    ensure_subnet_key,
    merge_cesnet_times_1h,
)

st.title("SLA Detection")

BASE_URL = "http://127.0.0.1:8003"
META_URL = f"{BASE_URL}/sla_metadata"
PREDICT_URL = f"{BASE_URL}/predict_sla"


@st.cache_data(ttl=30)
def fetch_metadata():
    try:
        r = requests.get(META_URL, timeout=5)
        r.raise_for_status()
        return r.json(), None
    except requests.exceptions.ConnectionError:
        return None, "Cannot reach the SLA API on port 8003."
    except requests.exceptions.RequestException as e:
        return None, str(e)


meta, meta_err = fetch_metadata()

if meta_err:
    st.error("SLA API is not running. Start it before using this page.")
elif meta and not meta.get("ready"):
    st.warning("SLA API is running but the model failed to load.")
else:
    threshold = meta.get("optimal_threshold") if meta else None

    traffic_csv = st.file_uploader(
        "Hourly subnet traffic CSV",
        type=["csv"],
        key="sla_traffic_hourly",
    )
    times_csv = st.file_uploader(
        "Timestamps file (times_1_hour.csv)",
        type=["csv"],
        key="sla_times_1_hour",
    )

    st.divider()

    # ── helpers ──────────────────────────────────────────────────────────

    def highlight_violations(row):
        if row.get("Anomaly") is True:
            match row.get("Severity"):
                case "LOW":
                    return ["background-color: #FFA500"] * len(row)
                case "MEDIUM":
                    return ["background-color: #FF4500"] * len(row)
                case "HIGH":
                    return ["background-color: #FF0000"] * len(row)
        return [""] * len(row)

    def show_stats(sla_df: pd.DataFrame):
        total_rows = len(sla_df)
        scored = sla_df["Anomaly"].notna().sum()
        violation_count = int((sla_df["Anomaly"] == True).sum())  # noqa: E712
        violation_rate = (violation_count / scored) * 100 if scored else 0.0

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Rows", total_rows)
        col2.metric("SLA Violations", violation_count)
        col3.metric("Violation Rate (%)", f"{violation_rate:.2f}")

    def filter_rows(sla_df: pd.DataFrame) -> pd.DataFrame:
        show_only = st.toggle("Show only violations")
        if show_only:
            out = sla_df[sla_df["Anomaly"] == True].copy()  # noqa: E712
            severity_options = ["LOW", "MEDIUM", "HIGH"]
            selected = st.multiselect(
                "Filter by Severity",
                severity_options,
                default=severity_options,
            )
            return out[out["Severity"].isin(selected)]
        return sla_df

    def download_csv(sla_df: pd.DataFrame):
        csv = sla_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download Results as CSV",
            data=csv,
            file_name="sla_results.csv",
            mime="text/csv",
        )

    def download_report(sla_df: pd.DataFrame, selection):
        if (
            selection.selection.rows
            and sla_df.iloc[selection.selection.rows[0]].get("Anomaly") is True
        ):
            idx = selection.selection.rows[0]
            report = sla_df.iloc[idx].get("Report", "")
            st.download_button(
                label="Download Report",
                data=str(report),
                file_name="sla_report.txt",
                mime="text/plain",
            )
        else:
            st.button("Select a violation row to download report", disabled=True)

    # ── run analysis ─────────────────────────────────────────────────────

    has_traffic_here = traffic_csv is not None
    has_traffic_session = "df" in st.session_state
    has_source = has_traffic_here or has_traffic_session

    if not has_source:
        st.info("Upload a traffic CSV above, or load one from the Upload page first.")

    if st.button("Run Analysis", disabled=not has_source) and has_source:
        if traffic_csv is not None:
            base = pd.read_csv(traffic_csv)
        else:
            base = st.session_state["df"].copy()

        prep_error: str | None = None
        work = ensure_subnet_key(base, "0")

        if df_has_resolvable_clock(work):
            pass
        elif "id_time" not in work.columns:
            prep_error = "CSV has no timestamp column and no id_time. Cannot proceed."
        elif times_csv is None:
            prep_error = "Upload the timestamps file (times_1_hour.csv) to map id_time to real timestamps."
        else:
            try:
                times_df = pd.read_csv(times_csv)
                work = merge_cesnet_times_1h(work, times_df)
                work = ensure_subnet_key(work, "0")
            except Exception as e:
                prep_error = f"Failed to merge timestamps: {e}"

        if prep_error:
            st.error(prep_error)
        else:
            fc = list(meta.get("feature_columns") or [])
            if not fc:
                st.error("Model metadata is missing feature columns.")
            else:
                rows_payload = None
                work_ids = work.reset_index(drop=False).rename(columns={"index": "__row_id"})
                input_row_count = len(work_ids)
                try:
                    engineered = engineer_sla_features(work_ids, fc)
                    rows_payload = json.loads(
                        engineered.to_json(orient="records", date_format="iso")
                    )
                except Exception as e:
                    st.error(f"Feature engineering failed: {e}")

                if rows_payload is not None:
                    try:
                        response = requests.post(
                            PREDICT_URL,
                            json={"rows": rows_payload, "input_row_count": input_row_count},
                            timeout=120,
                        )
                    except requests.exceptions.ConnectionError:
                        st.error("Lost connection to the SLA API.")
                    else:
                        if response.status_code != 200:
                            st.error(f"API error {response.status_code}: {response.text}")
                        else:
                            data = response.json()
                            results = data.get("results") or []
                            built: list[dict] = []
                            for item in results:
                                rid = item.get("row_id", 0)
                                ts = None
                                if rid < len(work_ids):
                                    row_src = work_ids.iloc[int(rid)]
                                    for col in ("datetime", "timestamp", "time", "id_time"):
                                        val = row_src.get(col)
                                        if val is not None and not (
                                            isinstance(val, float) and pd.isna(val)
                                        ):
                                            ts = val
                                            break

                                if item.get("skipped", False):
                                    built.append({"Timestamp": ts, "Anomaly": None})
                                elif item.get("sla_violation"):
                                    built.append({
                                        "Timestamp": ts,
                                        "Anomaly": True,
                                        "Severity": item.get("severity"),
                                        "Score": item.get("probability"),
                                        "Recommendation": item.get("recommendation"),
                                        "Report": item.get("report"),
                                    })
                                else:
                                    built.append({
                                        "Timestamp": ts,
                                        "Anomaly": False,
                                        "Score": item.get("probability"),
                                    })

                            st.session_state["sla_results_df"] = pd.DataFrame(built)

    # ── display results ──────────────────────────────────────────────────

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
            download_report(filtered.reset_index(drop=True), selection)

        selected_index = st.selectbox("Select row for details", filtered.index)
        if selected_index is not None:
            st.write(filtered.drop(columns=["Report"], errors="ignore").loc[selected_index])
