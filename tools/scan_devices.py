#!/usr/bin/env python3
"""Scan for OMRON BLE devices.

Usage:
    pdm run python tools/scan_devices.py
    pdm run python tools/scan_devices.py --timeout 20
    pdm run python tools/scan_devices.py --all  # Show all BLE devices
"""

import argparse
import asyncio
import logging
import sys

# Add src to path
sys.path.insert(0, ".")

from src.omron_ble.client import OmronBLEClient


async def scan_devices(timeout: float = 10.0, show_all: bool = False) -> None:
    """Scan for BLE devices."""
    print(f"\n{'=' * 60}")
    print(f"Scanning for {'all BLE' if show_all else 'OMRON'} devices ({timeout}s)...")
    print(f"{'=' * 60}\n")

    if show_all:
        devices = await OmronBLEClient.scan_devices(timeout)
    else:
        devices = await OmronBLEClient.find_omron_devices(timeout)

    if not devices:
        print("No devices found.")
        print("\nTroubleshooting tips:")
        print("  1. Make sure Bluetooth is enabled: bluetoothctl show")
        print("  2. For OMRON: Press the Bluetooth button on the device")
        print("  3. Try --all to see all BLE devices")
        print("  4. Increase timeout: --timeout 30")
        return

    print(f"Found {len(devices)} device(s):\n")
    print(f"{'MAC Address':<20} {'Name':<30}")
    print("-" * 50)

    for device in devices:
        name = device.name or "(unknown)"
        print(f"{device.address:<20} {name:<30}")

    print(f"\n{'=' * 60}")
    print("Next steps:")
    print("  1. Note the MAC address of your OMRON device")
    print("  2. Update config/config.yaml with the MAC address")
    print("  3. Run: pdm run python tools/read_device.py")
    print(f"{'=' * 60}\n")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Scan for OMRON BLE devices",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  pdm run python tools/scan_devices.py
  pdm run python tools/scan_devices.py --timeout 20
  pdm run python tools/scan_devices.py --all
        """,
    )
    parser.add_argument(
        "--timeout",
        "-t",
        type=float,
        default=10.0,
        help="Scan timeout in seconds (default: 10)",
    )
    parser.add_argument(
        "--all",
        "-a",
        action="store_true",
        help="Show all BLE devices, not just OMRON",
    )
    parser.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO, format="%(message)s")

    try:
        asyncio.run(scan_devices(args.timeout, args.all))
    except KeyboardInterrupt:
        print("\nScan cancelled.")
    except Exception as e:
        print(f"\nError: {e}")
        if args.debug:
            raise
        sys.exit(1)


if __name__ == "__main__":
    main()
