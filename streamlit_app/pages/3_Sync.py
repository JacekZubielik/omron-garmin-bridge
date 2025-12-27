"""Sync page - Manual synchronization controls."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import streamlit as st

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

st.set_page_config(page_title="Sync", page_icon="🔄", layout="wide")


def main() -> None:
    """Sync page."""
    st.title("🔄 Manual Sync")
    st.markdown("Synchronization with OMRON device")

    st.markdown("---")

    # Device settings
    col1, col2 = st.columns(2)

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
        sync_garmin = st.checkbox("Upload to Garmin", value=True)
        sync_mqtt = st.checkbox("Publish to MQTT", value=True)
        dry_run = st.checkbox("Dry run (no changes)", value=False)

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
        "🚀 Start Sync",
        type="primary",
        width="stretch",
        disabled=not bt_pressed,
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
                        dry_run=dry_run,
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


if __name__ == "__main__":
    main()
