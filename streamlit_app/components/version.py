"""Version helper for Streamlit UI."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import streamlit as st


@lru_cache(maxsize=1)
def get_version() -> str:
    """Get version from pyproject.toml.

    Returns:
        Version string (e.g., '0.1.3')
    """
    # Try to read from pyproject.toml
    pyproject_paths = [
        Path(__file__).parent.parent.parent / "pyproject.toml",  # streamlit_app/components -> root
        Path("/app/pyproject.toml"),  # Docker container
        Path("pyproject.toml"),  # Current directory
    ]

    for pyproject_path in pyproject_paths:
        if pyproject_path.exists():
            try:
                content = pyproject_path.read_text()
                for line in content.splitlines():
                    if line.startswith("version = "):
                        # Extract version from: version = "0.1.3"
                        version = line.split("=")[1].strip().strip('"').strip("'")
                        return version
            except Exception:  # nosec B112
                continue

    return "unknown"


@lru_cache(maxsize=1)
def get_environment() -> str:
    """Detect if running in dev or prod environment.

    Returns:
        'dev', 'prod', or 'local'
    """
    # Check IMAGE_TAG environment variable (set in docker-compose)
    image_tag = os.environ.get("IMAGE_TAG", "")
    if image_tag:
        if "dev" in image_tag.lower():
            return "dev"
        return "prod"

    # Check if running in Docker
    if Path("/.dockerenv").exists() or os.environ.get("DOCKER_CONTAINER"):
        # Check for dev indicators
        log_level = os.environ.get("LOG_LEVEL", "")
        if log_level.upper() == "DEBUG":
            return "dev"
        return "prod"

    # Local development (not in Docker)
    return "local"


def get_version_badge() -> str:
    """Get version with environment badge as HTML.

    Returns:
        HTML string with version and environment badge
    """
    version = get_version()
    env = get_environment()

    # Badge colors
    badge_colors = {
        "dev": ("#ffc107", "#000"),  # yellow bg, black text
        "prod": ("#28a745", "#fff"),  # green bg, white text
        "local": ("#6c757d", "#fff"),  # gray bg, white text
    }

    bg_color, text_color = badge_colors.get(env, ("#6c757d", "#fff"))

    badge_style = (
        f"background-color: {bg_color}; "
        f"color: {text_color}; "
        "padding: 2px 6px; "
        "border-radius: 4px; "
        "font-size: 0.75em; "
        "font-weight: bold; "
        "margin-left: 8px; "
        "text-transform: uppercase;"
    )

    return f'OMRON Garmin Bridge v{version} <span style="{badge_style}">{env}</span>'


def show_version_footer() -> None:
    """Display version footer in Streamlit sidebar."""
    st.caption(
        get_version_badge(),
        unsafe_allow_html=True,
    )
