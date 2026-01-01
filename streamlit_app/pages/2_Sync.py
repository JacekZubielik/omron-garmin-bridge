"""Sync page - Manual synchronization controls."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import streamlit as st
import yaml

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.duplicate_filter import DuplicateFilter  # noqa: E402
from streamlit_app.components.icons import ICONS, load_fontawesome  # noqa: E402
from streamlit_app.components.version import show_version_footer  # noqa: E402


def load_users_config() -> list[dict[str, Any]]:
    """Load users configuration from config.yaml."""
    config_path = project_root / "config" / "config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
        users: list[dict[str, Any]] = config.get("users", [])
        return users
    return []


def main() -> None:
    """Sync page."""
    load_fontawesome()

    # Initialize database for pending counts
    db_path = project_root / "data" / "omron.db"
    db = DuplicateFilter(str(db_path))

    with st.sidebar:
        # Pending Sync Status
        st.subheader("Pending Sync")

        pending_garmin = db.get_pending_garmin()
        pending_mqtt = db.get_pending_mqtt()

        col_pg, col_pm = st.columns(2)
        with col_pg:
            if pending_garmin:
                st.markdown(
                    f"<span style='color: #ffc107;'>{ICONS['warning']} Garmin: {len(pending_garmin)}</span>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<span style='color: #28a745;'>{ICONS['check']} Garmin: 0</span>",
                    unsafe_allow_html=True,
                )
        with col_pm:
            if pending_mqtt:
                st.markdown(
                    f"<span style='color: #ffc107;'>{ICONS['warning']} MQTT: {len(pending_mqtt)}</span>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<span style='color: #28a745;'>{ICONS['check']} MQTT: 0</span>",
                    unsafe_allow_html=True,
                )

        st.markdown("---")
        show_version_footer()

    st.markdown(f"# {ICONS['sync']} Manual Sync", unsafe_allow_html=True)
    st.markdown("Synchronization with OMRON device")

    st.markdown("---")

    # Device settings
    col1, spacer, col2 = st.columns([1, 0.1, 1])

    with col1:
        st.subheader("Device Settings")
        mac_address = st.text_input(
            "MAC Address",
            value="00:5F:BF:91:9B:4B",
            help="MAC address of your OMRON device",
        )
        device_model = st.selectbox(
            "Device Model",
            options=["HEM-7361T", "HEM-7155T", "HEM-7322T", "HEM-7600T"],
            index=0,
        )

    with col2:
        st.subheader("Sync Options")

        # Load users from config
        users = load_users_config()

        if users:
            st.markdown("**Per-user options:**")
            sync_garmin_users: dict[int, bool] = {}
            sync_mqtt_users: dict[int, bool] = {}

            for user in users:
                user_name = user.get("name", f"User {user.get('omron_slot', '?')}")
                omron_slot = user.get("omron_slot", 1)
                garmin_email = user.get("garmin_email", "")
                # Read per-user enabled from config (default True)
                garmin_config_enabled = user.get("garmin_enabled", True)
                mqtt_config_enabled = user.get("mqtt_enabled", True)

                with st.container():
                    st.markdown(f"**{user_name}** (Slot {omron_slot})")
                    col_g, col_m = st.columns(2)
                    with col_g:
                        garmin_label = "Garmin" if garmin_email else "Garmin (no token)"
                        # Use config value as default, disabled if no email
                        sync_garmin_users[omron_slot] = st.checkbox(
                            garmin_label,
                            value=garmin_config_enabled and bool(garmin_email),
                            key=f"sync_garmin_{omron_slot}",
                            disabled=not garmin_email,
                        )
                    with col_m:
                        sync_mqtt_users[omron_slot] = st.checkbox(
                            "MQTT",
                            value=mqtt_config_enabled,
                            key=f"sync_mqtt_{omron_slot}",
                        )

            # Global flags based on per-user settings
            sync_garmin = any(sync_garmin_users.values())
            sync_mqtt = any(sync_mqtt_users.values())

            # Save Settings button
            if st.button("Save Settings", key="save_sync_settings", icon=":material/save:"):
                # Load current config
                config_path = project_root / "config" / "config.yaml"
                if config_path.exists():
                    with open(config_path) as f:
                        config = yaml.safe_load(f) or {}

                    # Update user settings
                    for user in config.get("users", []):
                        slot = user.get("omron_slot")
                        if slot in sync_garmin_users:
                            user["garmin_enabled"] = sync_garmin_users[slot]
                        if slot in sync_mqtt_users:
                            user["mqtt_enabled"] = sync_mqtt_users[slot]

                    # Save config
                    with open(config_path, "w") as f:
                        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

                    st.success("Settings saved!")
                else:
                    st.error("Config file not found")

        else:
            # Fallback if no users configured
            st.warning("No users configured. Configure in Settings first.")
            sync_garmin = st.checkbox("Upload to Garmin", value=True)
            sync_mqtt = st.checkbox("Publish to MQTT", value=True)
            sync_garmin_users = {}
            sync_mqtt_users = {}

    st.markdown("---")

    # Sync instructions
    st.subheader("Run Sync")

    st.error(
        "**IMPORTANT: Timing is critical!**\n\n"
        "OMRON stays in Bluetooth mode for only **~30 seconds** after pressing BT button."
    )

    st.markdown(
        """
        **Steps:**
        1. Press **BT button** on OMRON (Bluetooth icon blinks)
        2. **Immediately** click Start Sync below
        """
    )

    # Checkbox confirmation
    bt_pressed = st.checkbox(
        "I have pressed the BT button and it's blinking",
        value=False,
        key="bt_confirmation",
    )

    # Sync button
    sync_button = st.button(
        "Start Sync",
        type="primary",
        width="stretch",
        disabled=not bt_pressed,
        icon=":material/sync:",
    )

    if not bt_pressed:
        st.info("Check the box above after pressing the BT button")

    if sync_button and bt_pressed:
        progress_bar = st.progress(0, text="Connecting...")
        result_container = st.empty()

        try:
            from src.main import OmronGarminBridge, load_config

            progress_bar.progress(20, text="Loading configuration...")

            config = load_config(str(project_root / "config" / "config.yaml"))
            config["omron"]["mac_address"] = mac_address
            config["omron"]["device_model"] = device_model

            bridge = OmronGarminBridge(config)

            # Initialize Garmin and MQTT connections
            if sync_garmin:
                progress_bar.progress(30, text="Connecting to Garmin...")
                bridge._init_garmin()
            if sync_mqtt:
                progress_bar.progress(35, text="Connecting to MQTT...")
                bridge._init_mqtt()

            progress_bar.progress(40, text="Connecting to OMRON...")

            # Run async sync
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                summary = loop.run_until_complete(
                    bridge.sync(
                        garmin_enabled=sync_garmin,
                        mqtt_enabled=sync_mqtt,
                    )
                )
            finally:
                loop.close()

            progress_bar.progress(100, text="Done")

            # Check for errors
            if summary.get("errors"):
                error_msg = summary["errors"][0] if summary["errors"] else "Unknown"

                if "ATT error" in str(error_msg) or "Unlikely Error" in str(error_msg):
                    st.error(
                        "**Bluetooth Connection Lost**\n\n"
                        "Device disconnected. Press BT button and try again quickly."
                    )
                elif "not found" in str(error_msg).lower():
                    st.error(
                        "**Device Not Found**\n\n"
                        "Check: device on, BT pressed, MAC correct, in range."
                    )
                else:
                    st.error(f"**Error:** {error_msg}")

                result_container.code(f"Error: {error_msg}")
            else:
                # Success
                if summary["new_records"] > 0:
                    st.success(f"**Synced {summary['new_records']} new reading(s)!**")
                else:
                    st.info(f"**No new records** (device has {summary['device_records']} total)")

                # Summary log
                lines = [
                    f"Device:    {device_model}",
                    f"Records:   {summary['device_records']} on device",
                    f"New:       {summary['new_records']}",
                ]
                if sync_garmin and summary.get("garmin"):
                    lines.append(f"Garmin:    {summary['garmin'].get('uploaded', 0)} uploaded")
                if sync_mqtt and summary.get("mqtt"):
                    lines.append(f"MQTT:      {summary['mqtt'].get('success', 0)} published")

                result_container.code("\n".join(lines))

                # Metrics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Device", summary["device_records"])
                with col2:
                    st.metric("New", summary["new_records"])
                with col3:
                    if sync_garmin and summary.get("garmin"):
                        st.metric("Garmin", summary["garmin"].get("uploaded", 0))
                with col4:
                    if sync_mqtt and summary.get("mqtt"):
                        st.metric("MQTT", summary["mqtt"].get("success", 0))

        except FileNotFoundError:
            progress_bar.progress(100, text="Error")
            st.error("**Config not found** - create config/config.yaml")

        except Exception as e:
            progress_bar.progress(100, text="Error")
            error_str = str(e)

            if "ATT error" in error_str or "Unlikely Error" in error_str:
                st.error("**Bluetooth connection lost** - press BT and try again quickly")
            elif "not found" in error_str.lower():
                st.error(f"**Device not found** at {mac_address}")
            elif "timeout" in error_str.lower():
                st.error("**Timeout** - press BT and start sync immediately")
            else:
                st.error(f"**Failed:** {error_str}")

            result_container.code(f"Error: {error_str}")

    # CLI section
    st.markdown("---")
    with st.expander("Command Line Alternative"):
        st.markdown("Press BT button, then run:")
        st.code("pdm run python -m src.main sync", language="bash")

    # Retry Failed Uploads section
    st.markdown("---")
    st.subheader("Retry Failed Uploads")

    # Refresh pending counts (db already initialized at top)
    pending_garmin = db.get_pending_garmin()
    pending_mqtt = db.get_pending_mqtt()

    if not pending_garmin and not pending_mqtt:
        st.success("All records have been synced successfully!")
    else:
        st.info(f"**Pending:** {len(pending_garmin)} Garmin, {len(pending_mqtt)} MQTT")

        # Show pending records
        if pending_garmin:
            with st.expander(f"Pending Garmin uploads ({len(pending_garmin)})"):
                for r in pending_garmin[:10]:  # Show max 10
                    ts = r["timestamp"][:16].replace("T", " ")
                    st.text(f"{ts} | {r['systolic']}/{r['diastolic']} | {r['pulse']} bpm")
                if len(pending_garmin) > 10:
                    st.caption(f"... and {len(pending_garmin) - 10} more")

        if pending_mqtt:
            with st.expander(f"Pending MQTT publishes ({len(pending_mqtt)})"):
                for r in pending_mqtt[:10]:  # Show max 10
                    ts = r["timestamp"][:16].replace("T", " ")
                    st.text(f"{ts} | {r['systolic']}/{r['diastolic']} | {r['pulse']} bpm")
                if len(pending_mqtt) > 10:
                    st.caption(f"... and {len(pending_mqtt) - 10} more")

        col_retry_g, col_retry_m = st.columns(2)

        with col_retry_g:
            retry_garmin_btn = st.button(
                f"Retry Garmin ({len(pending_garmin)})",
                disabled=not pending_garmin,
                type="primary" if pending_garmin else "secondary",
                key="retry_garmin",
                icon=":material/cloud_upload:",
            )

        with col_retry_m:
            retry_mqtt_btn = st.button(
                f"Retry MQTT ({len(pending_mqtt)})",
                disabled=not pending_mqtt,
                type="primary" if pending_mqtt else "secondary",
                key="retry_mqtt",
                icon=":material/wifi:",
            )

        # Handle retry Garmin
        if retry_garmin_btn and pending_garmin:
            with st.spinner("Retrying Garmin uploads..."):
                try:
                    from src.main import OmronGarminBridge, load_config

                    config = load_config(str(project_root / "config" / "config.yaml"))
                    bridge = OmronGarminBridge(config)

                    if bridge._init_garmin():
                        uploaded, skipped, failed = bridge.retry_pending_garmin()
                        bridge.cleanup()

                        if uploaded > 0 or skipped > 0:
                            st.success(
                                f"Garmin: {uploaded} uploaded, {skipped} skipped (duplicates)"
                            )
                        if failed > 0:
                            st.warning(f"Garmin: {failed} failed")
                        if uploaded == 0 and skipped == 0 and failed == 0:
                            st.info("No pending records")

                        st.rerun()
                    else:
                        st.error("Failed to connect to Garmin")
                except Exception as e:
                    st.error(f"Error: {e}")

        # Handle retry MQTT
        if retry_mqtt_btn and pending_mqtt:
            with st.spinner("Retrying MQTT publishes..."):
                try:
                    from src.main import OmronGarminBridge, load_config

                    config = load_config(str(project_root / "config" / "config.yaml"))
                    bridge = OmronGarminBridge(config)

                    if bridge._init_mqtt():
                        success, failed = bridge.retry_pending_mqtt()
                        bridge.cleanup()

                        if success > 0:
                            st.success(f"MQTT: {success} published")
                        if failed > 0:
                            st.warning(f"MQTT: {failed} failed")
                        if success == 0 and failed == 0:
                            st.info("No pending records")

                        st.rerun()
                    else:
                        st.error("Failed to connect to MQTT broker")
                except Exception as e:
                    st.error(f"Error: {e}")


if __name__ == "__main__":
    main()
