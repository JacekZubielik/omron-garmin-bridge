"""Settings page - Configuration management."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st
import yaml

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.garmin_uploader import get_token_status, list_available_tokens  # noqa: E402
from streamlit_app.components.icons import ICONS, load_fontawesome  # noqa: E402
from streamlit_app.components.version import show_version_footer  # noqa: E402


def main() -> None:
    """Settings page."""
    load_fontawesome()

    # Get paired/trusted devices from bluetoothctl
    def get_paired_devices() -> dict[str, dict[str, bool]]:
        """Get paired and trusted status from bluetoothctl."""
        import subprocess  # nosec B404

        result: dict[str, dict[str, bool]] = {}
        try:
            # Get paired devices
            paired_output = subprocess.run(
                ["bluetoothctl", "devices", "Paired"],  # nosec B603 B607
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in paired_output.stdout.strip().split("\n"):
                if line.startswith("Device "):
                    parts = line.split(" ", 2)
                    if len(parts) >= 2:
                        mac = parts[1]
                        result[mac] = {"paired": True, "trusted": False}

            # Check trusted status for each paired device
            for mac in result:
                info_output = subprocess.run(
                    ["bluetoothctl", "info", mac],  # nosec B603 B607
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if "Trusted: yes" in info_output.stdout:
                    result[mac]["trusted"] = True
        except Exception:  # nosec B110
            pass
        return result

    paired_status = get_paired_devices()

    with st.sidebar:
        st.subheader("Bluetooth Pairing")
        st.markdown("**Paired devices**")
        omron_paired = {k: v for k, v in paired_status.items() if k.startswith("00:5F:BF")}
        if omron_paired:
            for mac, status in omron_paired.items():
                paired_icon = ICONS["check"] if status["paired"] else ICONS["xmark"]
                trusted_icon = ICONS["lock"] if status["trusted"] else ICONS["unlock"]
                st.markdown(
                    f"`{mac}`<br>Paired: {paired_icon} Trusted: {trusted_icon}",
                    unsafe_allow_html=True,
                )
        else:
            st.info("No paired OMRON devices")
        st.markdown("---")
        show_version_footer()

    st.markdown(f"# {ICONS['settings']} Settings", unsafe_allow_html=True)
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

    # Scan/Pair section
    st.markdown("---")
    st.subheader("Bluetooth Pairing")

    # Initialize session state for scanned devices
    if "scanned_devices" not in st.session_state:
        st.session_state.scanned_devices = []

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Scan for devices**")
        if st.button("Scan for OMRON devices", key="scan_btn", icon=":material/search:"):
            with st.spinner("Scanning for BLE devices (10s)..."):
                try:
                    import asyncio

                    from src.omron_ble.client import OmronBLEClient

                    async def do_scan() -> list[dict[str, str]]:
                        devices = await OmronBLEClient.scan_devices(timeout=10)
                        omron_devices = [
                            d
                            for d in devices
                            if d.name and ("BLESmart" in d.name or "OMRON" in d.name)
                        ]
                        return [
                            {"name": d.name or "Unknown", "mac": d.address} for d in omron_devices
                        ]

                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        found_devices = loop.run_until_complete(do_scan())
                    finally:
                        loop.close()

                    st.session_state.scanned_devices = found_devices

                    if found_devices:
                        st.success(f"Found {len(found_devices)} device(s)")
                    else:
                        st.warning("No OMRON devices found. Press BT button on device first.")
                except Exception as e:
                    st.error(f"Scan failed: {e}")

        # Show scanned devices
        if st.session_state.scanned_devices:
            for idx, dev in enumerate(st.session_state.scanned_devices):
                status = paired_status.get(dev["mac"], {})
                is_paired = status.get("paired", False)
                is_trusted = status.get("trusted", False)

                paired_icon = ICONS["check"] if is_paired else ICONS["xmark"]
                trusted_icon = ICONS["lock"] if is_trusted else ICONS["unlock"]

                st.markdown(
                    f"**{dev['name']}**  \n"
                    f"`{dev['mac']}`  \n"
                    f"Paired: {paired_icon} | Trusted: {trusted_icon}",
                    unsafe_allow_html=True,
                )

                if is_paired and st.button(
                    "Unpair", key=f"unpair_{idx}", icon=":material/link_off:"
                ):
                    import subprocess  # nosec B404

                    try:
                        subprocess.run(
                            ["bluetoothctl", "remove", dev["mac"]],  # nosec B603 B607
                            capture_output=True,
                            timeout=10,
                        )
                        st.success(f"Unpaired {dev['mac']}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Unpair failed: {e}")

    with col2:
        st.markdown("**Pair device**")

        # Build options from scanned devices
        device_options = [""] + [
            f"{d['mac']} ({d['name']})" for d in st.session_state.scanned_devices
        ]
        if mac_address and not any(mac_address in opt for opt in device_options):
            device_options.append(f"{mac_address} (from config)")

        selected_device = st.selectbox(
            "Select device to pair",
            options=device_options,
            key="pair_select",
            help="Scan for devices first, or select from config",
        )

        # Extract MAC from selection
        pair_mac = selected_device.split(" ")[0] if selected_device else ""

        if st.button("Pair Device", key="pair_btn", disabled=not pair_mac, icon=":material/link:"):
            st.info(
                "**Pairing instructions:**\n\n"
                "1. Hold BT button on OMRON until 'P' appears\n"
                "2. Wait for pairing to complete"
            )
            with st.spinner("Pairing..."):
                try:
                    import asyncio

                    from src.omron_ble.client import OmronBLEClient

                    async def do_pair(mac: str, model: str) -> bool:
                        client = OmronBLEClient(device_model=model, mac_address=mac)
                        return await client.pair()

                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        success = loop.run_until_complete(do_pair(pair_mac, device_model))
                    finally:
                        loop.close()

                    if success:
                        st.success(f"Successfully paired with {pair_mac}")
                        st.rerun()
                    else:
                        st.error("Pairing failed. Try again or use CLI.")
                except Exception as e:
                    st.error(f"Pairing error: {e}")

    with st.expander("CLI Pairing Commands"):
        st.code(
            """# Scan for devices
