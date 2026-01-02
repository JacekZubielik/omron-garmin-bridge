"""OMRON Garmin Bridge - Streamlit Web UI.

Main application entry point using st.navigation.

Usage:
    pdm run streamlit run streamlit_app/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.main import load_config, setup_logging  # noqa: E402

# Setup logging from config (once per session)
if "logging_configured" not in st.session_state:
    config = load_config(str(project_root / "config" / "config.yaml"))
    setup_logging(config)
    st.session_state.logging_configured = True

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
