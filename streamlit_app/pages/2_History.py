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
    st.title("📈 Reading History")
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
        show_flags_only = st.checkbox("Show only readings with flags")

    with col4:
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

    # Filter by flags if requested
    if show_flags_only:
        history = [r for r in history if r.get("irregular_heartbeat") or r.get("body_movement")]

    if not history:
        st.warning("No readings found with selected filters.")
        return

    st.markdown("---")
    st.subheader(f"Found {len(history)} readings")

    # Convert to DataFrame for display
    df = pd.DataFrame(history)

    # Format columns
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["Date"] = df["timestamp"].dt.strftime("%Y-%m-%d")
    df["Time"] = df["timestamp"].dt.strftime("%H:%M")
    df["IHB"] = df["irregular_heartbeat"].apply(lambda x: "⚠️" if x else "")
    df["MOV"] = df["body_movement"].apply(lambda x: "🏃" if x else "")
    df["Garmin"] = df["garmin_uploaded"].apply(lambda x: "✅" if x else "❌")
    df["MQTT"] = df["mqtt_published"].apply(lambda x: "✅" if x else "❌")

    # Select and rename columns for display
    display_df = df[
        [
            "Date",
            "Time",
            "systolic",
            "diastolic",
            "pulse",
            "IHB",
            "MOV",
            "category",
            "Garmin",
            "MQTT",
        ]
    ].rename(
        columns={
            "systolic": "SYS",
            "diastolic": "DIA",
            "pulse": "Pulse",
            "category": "Category",
        }
    )

    # Format category
    display_df["Category"] = display_df["Category"].apply(
        lambda x: x.replace("_", " ").title() if x else "Unknown"
    )

    # Display table
    st.dataframe(
        display_df,
        width="stretch",
        hide_index=True,
        column_config={
            "SYS": st.column_config.NumberColumn("SYS", format="%d mmHg"),
            "DIA": st.column_config.NumberColumn("DIA", format="%d mmHg"),
            "Pulse": st.column_config.NumberColumn("Pulse", format="%d bpm"),
        },
    )

    # Export options
    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        # CSV export
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download as CSV",
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
