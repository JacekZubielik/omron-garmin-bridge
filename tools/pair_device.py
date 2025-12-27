#!/usr/bin/env python3
"""Pair with OMRON blood pressure monitor.

This script performs one-time pairing with an OMRON device.
After successful pairing, subsequent connections don't require pairing.

Usage:
    pdm run python tools/pair_device.py
    pdm run python tools/pair_device.py --mac 00:5F:BF:91:9B:4B

Before running:
    1. Hold Bluetooth button on OMRON for 3+ seconds until 'P' blinks
    2. Run this script
    3. If prompted in bluetoothctl (another terminal), type 'yes'
"""

import argparse
import asyncio
import logging
import sys

# Add src to path
sys.path.insert(0, ".")

from src.omron_ble.client import OmronBLEClient


async def pair_device(
    mac_address: str | None = None,
    model: str = "HEM-7361T",
    scan_timeout: float = 15.0,
    skip_os_pair: bool = False,
) -> bool:
    """Pair with OMRON device."""
    print(f"\n{'=' * 70}")
    print("OMRON Device Pairing")
    print(f"{'=' * 70}")
    print()
    print("IMPORTANT: Before continuing, make sure:")
    print("  1. Bluetooth agent is running (in another terminal run):")
    print("     bluetoothctl")
    print("     > power on")
    print("     > pairable on")
    print("     > agent on")
    print("     > default-agent")
    print("     (leave this terminal open!)")
    print()
    print("  2. Device shows blinking 'P' (hold BT button for 3+ seconds)")
    print("  3. If 'P' is not blinking, reset pairing on device first")
    print("     (hold BT button 10+ seconds)")
    print()

    if mac_address:
        print(f"Target device: {mac_address}")
    else:
        print("No MAC specified - will scan for OMRON devices")
    print()

    input("Press ENTER when device shows blinking 'P'...")
    print()

    client = OmronBLEClient(model, mac_address)

    try:
        print(f"Scanning for device (timeout: {scan_timeout}s)...")
        await client.connect(pairing_mode=True, scan_timeout=scan_timeout)
        print(f"Connected to {client.mac_address}")
        print()

        print("Sending pairing key to device...")
        print()
        print("NOTE: If a pairing prompt appears in another terminal")
        print("      (bluetoothctl), type 'yes' to confirm.")
        print()

        await client.pair(skip_os_pair=skip_os_pair)

        print()
        print(f"{'=' * 70}")
        print("SUCCESS! Device paired.")
        print()
        print("The device should now show a square symbol instead of 'P'.")
        print()
        print("You can now read data without pairing:")
        print(f"  pdm run python tools/read_device.py --mac {client.mac_address}")
        print(f"  pdm run python tools/sync_records.py --mac {client.mac_address}")
        print(f"{'=' * 70}")
        print()

        return True

    except Exception as e:
        print()
        print(f"{'=' * 70}")
        print(f"PAIRING FAILED: {e}")
        print()
        print("Troubleshooting:")
        print("  1. Make sure device shows blinking 'P'")
        print("  2. Hold BT button for 10+ seconds to reset pairing")
        print("  3. Remove old pairing: bluetoothctl remove <MAC>")
        print("  4. Restart Bluetooth: sudo systemctl restart bluetooth")
        print("  5. Try again with --debug flag for more info")
        print(f"{'=' * 70}")
        print()
        return False

    finally:
        await client.disconnect()


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Pair with OMRON blood pressure monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Before pairing:
  1. Reset device pairing: hold BT button 10+ seconds
  2. Enter pairing mode: hold BT button until 'P' blinks
  3. Run this script

Examples:
  pdm run python tools/pair_device.py
  pdm run python tools/pair_device.py --mac 00:5F:BF:91:9B:4B
  pdm run python tools/pair_device.py --debug
        """,
    )
    parser.add_argument(
        "--mac",
        "-m",
        type=str,
        default=None,
        help="Device MAC address (optional - will scan if not provided)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="HEM-7361T",
        help="Device model (default: HEM-7361T)",
    )
    parser.add_argument(
        "--timeout",
        "-t",
        type=float,
        default=15.0,
        help="Scan timeout in seconds (default: 15)",
    )
    parser.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--skip-os-pair",
        action="store_true",
        help="Skip OS-level Bluetooth pairing (try OMRON protocol directly)",
    )

    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
    else:
        logging.basicConfig(level=logging.WARNING)

    try:
        success = asyncio.run(
            pair_device(
                mac_address=args.mac,
                model=args.model,
                scan_timeout=args.timeout,
                skip_os_pair=args.skip_os_pair,
            )
        )
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(1)


if __name__ == "__main__":
    main()
