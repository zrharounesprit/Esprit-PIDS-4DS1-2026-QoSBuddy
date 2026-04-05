# ─────────────────────────────────────────────────────────────────────────────
# pages/upload.py — Shared CSV Upload Page
#
# This page handles the CSV upload for the entire dashboard.
# Once uploaded here, the dataframe is stored in st.session_state["df"]
# so every other page can read it without uploading again.
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
import pandas as pd


st.title("Upload Dataset")
st.caption(
    "Upload your CSV file once here. All model pages will automatically "
    "use this data — no need to upload again when switching pages."
)

st.divider()

# ── File uploader ─────────────────────────────────────────────────────────────
uploaded_file = st.file_uploader(
    "Upload a CSV file from your ip_addresses_sample hourly folder",
    type=["csv"],
)

if uploaded_file is not None:
    # read the CSV into a pandas dataframe
    df = pd.read_csv(uploaded_file)

    # store the dataframe in session_state so all other pages can access it
    # session_state works like a shared dictionary that survives page switches
    st.session_state["df"]        = df
    st.session_state["file_name"] = uploaded_file.name

    st.success(f"✅ Loaded **{uploaded_file.name}** — {len(df)} rows, {len(df.columns)} columns.")

    # show a preview so the user can confirm the right file was uploaded
    st.markdown("**Preview (first 5 rows):**")
    st.dataframe(df.head(), use_container_width=True)

    st.info(
        "You can now navigate to any model page from the sidebar. "
        "They will all use this dataset automatically."
    )

# ── Show current status if something is already loaded ───────────────────────
# This handles the case where the user comes back to this page after uploading
elif "df" in st.session_state:
    st.success(
        f"**{st.session_state['file_name']}** is already loaded "
        f"({len(st.session_state['df'])} rows). "
        "You can upload a different file to replace it."
    )
    st.dataframe(st.session_state["df"].head(), use_container_width=True)

else:
    # nothing uploaded yet — show a clear message
    st.warning("No file uploaded yet. Upload a CSV file above to get started.")
