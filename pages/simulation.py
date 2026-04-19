import streamlit as st
import pandas as pd
import plotly.express as px

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'utils'))

from agent import SmartAgent, extract_profile
from network import Network
from simulator import run_multiple_simulations
from persona import build_prompt, query_llm, llm_to_profile

st.title("Network Simulation System")

uploaded_files = st.file_uploader(
    "Upload user CSVs",
    type="csv",
    accept_multiple_files=True
)

def show_stats(simulation_results):
    st.subheader("Simulation Results")
    col1, col2, col3 = st.columns(3)
    col1.metric("Avg Load", f"{simulation_results['load'].mean():.2f}")
    col2.metric("Avg Latency (ms)", f"{simulation_results['latency'].mean():.2f}")
    col3.metric("Avg Packet Loss (%)", f"{simulation_results['packet_loss'].mean() * 100:.2f}%")

def show_impact_stats(impact):
    st.subheader("What-If Impact")
    col1, col2, col3 = st.columns(3)

    if impact["congestion_time"] > 5:
        col1.metric("Congestion Time Intervals", f":red[{impact['congestion_time']}]")
    elif impact["congestion_time"] > 0:
        col1.metric("Congestion Time Intervals", f":orange[{impact['congestion_time']}]")
    else:
        col1.metric("Congestion Time Intervals", f":green[{impact['congestion_time']}]")

    if impact["latency_increase"] > 50:
        col2.metric("Avg Latency Increase (ms)", f":red[+ {impact['latency_increase']:.2f}]")
    elif impact["latency_increase"] > 0:
        col2.metric("Avg Latency Increase (ms)", f":orange[+{impact['latency_increase']:.2f}]")
    else:
        col2.metric("Avg Latency Increase (ms)", f":green[{impact['latency_increase']:.2f}]")

    if impact["max_load_increase"] > 0.5:
        col3.metric("Max Load Increase", f":red[+ {impact['max_load_increase']:.2f}]")
    elif impact["max_load_increase"] > 0:
        col3.metric("Max Load Increase", f":orange[+ {impact['max_load_increase']:.2f}]")
    else:
        col3.metric("Max Load Increase", f":green[{impact['max_load_increase']:.2f}]")

agents = []

if uploaded_files:
    for idx, file in enumerate(uploaded_files):
        df = pd.read_csv(file)
        profile = extract_profile(df)

        agent = SmartAgent(name=f"Agent_{idx+1}", profile=profile)
        agents.append(agent)

capacity = 1e8 * (st.slider("Network Capacity in Mb", 1, 10, 4))/8

network = Network(capacity)

simulation_number = st.slider("Number of Simulations to Run", 1, 100, 1)


if 'base_result' not in st.session_state:
    st.session_state.base_result = None

if 'base_logs' not in st.session_state:
    st.session_state.base_logs = None

if st.button("Run Current Network"):
    st.session_state.base_result, st.session_state.base_logs = run_multiple_simulations(agents, network, simulation_number)

if st.session_state.base_result is not None:
    result = st.session_state.base_result
    logs = st.session_state.base_logs
    st.subheader("Current Network")
    st.line_chart(result.set_index("time")["traffic"])
    st.subheader("State Change Logs")
    logs["event_code"] = logs["event"].astype("category").cat.codes

    fig = px.scatter(
        logs,
        x="timestamp",
        y="agent",
        color="event",
        title="Agent Behavior Timeline"
    )

    st.plotly_chart(fig, use_container_width=True)
    show_stats(result)

    st.divider()
    st.subheader("What-If: Add a New User")

    persona_input = st.text_input("Describe new user (e.g., streamer, gamer)")

    # Only regenerate the persona profile when the input text actually changes
    if persona_input:
        if st.session_state.get("persona_input_last") != persona_input:
            st.session_state.persona_input_last = persona_input
            st.session_state.persona_profile = llm_to_profile(query_llm(build_prompt(persona_input)))
            st.session_state.whatif_result = None  # clear stale result

        if "persona_profile" in st.session_state:
            st.info(f"Detected Profile: {st.session_state.persona_profile['type'].capitalize()}")

    # Always render the button at the top level so Streamlit doesn't lose it on re-render
    run_whatif = st.button(
        "Run What-If Scenario",
        disabled=(not persona_input or "persona_profile" not in st.session_state),
    )

    if run_whatif:
        persona_agent = SmartAgent(st.session_state.persona_profile, name="Persona")
        base = st.session_state.base_result
        new_agents = agents + [persona_agent]
        new_result = run_multiple_simulations(new_agents, network, simulation_number)[0]
        st.session_state.whatif_result = new_result

    if "whatif_result" in st.session_state and st.session_state.whatif_result is not None:
        base = st.session_state.base_result
        new = st.session_state.whatif_result

        st.subheader("Before vs After")
        df_compare = pd.DataFrame({
            "time": base["time"],
            "Before": base["traffic"].values,
            "After": new["traffic"].values,
        })
        st.line_chart(df_compare.set_index("time"))

        impact = {
            "max_load_increase": new["load"].max() - base["load"].max(),
            "latency_increase": new["latency"].mean() - base["latency"].mean(),
            "congestion_time": int((new["load"] > 1).sum()),
        }
        show_stats(new)
        show_impact_stats(impact)

        if new["load"].max() > 0.85:
            st.error("Warning: Adding this user violates QoS thresholds")
        else:
            st.success("This user can be added without violating QoS thresholds")