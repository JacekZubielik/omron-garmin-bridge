"""OMRON Garmin Bridge - Streamlit Web UI.

Main application entry point for the web dashboard.

Usage:
    pdm run streamlit run streamlit_app/app.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.duplicate_filter import DuplicateFilter  # noqa: E402
from streamlit_app.components.icons import (  # noqa: E402
    ICONS,
    get_bp_category_icon,
    load_fontawesome,
)
from streamlit_app.components.version import show_version_footer  # noqa: E402  # type: ignore

# Load Font Awesome
load_fontawesome()

# Initialize session state
if "db" not in st.session_state:
    db_path = project_root / "data" / "omron.db"
    st.session_state.db = DuplicateFilter(str(db_path))


def get_db() -> DuplicateFilter:
    """Get database instance from session state."""
    db: DuplicateFilter = st.session_state.db
    return db


def main() -> None:
    """Main application."""
    st.markdown(f"# {ICONS['heart']} Dashboard", unsafe_allow_html=True)
    st.markdown("---")

    db = get_db()

    # Sidebar - User filter and Status
    with st.sidebar:
        # User slot filter
        user_slot = st.selectbox(
            "User",
            options=[None, 1, 2],
            format_func=lambda x: "All Users" if x is None else f"User {x}",
            key="dashboard_user_slot",
        )

        st.markdown("---")
        st.header("Status")

        # Get statistics (filtered by user_slot)
        stats = db.get_statistics(user_slot=user_slot)

        # Connection status indicators
        st.subheader("Connections")
        col1, col2 = st.columns(2)
        with col1:
            garmin_pct = (
                (stats["garmin_uploaded"] / stats["total_records"] * 100)
                if stats["total_records"] > 0
                else 0
            )
            st.metric("Garmin", f"{stats['garmin_uploaded']}", f"{garmin_pct:.0f}%")
        with col2:
            mqtt_pct = (
                (stats["mqtt_published"] / stats["total_records"] * 100)
                if stats["total_records"] > 0
                else 0
            )
            st.metric("MQTT", f"{stats['mqtt_published']}", f"{mqtt_pct:.0f}%")

        st.subheader("Database")
        st.metric("Total Records", stats["total_records"])

        if stats["first_record"]:
            st.caption(f"From: {stats['first_record'][:10]}")
        if stats["last_record"]:
            st.caption(f"To: {stats['last_record'][:10]}")

        st.markdown("---")
        show_version_footer()

    # Main content - Dashboard
    col1, col2 = st.columns(2)

    # Last reading
    history = db.get_history(limit=1, user_slot=user_slot)
    if history:
        last = history[0]
        with col1:
            st.subheader("Last Reading")

            # Format timestamp: "2025-12-27T21:13:00" -> "27 Dec 2025, 21:13"
            ts = datetime.fromisoformat(last["timestamp"])
            formatted_date = ts.strftime("%d %b %Y, %H:%M")
            st.markdown(f"{ICONS['calendar']} **Date:** {formatted_date}", unsafe_allow_html=True)

            st.metric("Systolic", f"{last['systolic']} mmHg")
            st.metric("Diastolic", f"{last['diastolic']} mmHg")
            st.metric("Pulse", f"{last['pulse']} bpm")

            # Flags
            flags = []
            if last.get("irregular_heartbeat"):
                flags.append(f"{ICONS['warning']} IHB")
            if last.get("body_movement"):
                flags.append(f"{ICONS['warning']} MOV")
            if flags:
                st.markdown(
                    f"<div style='color: #ffc107;'>{' | '.join(flags)}</div>",
                    unsafe_allow_html=True,
                )

        # Average Blood Pressure
        with col2:
            st.subheader("Average Blood Pressure")

            # Category with icon
            category = last.get("category", "unknown")
            cat_icon = get_bp_category_icon(category)
            st.markdown(f"{cat_icon} {category.replace('_', ' ').title()}", unsafe_allow_html=True)

            if stats.get("avg_systolic"):
                st.metric("Systolic", f"{stats['avg_systolic']:.0f} mmHg")
                st.metric("Diastolic", f"{stats['avg_diastolic']:.0f} mmHg")
                st.metric("Pulse", f"{stats['avg_pulse']:.0f} bpm")
    else:
        st.info("No readings in database. Run a sync to get started!")
        st.code("pdm run python -m src.main sync", language="bash")

    # Recent readings table
    st.markdown("---")
    st.subheader("Recent Readings")

    history = db.get_history(limit=10, user_slot=user_slot)
    if history:
        # Convert to display format
        display_data = []
        for r in history:
            flags = []
            if r.get("irregular_heartbeat"):
                flags.append("IHB")
            if r.get("body_movement"):
                flags.append("MOV")

            # Format timestamp
            ts = datetime.fromisoformat(r["timestamp"])
            formatted_time = ts.strftime("%d %b %Y, %H:%M")

            row: dict[str, str | int] = {"Date": formatted_time}
            # Show User column only when "All Users" is selected
            if user_slot is None:
                row["User"] = r.get("user_slot", 1)
            row.update(
                {
                    "SYS": r["systolic"],
                    "DIA": r["diastolic"],
                    "Pulse": r["pulse"],
                    "Flags": ", ".join(flags) if flags else "-",
                    "Garmin": "✓" if r.get("garmin_uploaded") else "✗",
                    "MQTT": "✓" if r.get("mqtt_published") else "✗",
                }
            )
            display_data.append(row)

        st.dataframe(display_data, width="stretch", hide_index=True)
    else:
        st.write("No readings yet.")


if __name__ == "__main__":
    main()
