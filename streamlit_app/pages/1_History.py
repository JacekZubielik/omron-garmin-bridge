"""History page - Detailed reading history with filtering."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.duplicate_filter import DuplicateFilter  # noqa: E402
from streamlit_app.components.icons import ICONS, load_fontawesome  # noqa: E402


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

    db = get_db()

    # Sidebar - Filters
    with st.sidebar:
        st.subheader("Filters")
        days = st.selectbox(
            "Time Range",
            options=[7, 14, 30, 90, 365, 0],
            format_func=lambda x: f"Last {x} days" if x > 0 else "All time",
            index=2,
        )
        user_slot = st.selectbox(
            "User Slot",
            options=[None, 1, 2],
            format_func=lambda x: "All users" if x is None else f"User {x}",
        )
        limit = st.number_input("Max records", min_value=10, max_value=1000, value=100)
        st.markdown("---")
        st.caption("OMRON Garmin Bridge v0.1.0")

    st.markdown(f"# {ICONS['table']} Reading History", unsafe_allow_html=True)
    st.markdown("Browse and filter blood pressure readings")

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

    # Convert to DataFrame for display
    df = pd.DataFrame(history)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Table section
    st.markdown("---")
    st.subheader(f"Found {len(history)} readings")
    show_flags_only = st.checkbox("Show only readings with flags")

    if show_flags_only:
        history = [r for r in history if r.get("irregular_heartbeat") or r.get("body_movement")]
        if not history:
            st.warning("No readings with flags found.")
            return
        # Rebuild df after filtering
        df = pd.DataFrame(history)
        df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Build display data like Dashboard
    display_data = []
    for _, r in df.iterrows():
        flags = []
        if r.get("irregular_heartbeat"):
            flags.append("IHB")
        if r.get("body_movement"):
            flags.append("MOV")

        # Format timestamp
        formatted_time = r["timestamp"].strftime("%d %b %Y, %H:%M")

        display_data.append(
            {
                "Date": formatted_time,
                "SYS": r["systolic"],
                "DIA": r["diastolic"],
                "Pulse": r["pulse"],
                "Category": (
                    r["category"].replace("_", " ").title() if r.get("category") else "Unknown"
                ),
                "Flags": ", ".join(flags) if flags else "-",
                "Garmin": "✓" if r.get("garmin_uploaded") else "✗",
                "MQTT": "✓" if r.get("mqtt_published") else "✗",
            }
        )

    st.dataframe(display_data, width="stretch", hide_index=True)

    # CSV export
    csv = df.to_csv(index=False)
    st.download_button(
        label="Download as CSV",
        icon=":material/download:",
        data=csv,
        file_name=f"blood_pressure_history_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )

    # Blood Pressure Chart
    st.markdown("---")
    st.subheader("Blood Pressure Trend")

    # Prepare data for chart
    dates = df["timestamp"].tolist()
    systolic = df["systolic"].tolist()
    diastolic = df["diastolic"].tolist()

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=systolic,
            mode="lines+markers",
            name="Systolic",
            line={"color": "#dc3545", "width": 2},
            marker={"size": 6},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=diastolic,
            mode="lines+markers",
            name="Diastolic",
            line={"color": "#3498db", "width": 2},
            marker={"size": 6},
        )
    )

    # Add reference lines
    fig.add_hline(y=140, line_dash="dash", line_color="orange", annotation_text="High SYS")
    fig.add_hline(y=90, line_dash="dash", line_color="orange", annotation_text="High DIA")
    fig.add_hline(y=120, line_dash="dot", line_color="green", annotation_text="Normal SYS")
    fig.add_hline(y=80, line_dash="dot", line_color="green", annotation_text="Normal DIA")

    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="mmHg",
        hovermode="x unified",
        legend={"yanchor": "top", "y": 0.99, "xanchor": "left", "x": 0.01},
        margin={"t": 20},
    )

    st.plotly_chart(fig, width="stretch")

    # Pulse Chart
    st.subheader("Heart Rate Trend")
    pulse = df["pulse"].tolist()

    fig_pulse = go.Figure()
    fig_pulse.add_trace(
        go.Scatter(
            x=dates,
            y=pulse,
            mode="lines+markers",
            name="Pulse",
            line={"color": "#9b59b6", "width": 2},
            fill="tozeroy",
            fillcolor="rgba(155, 89, 182, 0.1)",
        )
    )

    fig_pulse.add_hline(y=100, line_dash="dash", line_color="orange", annotation_text="High")
    fig_pulse.add_hline(y=60, line_dash="dash", line_color="blue", annotation_text="Low")

    fig_pulse.update_layout(
        xaxis_title="Date",
        yaxis_title="BPM",
        hovermode="x unified",
        margin={"t": 20},
    )

    st.plotly_chart(fig_pulse, width="stretch")

    # Category distribution
    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Reading Categories")
        categories: dict[str, int] = {}
        for r in history:
            cat = r.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1

        if categories:
            fig_cat = px.pie(
                values=list(categories.values()),
                names=[c.replace("_", " ").title() for c in categories],
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            st.plotly_chart(fig_cat, width="stretch")

    with col2:
        st.subheader("Flags Detected")
        ihb_count = sum(1 for r in history if r.get("irregular_heartbeat"))
        mov_count = sum(1 for r in history if r.get("body_movement"))

        st.metric("Irregular Heartbeat (IHB)", ihb_count)
        st.metric("Body Movement (MOV)", mov_count)

        if ihb_count > 0:
            st.markdown(
                f"{ICONS['warning']} **{ihb_count} readings with irregular heartbeat detected.** "
                "Consider consulting a healthcare provider.",
                unsafe_allow_html=True,
            )


if __name__ == "__main__":
    main()
