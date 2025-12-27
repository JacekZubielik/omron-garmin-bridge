"""History page - Detailed reading history with filtering."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.duplicate_filter import DuplicateFilter  # noqa: E402
from streamlit_app.components.icons import ICONS, load_fontawesome  # noqa: E402

st.set_page_config(page_title="History", page_icon="📈", layout="wide")


def get_db() -> DuplicateFilter:
    """Get or create database instance."""
    if "db" not in st.session_state:
        db_path = project_root / "data" / "omron.db"
        st.session_state.db = DuplicateFilter(str(db_path))
    db: DuplicateFilter = st.session_state.db
    return db


def main() -> None:
    """History page."""
    load_fontawesome()

    with st.sidebar:
        st.markdown("---")
        st.caption("OMRON Garmin Bridge v0.1.0")

    st.markdown(f"# {ICONS['table']} Reading History", unsafe_allow_html=True)
    st.markdown("Browse and filter blood pressure readings")

    db = get_db()

    # Filters
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        days = st.selectbox(
            "Time Range",
            options=[7, 14, 30, 90, 365, 0],
            format_func=lambda x: f"Last {x} days" if x > 0 else "All time",
            index=2,
        )

    with col2:
        user_slot = st.selectbox(
            "User Slot",
            options=[None, 1, 2],
            format_func=lambda x: "All users" if x is None else f"User {x}",
        )

    with col3:
        limit = st.number_input("Max records", min_value=10, max_value=1000, value=100)

    # Get data
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days) if days > 0 else None

    history = db.get_history(
        limit=limit,
        user_slot=user_slot,
        start_date=start_date,
        end_date=end_date,
    )

    if not history:
        st.warning("No readings found with selected filters.")
        return

    st.markdown("---")
    st.subheader(f"Found {len(history)} readings")
    show_flags_only = st.checkbox("Show only readings with flags")

    if show_flags_only:
        history = [r for r in history if r.get("irregular_heartbeat") or r.get("body_movement")]
        if not history:
            st.warning("No readings with flags found.")
            return

    # Convert to DataFrame for display
    df = pd.DataFrame(history)

    # Format columns
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["Date"] = df["timestamp"].dt.strftime("%Y-%m-%d")
    df["Time"] = df["timestamp"].dt.strftime("%H:%M")
    # Format category
    df["Category"] = df["category"].apply(lambda x: x.replace("_", " ").title() if x else "Unknown")

    # Build HTML table with Font Awesome icons
    icon_check = '<i class="fa-solid fa-check" style="color: #28a745;"></i>'
    icon_xmark = '<i class="fa-solid fa-xmark" style="color: #dc3545;"></i>'
    icon_warning = '<i class="fa-solid fa-triangle-exclamation" style="color: #ffc107;"></i>'
    icon_running = '<i class="fa-solid fa-person-running" style="color: #17a2b8;"></i>'

    table_html = """
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
    .history-table { width: 100%; border-collapse: collapse; font-size: 14px; }
    .history-table th { background: #f0f2f6; color: #333; padding: 8px 12px; text-align: left; border-bottom: 2px solid #ddd; }
    .history-table td { padding: 8px 12px; border-bottom: 1px solid #eee; }
    .history-table .num { text-align: right; font-family: monospace; }
    </style>
    <table class="history-table">
    <thead>
        <tr>
            <th>Date</th>
            <th>Time</th>
            <th class="num">SYS</th>
            <th class="num">DIA</th>
            <th class="num">Pulse</th>
            <th>IHB</th>
            <th>MOV</th>
            <th>Category</th>
            <th>Garmin</th>
            <th>MQTT</th>
        </tr>
    </thead>
    <tbody>
    """

    for _, row in df.iterrows():
        ihb = icon_warning if row["irregular_heartbeat"] else ""
        mov = icon_running if row["body_movement"] else ""
        garmin = icon_check if row["garmin_uploaded"] else icon_xmark
        mqtt = icon_check if row["mqtt_published"] else icon_xmark

        table_html += f"""
        <tr>
            <td>{row["Date"]}</td>
            <td>{row["Time"]}</td>
            <td class="num">{row["systolic"]}</td>
            <td class="num">{row["diastolic"]}</td>
            <td class="num">{row["pulse"]}</td>
            <td>{ihb}</td>
            <td>{mov}</td>
            <td>{row["Category"]}</td>
            <td>{garmin}</td>
            <td>{mqtt}</td>
        </tr>
        """

    table_html += "</tbody></table>"

    # Display HTML table using st.html() which properly renders HTML
    st.html(table_html)

    # Export options
    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        # CSV export
        csv = df.to_csv(index=False)
        st.download_button(
            label="Download as CSV",
            icon=":material/download:",
            data=csv,
            file_name=f"blood_pressure_history_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )

    with col2:
        # Summary statistics
        st.markdown("**Summary Statistics:**")
        st.write(f"- Average SYS: {df['systolic'].mean():.0f} mmHg")
        st.write(f"- Average DIA: {df['diastolic'].mean():.0f} mmHg")
        st.write(f"- Average Pulse: {df['pulse'].mean():.0f} bpm")
        st.write(f"- IHB events: {df['irregular_heartbeat'].sum()}")
        st.write(f"- MOV events: {df['body_movement'].sum()}")


if __name__ == "__main__":
    main()