pdm run python tools/scan_devices.py

# Pair with device (hold BT button until 'P' appears first!)
pdm run python tools/pair_device.py --mac 00:5F:BF:91:9B:4B

# If pairing fails, reset Bluetooth cache:
bluetoothctl remove 00:5F:BF:91:9B:4B
sudo rm -rf /var/lib/bluetooth/<ADAPTER_MAC>/<OMRON_MAC>
sudo systemctl restart bluetooth""",
            language="bash",
        )

    st.markdown("---")

    # Garmin settings
    st.subheader("Garmin Connect")
    garmin_config = config.get("garmin", {})

    tokens_path = st.text_input(
        "Tokens Path",
        value=garmin_config.get("tokens_path", "./data/tokens"),
    )

    # Token status per user
    tokens_dir = project_root / "data" / "tokens"
    users_config = config.get("users", [])

    st.markdown("**Account Status**")

    # Helper function to generate tokens
    def generate_garmin_token(email: str, password: str, tokens_dir: Path) -> tuple[bool, str]:
        """Generate Garmin OAuth tokens.

        Returns:
            Tuple of (success, message)
        """
        from garminconnect import Garmin, GarminConnectAuthenticationError

        try:
            # Create user-specific token directory
            user_folder = email.replace("@", "_at_")
            user_tokens_dir = tokens_dir / user_folder
            user_tokens_dir.mkdir(parents=True, exist_ok=True)

            # Login and save tokens
            garmin = Garmin(email, password)
            garmin.login()
            garmin.garth.dump(str(user_tokens_dir))

            # Get display name
            try:
                display_name = garmin.display_name
                return True, f"Token generated for {display_name}"
            except Exception:
                return True, f"Token generated for {email}"

        except GarminConnectAuthenticationError as e:
            return False, f"Authentication failed: {e}"
        except Exception as e:
            return False, f"Error: {e}"

    if not users_config:
        st.info("Configure users in User Mapping section below first.")
    else:
        for idx, user in enumerate(users_config):
            user_name = user.get("name", "Unknown")
            garmin_email = user.get("garmin_email", "")
            omron_slot = user.get("omron_slot", "?")

            if not garmin_email:
                st.warning(
                    f"**User {omron_slot} ({user_name}):** No Garmin email configured",
                    icon=":material/warning:",
                )
            else:
                # Check token status
                token_status = get_token_status(tokens_dir, garmin_email)

                col_status, col_action = st.columns([4, 1])

                with col_status:
                    if token_status["valid"]:
                        display_name = token_status.get("display_name") or garmin_email
                        st.success(
                            f"**User {omron_slot} ({user_name}):** {display_name}",
                            icon=":material/check_circle:",
                        )
                    elif token_status["exists"]:
                        st.error(
                            f"**User {omron_slot} ({user_name}):** Token expired - {garmin_email}",
                            icon=":material/error:",
                        )
                    else:
                        st.warning(
                            f"**User {omron_slot} ({user_name}):** No token - {garmin_email}",
                            icon=":material/warning:",
                        )

                with col_action:
                    # Generate/Refresh token button
                    button_label = "Refresh" if token_status["exists"] else "Generate"
                    if st.button(
                        button_label,
                        key=f"gen_token_{idx}",
                        icon=":material/refresh:" if token_status["exists"] else ":material/key:",
                    ):
                        st.session_state[f"show_token_form_{idx}"] = True

                # Show token generation form if requested
                if st.session_state.get(f"show_token_form_{idx}", False):
                    with st.container():
                        st.markdown(f"**Generate token for {garmin_email}**")
                        password = st.text_input(
                            "Garmin Password",
                            type="password",
                            key=f"garmin_pass_{idx}",
                            help="Your Garmin Connect password (not stored)",
                        )

                        col_submit, col_cancel = st.columns(2)
                        with col_submit:
                            if st.button(
                                "Login & Generate", key=f"submit_token_{idx}", type="primary"
                            ):
                                if password:
                                    with st.spinner("Authenticating with Garmin..."):
                                        success, message = generate_garmin_token(
                                            garmin_email, password, tokens_dir
                                        )
                                    if success:
                                        st.success(message)
                                        st.session_state[f"show_token_form_{idx}"] = False
                                        st.rerun()
                                    else:
                                        st.error(message)
                                else:
                                    st.error("Password required")

                        with col_cancel:
                            if st.button("Cancel", key=f"cancel_token_{idx}"):
                                st.session_state[f"show_token_form_{idx}"] = False
                                st.rerun()

    # Show all available tokens
    with st.expander("All Available Tokens"):
        available_tokens = list_available_tokens(tokens_dir)
        if available_tokens:
            for token in available_tokens:
                status_icon = ICONS["check"] if token["valid"] else ICONS["xmark"]
                display = token.get("display_name") or token["email"]
                st.markdown(
                    f"{status_icon} **{display}** ({token['email']})",
                    unsafe_allow_html=True,
                )
                if token.get("error"):
                    st.caption(f"Error: {token['error']}")
        else:
            st.info("No tokens found. Generate tokens using the CLI command above.")

    with st.expander("CLI Token Commands"):
        st.code(
            """# Generate token for single user
