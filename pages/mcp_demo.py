import streamlit as st
import requests
import json
import pandas as pd
import plotly.express as px

API_BASE = "http://127.0.0.1:8005"

if "baseline_json" not in st.session_state:
    st.session_state.baseline_json = None
if "mcp_csv_files" not in st.session_state:
    st.session_state.mcp_csv_files = []
if "mcp_csv_names" not in st.session_state:
    st.session_state.mcp_csv_names = []


st.title("MCP Bridge Demo")
st.caption("MCP extracts parameters from prompts to call the API endpoints and returns visualized analysis")

st.divider()


st.subheader("Upload CSV Files")

uploaded_csvs = st.file_uploader(
    "Upload CSV files (each represents a network user)",
    type=["csv"],
    accept_multiple_files=True
)

if uploaded_csvs:
    csv_bytes_list = []
    csv_names_list = []
    for f in uploaded_csvs:
        f.seek(0)
        csv_bytes_list.append(f.read())
        csv_names_list.append(f.name)
    st.session_state.mcp_csv_files = csv_bytes_list
    st.session_state.mcp_csv_names = csv_names_list
    st.success(f"{len(uploaded_csvs)} file(s) uploaded")

st.divider()



st.subheader("MCP")

st.caption("Example: *'Run simulation with 4Mb/s capacity and 8 simulations'*")

baseline_prompt = st.text_area(
    "Describe the baseline simulation",
    placeholder="e.g., Run simulation with 4Mb/s capacity and 8 simulations",
    height=68
)

if st.button("Run Agent", use_container_width=True):
    
    if not st.session_state.mcp_csv_files:
        st.error("Please upload CSV files first")
    elif not baseline_prompt:
        st.error("Please task the agent")
    else:
        prompt_lower = baseline_prompt.lower()
        
        import re
        capacity = 4  
        cap_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:mb|capacity)", prompt_lower)
        if cap_match:
            capacity = float(cap_match.group(1))
        
        simulations = 1 
        sim_match = re.search(r"(\d+)\s*(?:simulations?|runs?)", prompt_lower)
        if sim_match:
            simulations = int(sim_match.group(1))
        
        with st.spinner(f"MCP extracting: capacity={capacity}MB, simulations={simulations}"):
            files = []
            for csv_bytes, name in zip(st.session_state.mcp_csv_files, st.session_state.mcp_csv_names):
                files.append(("files", (name, csv_bytes, "text/csv")))
            
            print(f"DEBUG: capacity={capacity}, simulations={simulations}, type(capacity)={type(capacity)}")
            print (f"DEBUG: files length={len(files)}")
            try:
                response = requests.post(
                    f"{API_BASE}/api/simulate_agents",
                    files=files,
                    data={"capacity": capacity, "simulations": simulations},
                    timeout=120
                )
                response.raise_for_status()
                st.session_state.baseline_json = response.json()
                st.success("MCP baseline simulation complete!")
            except Exception as e:
                st.error(f"Error: {e}")

