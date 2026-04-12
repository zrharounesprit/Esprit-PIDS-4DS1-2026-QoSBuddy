import streamlit as st
import requests
import pandas as pd
import numpy as np

# --- PAGE CONFIG ---
st.set_page_config(page_title="QoSBuddy | Persona Analysis", layout="wide")
st.title("👤 Universal Persona Classification")
st.markdown("---")

# --- 1. DATA CHECK ---
if "df" not in st.session_state:
    st.warning("⚠️ Please upload a network traffic CSV on the main page first.")
    st.stop()

df = st.session_state["df"]
file_name = st.session_state.get("file_name", "Uploaded File")

st.info(f"📁 **Analyzing Behavioral Patterns in:** {file_name}")

# --- 2. CLASSIFICATION ACTION ---
if st.button("Run Advanced AI Analysis", type="primary", use_container_width=True):
    with st.spinner("📤 Transmitting telemetry to QoSBuddy Inference Engine..."):
        try:
            # Columns required by your 7-feature XGBoost model
            cols_to_send = ['n_bytes', 'tcp_udp_ratio_packets', 'avg_duration', 'sum_n_dest_ip']
            
            # Column Validation
            missing_cols = [c for c in cols_to_send if c not in df.columns]
            if missing_cols:
                st.error(f"❌ Missing required columns in CSV: {missing_cols}")
                st.stop()

            # Prepare Payload
            payload = df[cols_to_send].to_dict(orient="records")
            
            # Send POST request to FastAPI (main.py)
            response = requests.post(
                "http://127.0.0.1:8000/classify_content",
                json=payload
            )
            
            if response.status_code == 200:
                res = response.json()
                persona = res['classification']
                profile = res['profile']
                
                # --- 3. RESULTS DISPLAY (METRICS) ---
                st.success(f"### Predicted Persona: **{persona}**")
                
                m1, m2, m3 = st.columns(3)
                with m1:
                    st.metric("Avg Traffic Volume", f"{profile['avg_traffic_bytes']} B")
                    st.metric("Avg Flow Duration", f"{profile['avg_duration']}s")
                with m2:
                    st.metric("Burstiness Index", profile['burstiness_score'])
                    st.metric("Unique Destinations", profile['destinations_contacted'])
                with m3:
                    st.metric("Evening Intensity", profile['evening_intensity'])
                    st.metric("TCP/UDP Ratio", profile['protocol_ratio'])
                
                # --- 4. VISUALIZATION (FIXED X-AXIS) ---
                st.divider()
                st.subheader("24-Hour Traffic Pattern Analysis")
                
                chart_df = df.copy()
                rows = len(chart_df)
                
                # Generate a 24-hour time range based on the row count
                start_time = pd.Timestamp("2026-01-01 00:00:00")
                time_indices = [
                    (start_time + pd.Timedelta(minutes=(i * (1440 / rows))))
                    for i in range(rows)
                ]
                
                # FIX: We use 'Time_HHmm' to avoid the Altair Colon Encoding Error
                chart_df['Time_HHmm'] = [t.strftime('%H:%M') for t in time_indices]
                chart_df = chart_df.set_index('Time_HHmm')
                
                # Plotting only the volume
                st.line_chart(chart_df['n_bytes'], use_container_width=True)
                
                st.caption(f"📊 X-Axis mapped to a normalized 24-hour cycle across {rows} observations.")

            else:
                st.error(f"❌ Backend Error: {response.text}")
                
        except Exception as e:
            st.error(f"📡 Connection Failed: Ensure 'main.py' is running on port 8000. ({e})")

# --- SIDEBAR ---
st.sidebar.markdown("---")
st.sidebar.subheader("System Info")
st.sidebar.info("Model: XGBoost Classifier\nFeatures: 7-Dimensional")
st.sidebar.caption("QoSBuddy Framework v3.0")
st.sidebar.write(f"Developer: Mohamed Aymen Hamzaoui")