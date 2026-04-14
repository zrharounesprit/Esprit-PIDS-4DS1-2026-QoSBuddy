# ─────────────────────────────────────────────────────────────────────────────
# app.py — QoSBuddy Dashboard Entry Point
#
# Run this to start the dashboard:
#   streamlit run app.py
#
# The CSV is uploaded once on the Upload page and stored in session_state.
# All model pages read from that shared state automatically.
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
import runpy


# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="QoSBuddy Dashboard",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# hides Streamlit's automatic multipage nav and default header
st.markdown("""
    <style>
        [data-testid="stSidebarNav"] {display: none;}
        [data-testid="stSidebarNavItems"] {display: none;}
        [data-testid="collapsedControl"] {display: none;}
        #MainMenu {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)


# ── Page registry ─────────────────────────────────────────────────────────────
# Add one entry per page.
# "label" → sidebar button text
# "file"  → path to the .py file inside dashboard/ (no .py extension)
# "desc"  → description shown on the home page card
# "color" → card accent colour on home page

PAGES = [
    {
        "label": "Home",
        "file" : None,
        "desc" : None,
        "color": None,
    },
    {
        "label": "Network Simulation",
        "file" : "pages/simulation",
        "desc" : (
            "Simulate how different user profiles impact network performance. "
            "Upload your dataset to create custom agents, or describe a new user "
            "for our LLM-powered persona generator to create a new agent on the fly."
        ),
        "color": "#00FFD5",
    },
    {
    "label": "MCP Demo",
    "file" : "pages/mcp_demo",
    "desc" : "Live MCP endpoint demonstration of the network simulation.",
    "color": "#0097a7",
    },
    {
        "label": "Upload Dataset",
        "file" : "pages/upload",
        "desc" : (
            "Upload your CSV file here once. All model pages will "
            "automatically use this data without needing to upload again."
        ),
        "color": "#1D9E75",
    },
    {
        "label": "Anomaly Detection",
        "file" : "pages/anomaly_interface",
        "desc" : (
            "Detects anomalies in network traffic, identifies key contributing features"
            ", and provides actionable recommendations to address potential issues."
        ),
        "color": "#F04444",
    },
    {
        "label": "Root Cause Analysis",
        "file" : "pages/Front_RCA",
        "desc" : (
            "Diagnose the root cause of a network issue. Classifies IPs "
            "into behavioural groups and generates a human-readable report."
        ),
        "color": "#534AB7",
    },
    # ── Teammates add their entries below ─────────────────────────────────────
    # {
    #     "label": "⚠️  Anomaly Detection",
    #     "file" : "pages/anomaly_model",
    #     "desc" : "Detects anomalies in network traffic.",
    #     "color": "#e53935",
    # },
    {
        "label": "Traffic Forecasting",
        "file" : "pages/forecasting",
        "desc" : (
            "Predict future network traffic volumes using an LSTM time-series "
            "model. Uses a 24-hour lookback window to forecast the next 6 hours."
        ),
        "color": "#2196F3",
    },
]


# ── Session state — remember active page ─────────────────────────────────────
if "current_page" not in st.session_state:
    st.session_state.current_page = "Home"


# ── Sidebar navbar ────────────────────────────────────────────────────────────
st.sidebar.title("QoSBuddy")
st.sidebar.caption("Intelligent Network Assurance")

# show a small indicator if a dataset is already loaded
if "df" in st.session_state:
    st.sidebar.success(f"{st.session_state['file_name']} loaded")
else:
    st.sidebar.warning("No dataset loaded")

st.sidebar.divider()

# one button per page — clicking stores the label and reruns
for page in PAGES:
    is_active = st.session_state.current_page == page["label"]
    if st.sidebar.button(
        page["label"],
        use_container_width=True,
        type="primary" if is_active else "secondary",
        key=page["label"],
    ):
        st.session_state.current_page = page["label"]
        st.rerun()

st.sidebar.divider()
st.sidebar.caption("Team VizBiz · Esprit 2025")


# ── Page router ───────────────────────────────────────────────────────────────
current = st.session_state.current_page

if current == "Home":

    st.title("QoSBuddy")
    st.subheader("Intelligent Network Assurance & Autonomous Optimization")
    st.divider()

    # show upload status prominently on home so the user knows what to do first
    if "df" in st.session_state:
        st.success(
            f"Dataset ready: **{st.session_state['file_name']}** "
            f"({len(st.session_state['df'])} rows). "
            "Navigate to any model page to analyse it."
        )
    else:
        st.info(
            "Start by going to **Upload Dataset** in the sidebar "
            "to load your CSV file. All model pages will use it automatically."
        )

    st.markdown(" ")

    # generate one card per page (skip Home itself)
    content_pages = [p for p in PAGES if p["file"] is not None]

    for i in range(0, len(content_pages), 2):
        pair = content_pages[i : i + 2]
        cols = st.columns(len(pair))

        for col, page in zip(cols, pair):
            with col:
                color = page.get("color", "#888")
                st.markdown(f"""
                <div style="
                    background:{color}12;
                    border-left:4px solid {color};
                    border-radius:8px;
                    padding:18px 20px;
                    min-height:110px;
                    margin-bottom:8px;
                ">
                    <h4 style="margin:0 0 8px 0;color:{color};">
                        {page["label"]}
                    </h4>
                    <p style="margin:0;color:#555;font-size:14px;
                              line-height:1.5;">
                        {page.get("desc", "")}
                    </p>
                </div>
                """, unsafe_allow_html=True)

                if st.button(f"Open", key=f"open_{page['label']}"):
                    st.session_state.current_page = page["label"]
                    st.rerun()

        st.markdown(" ")

else:
    # load and run the selected page file
    target = next((p for p in PAGES if p["label"] == current), None)

    if target and target["file"]:
        runpy.run_path(target["file"] + ".py", run_name="__main__")
    else:
        st.error(f"Page '{current}' not found.")
