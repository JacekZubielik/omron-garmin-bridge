"""Settings page - Configuration management."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st
import yaml

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

st.set_page_config(page_title="Settings", page_icon="⚙️", layout="wide")


def main() -> None:
    """Settings page."""
    st.title("⚙️ Settings")
    st.markdown("Configure OMRON Garmin Bridge")

    config_path = project_root / "config" / "config.yaml"
    example_path = project_root / "config" / "config.yaml.example"

    # Load current config
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
        st.success("Configuration loaded from config/config.yaml")
    elif example_path.exists():
        with open(example_path) as f:
            config = yaml.safe_load(f) or {}
        st.warning("Using example configuration. Save to create config.yaml")
    else:
        config = {}
        st.error("No configuration file found!")

    st.markdown("---")

    # OMRON Device settings
    st.subheader("OMRON Device")
    col1, col2 = st.columns(2)

    omron_config = config.get("omron", {})
    with col1:
        device_model = st.selectbox(
            "Device Model",
            options=["HEM-7361T", "HEM-7155T", "HEM-7322T", "HEM-7600T", "HEM-7530T"],
            index=["HEM-7361T", "HEM-7155T", "HEM-7322T", "HEM-7600T", "HEM-7530T"].index(
                omron_config.get("device_model", "HEM-7361T")
            ),
        )
        mac_address = st.text_input(
            "MAC Address",
            value=omron_config.get("mac_address", ""),
            help="Leave empty to scan for devices",
        )

    with col2:
        poll_interval = st.number_input(
            "Poll Interval (minutes)",
            min_value=0,
            max_value=1440,
            value=omron_config.get("poll_interval_minutes", 60),
            help="0 = manual only",
        )
        read_mode = st.selectbox(
            "Read Mode",
            options=["new_only", "all"],
            index=0 if omron_config.get("read_mode", "new_only") == "new_only" else 1,
        )
        sync_time = st.checkbox(
            "Sync Device Clock",
            value=omron_config.get("sync_time", True),
        )

    st.markdown("---")

    # Garmin settings
    st.subheader("Garmin Connect")
    garmin_config = config.get("garmin", {})

    col1, col2 = st.columns(2)
    with col1:
        garmin_enabled = st.checkbox(
            "Enable Garmin Upload",
            value=garmin_config.get("enabled", True),
        )
    with col2:
        tokens_path = st.text_input(
            "Tokens Path",
            value=garmin_config.get("tokens_path", "./data/tokens"),
        )

    # Check if tokens exist
    tokens_dir = project_root / "data" / "tokens"
    if tokens_dir.exists() and list(tokens_dir.glob("*.json")):
        st.success("✅ Garmin tokens found")
    else:
        st.warning("⚠️ Garmin tokens not found. Run: `pdm run python tools/import_tokens.py`")

    st.markdown("---")

    # MQTT settings
    st.subheader("MQTT")
    mqtt_config = config.get("mqtt", {})

    col1, col2, col3 = st.columns(3)
    with col1:
        mqtt_enabled = st.checkbox(
            "Enable MQTT",
            value=mqtt_config.get("enabled", True),
        )
        mqtt_host = st.text_input(
            "MQTT Host",
            value=mqtt_config.get("host", "192.168.40.19"),
        )
    with col2:
        mqtt_port = st.number_input(
            "MQTT Port",
            min_value=1,
            max_value=65535,
            value=mqtt_config.get("port", 1883),
        )
        mqtt_topic = st.text_input(
            "Base Topic",
            value=mqtt_config.get("base_topic", "omron/blood_pressure"),
        )
    with col3:
        mqtt_username = st.text_input(
            "Username (optional)",
            value=mqtt_config.get("username", ""),
        )
        mqtt_password = st.text_input(
            "Password (optional)",
            value=mqtt_config.get("password", ""),
            type="password",
        )

    st.markdown("---")

    # Users configuration
    st.subheader("User Mapping")
    st.markdown("Map OMRON device slots to Garmin accounts")

    users_config = config.get("users", [{"name": "User1", "omron_slot": 1, "garmin_email": ""}])

    for i, user in enumerate(users_config[:2]):  # Max 2 users
        col1, col2, col3 = st.columns(3)
        with col1:
            st.text_input(
                f"User {i + 1} Name", value=user.get("name", f"User{i + 1}"), key=f"user_{i}_name"
            )
        with col2:
            st.selectbox(
                "OMRON Slot",
                options=[1, 2],
                index=user.get("omron_slot", i + 1) - 1,
                key=f"user_{i}_slot",
            )
        with col3:
            st.text_input("Garmin Email", value=user.get("garmin_email", ""), key=f"user_{i}_email")

    st.markdown("---")

    # Save configuration
    if st.button("💾 Save Configuration", type="primary", width="stretch"):
        # Build new config
        new_config = {
            "omron": {
                "device_model": device_model,
                "mac_address": mac_address if mac_address else None,
                "poll_interval_minutes": poll_interval,
                "read_mode": read_mode,
                "sync_time": sync_time,
            },
            "users": [
                {
                    "name": st.session_state.get(f"user_{i}_name", f"User{i + 1}"),
                    "omron_slot": st.session_state.get(f"user_{i}_slot", i + 1),
                    "garmin_email": st.session_state.get(f"user_{i}_email", ""),
                }
                for i in range(2)
                if st.session_state.get(f"user_{i}_email")
            ],
            "garmin": {
                "enabled": garmin_enabled,
                "tokens_path": tokens_path,
            },
            "mqtt": {
                "enabled": mqtt_enabled,
                "host": mqtt_host,
                "port": mqtt_port,
                "base_topic": mqtt_topic,
            },
            "deduplication": {
                "database_path": "./data/omron.db",
            },
            "logging": {
                "level": "INFO",
                "file": "./logs/omron-bridge.log",
            },
        }

        if mqtt_username:
            new_config["mqtt"]["username"] = mqtt_username  # type: ignore[index]
        if mqtt_password:
            new_config["mqtt"]["password"] = mqtt_password  # type: ignore[index]

        # Save to file
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            yaml.dump(new_config, f, default_flow_style=False, sort_keys=False)

        st.success("Configuration saved!")
        st.rerun()

    # Show current config
    with st.expander("View Current Configuration"):
        st.code(yaml.dump(config, default_flow_style=False), language="yaml")


if __name__ == "__main__":
    main()
