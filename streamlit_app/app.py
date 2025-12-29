"""OMRON Garmin Bridge - Streamlit Web UI.

Main application entry point using st.navigation.

Usage:
    pdm run streamlit run streamlit_app/app.py
"""

from __future__ import annotations

import streamlit as st

# Define pages with st.Page
dashboard = st.Page(
    "pages/0_Dashboard.py",
    title="Dashboard",
    icon=":material/dashboard:",
    default=True,
)
history = st.Page(
    "pages/1_History.py",
    title="History",
    icon=":material/history:",
)
sync = st.Page(
    "pages/2_Sync.py",
    title="Sync",
    icon=":material/sync:",
)
settings = st.Page(
    "pages/3_Settings.py",
    title="Settings",
    icon=":material/settings:",
)

# Navigation
pg = st.navigation([dashboard, history, sync, settings])

# Page config
st.set_page_config(
    page_title="OMRON Garmin Bridge",
    page_icon="❤",
    layout="wide",
)

# Run selected page
pg.run()