if st.session_state.baseline_json:
    traffic_df = pd.DataFrame(st.session_state.baseline_json["traffic"])
    traffic_df["time"] = pd.to_datetime(traffic_df["time"])
    logs_df = pd.DataFrame(st.session_state.baseline_json["logs"])

    st.subheader("Network Traffic")
    st.line_chart(traffic_df.set_index("time")["traffic"])

    st.subheader("Agent Behavior Timeline")
    fig = px.scatter(
        logs_df,
        x="timestamp",
        y="agent",
        color="event",
        title="Agent Behavior Timeline"
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Simulation Results")
    col1, col2, col3 = st.columns(3)
    col1.metric("Avg Load", f"{traffic_df['load'].mean():.2f}")
    col2.metric("Avg Latency (ms)", f"{traffic_df['latency'].mean():.2f}")
    col3.metric("Avg Packet Loss (%)", f"{traffic_df['packet_loss'].mean() * 100:.2f}%")

st.divider()

st.subheader("Persona Simulation")
st.caption("Example: *'Add a gamer who plays FPS games at night'*")

persona_prompt = st.text_area(
    "Describe the new user",
    placeholder="e.g., a gamer who plays FPS games at night, a streamer watching 4K video",
    height=68,
    disabled=st.session_state.baseline_json is None
)

if st.button("Run What-If MCP Simulation", use_container_width=True,
             disabled=st.session_state.baseline_json is None):

    if not persona_prompt:
        st.error("Please describe the new user")
    else:
        capacity = st.session_state.baseline_json.get("capacity", 4)
        simulations = 1
        profiles = st.session_state.baseline_json.get("profiles", [])

        with st.spinner(f"MCP extracting persona: '{persona_prompt}'"):
            try:
                response = requests.post(
                    f"{API_BASE}/api/simulate_persona",
                    json={
                        "profiles": profiles,
                        "prompt": persona_prompt,
                        "capacity": capacity,
                        "simulations": simulations
                    },
                    timeout=120
                )
                response.raise_for_status()
                st.session_state.persona_json = response.json()
                st.success("Persona simulation complete!")

                before_df = pd.DataFrame(st.session_state.persona_json["before"])
                before_df["time"] = pd.to_datetime(before_df["time"])
                after_df = pd.DataFrame(st.session_state.persona_json["after"])
                after_df["time"] = pd.to_datetime(after_df["time"])
                logs_df = pd.DataFrame(st.session_state.persona_json["logs"])
                impact = st.session_state.persona_json.get("impact", {})
                decision = st.session_state.persona_json.get("decision", "UNKNOWN")

                st.info(f"Detected Profile: {st.session_state.persona_json.get('Persona', 'Unknown')}")

                st.subheader("Before vs After Traffic")
                df_compare = pd.DataFrame({
                    "Before": before_df.set_index("time")["load"],
                    "After": after_df.set_index("time")["load"]
                }, index=before_df["time"])
                st.line_chart(df_compare)

                st.subheader("Agent Behavior Timeline (with Persona)")
                fig = px.scatter(
                    logs_df,
                    x="timestamp",
                    y="agent",
                    color="event",
                    title="Agent Behavior Timeline"
                )
                st.plotly_chart(fig, use_container_width=True)

                # Stats
                st.subheader("Simulation Results")
                col1, col2, col3 = st.columns(3)
                col1.metric("Avg Load", f"{after_df['load'].mean():.2f}")
                col2.metric("Avg Latency (ms)", f"{after_df['latency'].mean():.2f}")
                col3.metric("Avg Packet Loss (%)", f"{after_df['packet_loss'].mean() * 100:.2f}%")

                # Impact stats
                st.subheader("What-If Impact")
                col1, col2, col3 = st.columns(3)

                congestion = impact.get("congestion_time", 0)
                if congestion > 5:
                    col1.metric("Congestion Time Intervals", f":red[{congestion}]")
                elif congestion > 0:
                    col1.metric("Congestion Time Intervals", f":orange[{congestion}]")
                else:
                    col1.metric("Congestion Time Intervals", f":green[{congestion}]")

                latency_inc = impact.get("latency_increase", 0)
                if latency_inc > 50:
                    col2.metric("Avg Latency Increase (ms)", f":red[+ {latency_inc:.2f}]")
                elif latency_inc > 0:
                    col2.metric("Avg Latency Increase (ms)", f":orange[+{latency_inc:.2f}]")
                else:
                    col2.metric("Avg Latency Increase (ms)", f":green[{latency_inc:.2f}]")

                load_inc = impact.get("max_load_increase", 0)
                if load_inc > 0.5:
                    col3.metric("Max Load Increase", f":red[+ {load_inc:.2f}]")
                elif load_inc > 0:
                    col3.metric("Max Load Increase", f":orange[+ {load_inc:.2f}]")
                else:
                    col3.metric("Max Load Increase", f":green[{load_inc:.2f}]")

                if decision == "ACCEPT":
                    st.success("This user can be added without violating QoS thresholds")
                else:
                    st.error("Warning: Adding this user violates QoS thresholds")

            except Exception as e:
                st.error(f"Error: {e}")

st.divider()

if st.button("Reset All"):
    st.session_state.baseline_json = None
    st.session_state.mcp_csv_files = []
    st.session_state.mcp_csv_names = []
    st.rerun()