pdm run python tools/import_tokens.py --email user@example.com

# Generate tokens for multiple users
pdm run python tools/import_tokens.py --email user1@example.com --email user2@example.com

# Interactive mode (prompts for email)
pdm run python tools/import_tokens.py""",
            language="bash",
        )

    st.markdown("---")

    # MQTT settings
    st.subheader("MQTT")
    mqtt_config = config.get("mqtt", {})

    # Test MQTT connection
    def test_mqtt_connection(host: str, port: int) -> bool:
        """Test MQTT broker connection."""
        try:
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False

    mqtt_host_val = mqtt_config.get("host", "192.168.40.19")
    mqtt_port_val = mqtt_config.get("port", 1883)
    mqtt_connected = test_mqtt_connection(mqtt_host_val, mqtt_port_val)

    # Show connection status (same style as Garmin Account Status)
    st.markdown("**Broker Status**")
    if mqtt_connected:
        st.success(
            f"**Connected:** {mqtt_host_val}:{mqtt_port_val}",
            icon=":material/check_circle:",
        )
    else:
        st.error(
            f"**Unreachable:** {mqtt_host_val}:{mqtt_port_val}",
            icon=":material/error:",
        )

    col1, col2, col3 = st.columns(3)
    with col1:
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

    # Use users_config from earlier (already loaded for Garmin section)
    if not users_config:
        users_config = [{"name": "User1", "omron_slot": 1, "garmin_email": ""}]

    for i in range(2):  # Max 2 users (OMRON slots 1 and 2)
        user = users_config[i] if i < len(users_config) else {}
        col1, col2 = st.columns(2)
        with col1:
            st.text_input(
                f"User {i + 1} - Name",
                value=user.get("name", ""),
                key=f"user_{i}_name",
                help=f"Name for user in OMRON slot {i + 1}",
            )
        with col2:
            st.text_input(
                "Garmin Email",
                value=user.get("garmin_email", ""),
                key=f"user_{i}_email",
                help=f"Garmin account email for OMRON slot {i + 1}",
            )

    st.markdown("---")

    # Save configuration
    if st.button("Save Configuration", type="primary", icon=":material/save:", width="stretch"):
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
                    "name": st.session_state.get(f"user_{i}_name", ""),
                    "omron_slot": i + 1,
                    "garmin_email": st.session_state.get(f"user_{i}_email", ""),
                }
                for i in range(2)
                if st.session_state.get(f"user_{i}_email")
            ],
            "garmin": {
                "tokens_path": tokens_path,
            },
            "mqtt": {
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

    # Show current config (read fresh from file)
    with st.expander("View Current Configuration"):
        if config_path.exists():
            with open(config_path) as f:
                current_config = f.read()
            st.code(current_config, language="yaml")
        else:
            st.warning("No config.yaml file found")


if __name__ == "__main__":
    main()
