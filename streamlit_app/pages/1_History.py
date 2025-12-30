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
from streamlit_app.components.version import show_version_footer  # noqa: E402


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
            options=[1, 2, None],
            format_func=lambda x: "All users" if x is None else f"User {x}",
            index=0,  # Default to User 1
        )
        limit = st.number_input("Max records", min_value=10, max_value=1000, value=100)
        st.markdown("---")
        show_version_footer()

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

    # Prepare data for chart - reshape for area chart
    df_chart = df.copy()
    df_chart["User"] = df_chart["user_slot"].apply(lambda x: f"User {x}")

    if user_slot is None:
        # All users - show lines with both users
        # Melt dataframe for systolic/diastolic split
        df_sys = df_chart[["timestamp", "systolic", "User"]].copy()
        df_sys["Metric"] = "Systolic"
        df_sys = df_sys.rename(columns={"systolic": "Value"})

        df_dia = df_chart[["timestamp", "diastolic", "User"]].copy()
        df_dia["Metric"] = "Diastolic"
        df_dia = df_dia.rename(columns={"diastolic": "Value"})

        df_melted = pd.concat([df_sys, df_dia])
        df_melted["Label"] = df_melted["User"] + " - " + df_melted["Metric"]

        fig = px.line(
            df_melted.sort_values("timestamp"),
            x="timestamp",
            y="Value",
            color="Label",
            line_group="Label",
            color_discrete_map={
                "User 1 - Systolic": "#dc3545",
                "User 1 - Diastolic": "#3498db",
                "User 2 - Systolic": "#e74c3c",
                "User 2 - Diastolic": "#2980b9",
            },
            markers=True,
        )
    else:
        # Single user - show systolic and diastolic lines
        df_melted = df_chart.melt(
            id_vars=["timestamp"],
            value_vars=["systolic", "diastolic"],
            var_name="Metric",
            value_name="Value",
        )
        df_melted["Metric"] = df_melted["Metric"].str.title()

        fig = px.line(
            df_melted.sort_values("timestamp"),
            x="timestamp",
            y="Value",
            color="Metric",
            color_discrete_map={
                "Systolic": "#dc3545",
                "Diastolic": "#3498db",
            },
            markers=True,
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

    st.plotly_chart(fig, use_container_width=True)

    # Pulse Chart
    st.subheader("Heart Rate Trend")

    if user_slot is None:
        # All users - show both users
        fig_pulse = px.area(
            df_chart.sort_values("timestamp"),
            x="timestamp",
            y="pulse",
            color="User",
            color_discrete_map={
                "User 1": "#9b59b6",
                "User 2": "#8e44ad",
            },
        )
    else:
        # Single user - area chart
        df_pulse = df_chart.sort_values("timestamp")
        fig_pulse = px.area(
            df_pulse,
            x="timestamp",
            y="pulse",
            color_discrete_sequence=["#9b59b6"],
        )

    fig_pulse.add_hline(y=100, line_dash="dash", line_color="orange", annotation_text="High")
    fig_pulse.add_hline(y=60, line_dash="dash", line_color="blue", annotation_text="Low")

    fig_pulse.update_layout(
        xaxis_title="Date",
        yaxis_title="BPM",
        hovermode="x unified",
        legend={"yanchor": "top", "y": 0.99, "xanchor": "left", "x": 0.01},
        margin={"t": 20},
    )

    st.plotly_chart(fig_pulse, use_container_width=True)

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
            # Color map based on BP category severity (key = raw category name from DB)
            category_colors = {
                "optimal": "#28a745",  # zielony
                "normal": "#5cb85c",  # jasnozielony
                "high_normal": "#8bc34a",  # ciepły zielony
                "grade1_hypertension": "#b39ddb",  # delikatny fioletowy
                "grade2_hypertension": "#dc3545",  # czerwony
                "grade3_hypertension": "#6a1b3d",  # ciężki krwisty fiolet
                "unknown": "#6c757d",
            }

            # Define order (worst at top, best at bottom)
            category_order = [
                "grade3_hypertension",
                "grade2_hypertension",
                "grade1_hypertension",
                "high_normal",
                "normal",
                "optimal",
                "unknown",
            ]

            # Sort categories by defined order
            sorted_cats = []
            for cat in category_order:
                if cat in categories:
                    sorted_cats.append((cat, categories[cat]))

            # Add any categories not in order
            for raw_cat, count in categories.items():
                if raw_cat not in [c[0] for c in sorted_cats]:
                    sorted_cats.append((raw_cat, count))

            cat_names = [c[0].replace("_", " ").title() for c in sorted_cats]
            cat_values = [c[1] for c in sorted_cats]
            colors = [category_colors.get(c[0], "#6c757d") for c in sorted_cats]

            fig_cat = go.Figure()
            fig_cat.add_trace(
                go.Bar(
                    x=cat_values,
                    y=cat_names,
                    orientation="h",
                    marker_color=colors,
                    text=cat_values,
                    textposition="inside",
                    insidetextanchor="middle",
                    texttemplate="<b>%{text}</b>",
                    textfont_size=24,
                )
            )
            fig_cat.update_layout(
                xaxis_title="Count",
                yaxis_title="",
                margin={"t": 20, "l": 10},
                showlegend=False,
                yaxis={"tickfont": {"size": 14}},
            )
            st.plotly_chart(fig_cat, use_container_width=True)

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
