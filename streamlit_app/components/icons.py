"""Font Awesome icons helper for Streamlit."""

from __future__ import annotations

import streamlit as st

# Font Awesome CSS - load once per page
FA_CSS = """
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
<style>
.fa-icon { font-size: 1em; }
.fa-icon-lg { font-size: 1.2em; }
.fa-icon-success { color: #28a745; }
.fa-icon-danger { color: #dc3545; }
.fa-icon-warning { color: #ffc107; }
.fa-icon-info { color: #17a2b8; }
.fa-icon-muted { color: #6c757d; }
</style>
"""


def load_fontawesome() -> None:
    """Load Font Awesome CSS. Call once per page."""
    st.markdown(FA_CSS, unsafe_allow_html=True)


def icon(name: str, color: str = "", size: str = "") -> str:
    """Generate Font Awesome icon HTML.

    Args:
        name: Icon name without 'fa-' prefix (e.g., 'check', 'heart-pulse')
        color: Color class: success, danger, warning, info, muted
        size: Size class: lg for larger

    Returns:
        HTML string for the icon
    """
    classes = ["fa-solid", f"fa-{name}", "fa-icon"]
    if size:
        classes.append(f"fa-icon-{size}")
    if color:
        classes.append(f"fa-icon-{color}")
    return f'<i class="{" ".join(classes)}"></i>'


def icon_text(icon_name: str, text: str, color: str = "") -> str:
    """Generate icon with text."""
    return f"{icon(icon_name, color)} {text}"


# Pre-defined icons
ICONS = {
    # Status
    "check": icon("check", "success"),
    "xmark": icon("xmark", "danger"),
    "warning": icon("triangle-exclamation", "warning"),
    "info": icon("circle-info", "info"),
    # Bluetooth/Connection
    "bluetooth": icon("bluetooth-b", "info"),
    "link": icon("link", "success"),
    "unlink": icon("link-slash", "muted"),
    "plug": icon("plug", "success"),
    "plug_off": icon("plug-circle-xmark", "danger"),
    # Health
    "heart": icon("heart-pulse", "danger"),
    "heart_circle": icon("heart-circle-check", "success"),
    # Actions
    "sync": icon("rotate", "success"),
    "scan": icon("magnifying-glass"),
    "settings": icon("gear", "danger"),
    "save": icon("floppy-disk"),
    "refresh": icon("arrows-rotate"),
    # Data
    "calendar": icon("calendar-days", "warning"),
    "chart": icon("chart-line", "warning"),
    "table": icon("table", "warning"),
    "database": icon("database", "warning"),
    # Devices
    "device": icon("mobile-screen"),
    # Lock/Security
    "lock": icon("lock", "success"),
    "unlock": icon("lock-open", "muted"),
    # Arrows/Navigation
    "arrow_up": icon("arrow-up", "danger"),
    "arrow_down": icon("arrow-down", "success"),
    # Categories (blood pressure)
    "bp_optimal": icon("circle", "success"),
    "bp_normal": icon("circle", "success"),
    "bp_high_normal": icon("circle", "warning"),
    "bp_grade1": icon("circle-exclamation", "warning"),
    "bp_grade2": icon("circle-exclamation", "danger"),
    "bp_grade3": icon("circle-radiation", "danger"),
}


def get_bp_category_icon(category: str) -> str:
    """Get icon for blood pressure category."""
    category_map = {
        "optimal": ICONS["bp_optimal"],
        "normal": ICONS["bp_normal"],
        "high_normal": ICONS["bp_high_normal"],
        "grade1_hypertension": ICONS["bp_grade1"],
        "grade2_hypertension": ICONS["bp_grade2"],
        "grade3_hypertension": ICONS["bp_grade3"],
    }
    return category_map.get(category, icon("circle-question", "muted"))
