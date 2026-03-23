"""History page - Detailed reading history with filtering."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.duplicate_filter import DuplicateFilter  # noqa: E402
from streamlit_app.components.icons import ICONS, load_fontawesome  # noqa: E402
from streamlit_app.components.version import show_version_footer  # noqa: E402

# Theme-adaptive layout — transparent backgrounds let Streamlit control dark/light
MEDICAL_LAYOUT = {
    "font": {"family": "Inter, -apple-system, SF Pro Display, sans-serif", "size": 13},
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
    "margin": {"l": 55, "r": 20, "t": 35, "b": 55},
    "xaxis": {
        "gridcolor": "rgba(128,128,128,0.15)",
        "gridwidth": 1,
        "zeroline": False,
        "showline": True,
        "linewidth": 1,
        "linecolor": "rgba(128,128,128,0.3)",
        "tickformat": "%b %d",
        "ticks": "outside",
        "ticklen": 4,
    },
    "yaxis": {
        "gridcolor": "rgba(128,128,128,0.15)",
        "gridwidth": 1,
        "zeroline": False,
        "showline": True,
        "linewidth": 1,
        "linecolor": "rgba(128,128,128,0.3)",
        "ticks": "outside",
        "ticklen": 4,
    },
    "hoverlabel": {"font_size": 12},
}

# BP category colors (clinical palette)
CATEGORY_COLORS = {
    "optimal": "#10B981",
    "normal": "#059669",
    "high_normal": "#D97706",
    "grade1_hypertension": "#DC2626",
    "grade2_hypertension": "#B91C1C",
    "grade3_hypertension": "#991B1B",
    "unknown": "#9CA3AF",
}

CATEGORY_ORDER = [
    "grade3_hypertension",
    "grade2_hypertension",
    "grade1_hypertension",
    "high_normal",
    "normal",
    "optimal",
]


def get_db() -> DuplicateFilter:
    """Get or create database instance."""
    if "db" not in st.session_state:
        db_path = project_root / "data" / "omron.db"
        st.session_state.db = DuplicateFilter(str(db_path))
    db: DuplicateFilter = st.session_state.db
    return db


def build_bp_chart(df_chart: pd.DataFrame, user_slot: int | None) -> go.Figure:
    """Build blood pressure trend chart with shaded risk zones."""
    fig = go.Figure()

    # Shaded risk zones — low opacity works in both light and dark mode
    fig.add_hrect(y0=0, y1=80, fillcolor="#10B981", opacity=0.07, line_width=0)
    fig.add_hrect(y0=80, y1=90, fillcolor="#10B981", opacity=0.04, line_width=0)
    fig.add_hrect(y0=120, y1=140, fillcolor="#F59E0B", opacity=0.08, line_width=0)
    fig.add_hrect(y0=140, y1=220, fillcolor="#EF4444", opacity=0.08, line_width=0)

    # Subtle threshold lines (only 2, not 4)
    fig.add_hline(y=140, line_dash="dot", line_color="#F87171", line_width=1, opacity=0.5)
    fig.add_hline(y=90, line_dash="dot", line_color="#F87171", line_width=1, opacity=0.5)

    df_sorted = df_chart.sort_values("timestamp")

    if user_slot is None:
        for slot in df_sorted["user_slot"].unique():
            df_u = df_sorted[df_sorted["user_slot"] == slot]
            label = f"User {slot}"
            fig.add_trace(
                go.Scatter(
                    x=df_u["timestamp"],
                    y=df_u["systolic"],
                    name=f"{label} SYS",
                    mode="lines+markers",
                    line={"color": "#DC2626", "width": 2.5},
                    marker={"size": 7, "line": {"width": 1.5, "color": "white"}},
                    legendgroup=label,
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=df_u["timestamp"],
                    y=df_u["diastolic"],
                    name=f"{label} DIA",
                    mode="lines+markers",
                    line={"color": "#1E40AF", "width": 2, "dash": "dot"},
                    marker={"size": 5, "symbol": "diamond", "line": {"width": 1, "color": "white"}},
                    legendgroup=label,
                )
            )
    else:
        fig.add_trace(
            go.Scatter(
                x=df_sorted["timestamp"],
                y=df_sorted["systolic"],
                name="Systolic",
                mode="lines+markers",
                line={"color": "#DC2626", "width": 2.5},
                marker={"size": 7, "line": {"width": 1.5, "color": "white"}},
                fill="tonexty" if len(df_sorted) > 2 else None,
            )
        )
        fig.add_trace(
            go.Scatter(
                x=df_sorted["timestamp"],
                y=df_sorted["diastolic"],
                name="Diastolic",
                mode="lines+markers",
                line={"color": "#1E40AF", "width": 2, "dash": "dot"},
                marker={"size": 5, "symbol": "diamond", "line": {"width": 1, "color": "white"}},
            )
        )

    fig.update_layout(
        **MEDICAL_LAYOUT,
        height=380,
        xaxis_title="",
        yaxis_title="mmHg",
        hovermode="x unified",
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
            "bgcolor": "rgba(0,0,0,0)",
            "bordercolor": "rgba(0,0,0,0)",
            "borderwidth": 0,
        },
    )
    return fig


def build_pulse_chart(df_chart: pd.DataFrame, user_slot: int | None) -> go.Figure:
    """Build heart rate trend chart."""
    fig = go.Figure()

    # Normal range zone
    fig.add_hrect(y0=60, y1=100, fillcolor="#7C3AED", opacity=0.06, line_width=0)
    fig.add_hline(y=80, line_dash="dot", line_color="#A5B4FC", line_width=1, opacity=0.3)

    df_sorted = df_chart.sort_values("timestamp")

    if user_slot is None:
        for slot in df_sorted["user_slot"].unique():
            df_u = df_sorted[df_sorted["user_slot"] == slot]
            fig.add_trace(
                go.Scatter(
                    x=df_u["timestamp"],
                    y=df_u["pulse"],
                    name=f"User {slot}",
                    mode="lines+markers",
                    line={"color": "#7C3AED" if slot == 1 else "#A78BFA", "width": 2.5},
                    marker={"size": 6, "line": {"width": 1, "color": "white"}},
                )
            )
    else:
        fig.add_trace(
            go.Scatter(
                x=df_sorted["timestamp"],
                y=df_sorted["pulse"],
                name="Pulse",
                mode="lines+markers",
                line={"color": "#7C3AED", "width": 2.5},
                marker={"size": 6, "line": {"width": 1, "color": "white"}},
                fill="tozeroy",
                fillcolor="rgba(124, 58, 237, 0.06)",
            )
        )

    fig.update_layout(
        **MEDICAL_LAYOUT,
        height=280,
        xaxis_title="",
        yaxis_title="BPM",
        hovermode="x unified",
        showlegend=user_slot is None,
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
        },
    )
    return fig


def build_category_donut(history: list[dict]) -> go.Figure:
    """Build category distribution donut chart."""
    categories: dict[str, int] = {}
    for r in history:
        cat = r.get("category", "unknown")
        categories[cat] = categories.get(cat, 0) + 1

    # Sort by severity order
    sorted_cats = []
    for cat in CATEGORY_ORDER:
        if cat in categories:
            sorted_cats.append((cat, categories[cat]))
    for raw_cat, count in categories.items():
        if raw_cat not in [c[0] for c in sorted_cats]:
            sorted_cats.append((raw_cat, count))

    labels = [c[0].replace("_", " ").title() for c in sorted_cats]
    values = [c[1] for c in sorted_cats]
    colors = [CATEGORY_COLORS.get(c[0], "#9CA3AF") for c in sorted_cats]

    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.55,
                marker_colors=colors,
                textinfo="label+value",
                textposition="outside",
                textfont_size=12,
                pull=[0.02] * len(labels),
                hovertemplate="<b>%{label}</b><br>%{value} readings (%{percent})<extra></extra>",
            )
        ]
    )

    total = sum(values)
    fig.add_annotation(
        text=f"<b>{total}</b><br><span style='font-size:11px;color:#6B7280'>total</span>",
        x=0.5,
        y=0.5,
        font_size=28,
        showarrow=False,
    )

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, -apple-system, sans-serif", "size": 12},
        height=320,
        margin={"t": 10, "b": 10, "l": 10, "r": 10},
        showlegend=False,
    )
    return fig


def build_scatter(df_chart: pd.DataFrame) -> go.Figure:
    """Build SYS vs DIA scatter plot with risk zones."""
    fig = go.Figure()

    # Risk zone backgrounds — low opacity for both themes
    fig.add_shape(
        type="rect", x0=0, x1=80, y0=0, y1=120, fillcolor="#10B981", opacity=0.07, line_width=0
    )
    fig.add_shape(
        type="rect", x0=80, x1=90, y0=120, y1=140, fillcolor="#F59E0B", opacity=0.08, line_width=0
    )
    fig.add_shape(
        type="rect", x0=90, x1=130, y0=140, y1=220, fillcolor="#EF4444", opacity=0.07, line_width=0
    )

    # Threshold lines
    fig.add_hline(y=140, line_dash="dot", line_color="#F87171", line_width=1, opacity=0.4)
    fig.add_vline(x=90, line_dash="dot", line_color="#F87171", line_width=1, opacity=0.4)

    # Map categories to colors
    for _, row in df_chart.iterrows():
        cat = row.get("category", "unknown")
        color = CATEGORY_COLORS.get(cat, "#9CA3AF")
        fig.add_trace(
            go.Scatter(
                x=[row["diastolic"]],
                y=[row["systolic"]],
                mode="markers",
                marker={
                    "size": max(8, row["pulse"] / 8),
                    "color": color,
                    "line": {"width": 1.5, "color": "white"},
                    "opacity": 0.85,
                },
                hovertemplate=(
                    f"<b>{row['timestamp'].strftime('%d %b %Y, %H:%M')}</b><br>"
                    f"SYS: {row['systolic']} mmHg<br>"
                    f"DIA: {row['diastolic']} mmHg<br>"
                    f"Pulse: {row['pulse']} bpm<extra></extra>"
                ),
                showlegend=False,
            )
        )

    fig.update_layout(
        font=MEDICAL_LAYOUT["font"],
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=MEDICAL_LAYOUT["margin"],
        hoverlabel=MEDICAL_LAYOUT["hoverlabel"],
        height=350,
        xaxis_title="Diastolic (mmHg)",
        yaxis_title="Systolic (mmHg)",
        xaxis={
            "range": [50, max(df_chart["diastolic"].max() + 15, 110)],
            "gridcolor": "rgba(128,128,128,0.15)",
            "showline": True,
            "linecolor": "rgba(128,128,128,0.3)",
        },
        yaxis={
            "range": [80, max(df_chart["systolic"].max() + 15, 180)],
            "gridcolor": "rgba(128,128,128,0.15)",
            "showline": True,
            "linecolor": "rgba(128,128,128,0.3)",
        },
    )
    return fig


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
            index=0,
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

    # Convert to DataFrame
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
        df = pd.DataFrame(history)
        df["timestamp"] = pd.to_datetime(df["timestamp"])

    display_data = []
    for _, r in df.iterrows():
        flags = []
        if r.get("irregular_heartbeat"):
            flags.append("IHB")
        if r.get("body_movement"):
            flags.append("MOV")

        display_data.append(
            {
                "Date": r["timestamp"].strftime("%d %b %Y, %H:%M"),
                "SYS": r["systolic"],
                "DIA": r["diastolic"],
                "Pulse": r["pulse"],
                "Category": (
                    r["category"].replace("_", " ").title() if r.get("category") else "Unknown"
                ),
                "Flags": ", ".join(flags) if flags else "-",
                "Garmin": "\u2713" if r.get("garmin_uploaded") else "\u2717",
                "MQTT": "\u2713" if r.get("mqtt_published") else "\u2717",
            }
        )

    st.dataframe(display_data, use_container_width=True, hide_index=True)

    csv = df.to_csv(index=False)
    st.download_button(
        label="Download as CSV",
        icon=":material/download:",
        data=csv,
        file_name=f"blood_pressure_history_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )

    # Blood Pressure Trend
    st.markdown("---")
    st.subheader("Blood Pressure Trend")
    df_chart = df.copy()
    fig_bp = build_bp_chart(df_chart, user_slot)
    st.plotly_chart(fig_bp, use_container_width=True)

    # Heart Rate Trend
    st.subheader("Heart Rate Trend")
    fig_pulse = build_pulse_chart(df_chart, user_slot)
    st.plotly_chart(fig_pulse, use_container_width=True)

    # Bottom row: Category donut + SYS vs DIA scatter
    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("BP Categories")
        fig_cat = build_category_donut(history)
        st.plotly_chart(fig_cat, use_container_width=True)

    with col2:
        st.subheader("SYS vs DIA")
        fig_scatter = build_scatter(df_chart)
        st.plotly_chart(fig_scatter, use_container_width=True)

    # Flags section
    st.markdown("---")
    ihb_count = sum(1 for r in history if r.get("irregular_heartbeat"))
    mov_count = sum(1 for r in history if r.get("body_movement"))

    c1, c2 = st.columns(2)
    c1.metric("Irregular Heartbeat (IHB)", ihb_count)
    c2.metric("Body Movement (MOV)", mov_count)

    if ihb_count > 0:
        st.markdown(
            f"{ICONS['warning']} **{ihb_count} readings with irregular heartbeat detected.** "
            "Consider consulting a healthcare provider.",
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
