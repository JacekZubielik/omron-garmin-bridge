"""Dashboard page - Overview of blood pressure readings."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.duplicate_filter import DuplicateFilter  # noqa: E402
from streamlit_app.components.icons import ICONS, load_fontawesome  # noqa: E402

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")


def get_db() -> DuplicateFilter:
    """Get or create database instance."""
    if "db" not in st.session_state:
        db_path = project_root / "data" / "omron.db"
        st.session_state.db = DuplicateFilter(str(db_path))
    db: DuplicateFilter = st.session_state.db
    return db


def main() -> None:
    """Dashboard page."""
    load_fontawesome()

    with st.sidebar:
        st.markdown("---")
        st.caption("OMRON Garmin Bridge v0.1.0")

    st.markdown(f"# {ICONS['chart']} Dashboard", unsafe_allow_html=True)
    st.markdown("Blood pressure monitoring overview")

    db = get_db()
    _ = db.get_statistics()  # Validate DB connection

    # Date range filter
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        days = st.selectbox(
            "Time Range",
            options=[7, 14, 30, 90, 365],
            format_func=lambda x: f"Last {x} days",
            index=1,
        )
    with col3:
        if st.button("Refresh", icon=":material/refresh:"):
            st.rerun()

    # Get history for selected period
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    history = db.get_history(limit=1000, start_date=start_date, end_date=end_date)

    if not history:
        st.warning("No readings found for selected period.")
        return

    # Summary metrics
    st.markdown("---")
    st.subheader("Averages")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        avg_sys = sum(r["systolic"] for r in history) / len(history)
        st.metric("Systolic", f"{avg_sys:.0f} mmHg")

    with col2:
        avg_dia = sum(r["diastolic"] for r in history) / len(history)
        st.metric("Diastolic", f"{avg_dia:.0f} mmHg")

    with col3:
        avg_pulse = sum(r["pulse"] for r in history) / len(history)
        st.metric("Pulse", f"{avg_pulse:.0f} bpm")

    with col4:
        st.metric("Readings", len(history))

    # Blood Pressure Chart
    st.markdown("---")
    st.subheader("Blood Pressure Trend")

    # Prepare data for chart
    dates = [datetime.fromisoformat(r["timestamp"]) for r in history]
    systolic = [r["systolic"] for r in history]
    diastolic = [r["diastolic"] for r in history]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=systolic,
            mode="lines+markers",
            name="Systolic",
            line={"color": "#e74c3c", "width": 2},
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
    )

    st.plotly_chart(fig, width="stretch")

    # Pulse Chart
    st.subheader("Heart Rate Trend")
    pulse = [r["pulse"] for r in history]

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
