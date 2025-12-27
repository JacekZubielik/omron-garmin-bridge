#!/usr/bin/env python3
"""Read blood pressure records from OMRON device.

Usage:
    pdm run python tools/read_device.py
    pdm run python tools/read_device.py --mac 00:5F:BF:91:9B:4B
    pdm run python tools/read_device.py --new-only
"""

import argparse
import asyncio
import logging
import sys

# Add src to path
sys.path.insert(0, ".")

from src.models import BloodPressureReading
from src.omron_ble.client import OmronBLEClient


def print_reading(reading: BloodPressureReading, index: int) -> None:
    """Print a single reading in formatted way."""
    flags = []
    if reading.irregular_heartbeat:
        flags.append("IHB")
    if reading.body_movement:
        flags.append("MOV")
    flags_str = f" [{', '.join(flags)}]" if flags else ""

    print(
        f"  {index:3}. {reading.timestamp.strftime('%Y-%m-%d %H:%M')} | "
        f"{reading.systolic:3}/{reading.diastolic:3} mmHg | "
        f"{reading.pulse:3} bpm | "
        f"User {reading.user_slot} | "
        f"{reading.category}{flags_str}"
    )


async def read_device(
    mac_address: str | None = None,
    model: str = "HEM-7361T",
    only_new: bool = False,
    sync_time: bool = False,
) -> None:
    """Read records from OMRON device."""
    print(f"\n{'=' * 70}")
    print(f"Reading from OMRON {model}")
    if mac_address:
        print(f"MAC Address: {mac_address}")
    print(f"Mode: {'New records only' if only_new else 'All records'}")
    print(f"{'=' * 70}\n")

    client = OmronBLEClient(model, mac_address)

    try:
        print("Connecting...")
        await client.connect()
        print("Connected!\n")

        print("Reading records...")
        records_by_user = await client.read_records(
            only_new=only_new,
            sync_time=sync_time,
        )

        total_records = sum(len(r) for r in records_by_user)

        if total_records == 0:
            print("No records found on device.")
        else:
            print(f"Found {total_records} record(s):\n")

            for user_slot, records in enumerate(records_by_user, start=1):
                if records:
                    print(f"--- User {user_slot} ({len(records)} records) ---")
                    for i, reading in enumerate(records, start=1):
                        print_reading(reading, i)
                    print()

            # Summary statistics
            all_records = [r for user_records in records_by_user for r in user_records]
            if all_records:
                print("-" * 70)
                print("Summary:")

                avg_sys = sum(r.systolic for r in all_records) / len(all_records)
                avg_dia = sum(r.diastolic for r in all_records) / len(all_records)
                avg_pulse = sum(r.pulse for r in all_records) / len(all_records)

                print(f"  Average: {avg_sys:.0f}/{avg_dia:.0f} mmHg, {avg_pulse:.0f} bpm")
                print(f"  Oldest:  {min(r.timestamp for r in all_records)}")
                print(f"  Newest:  {max(r.timestamp for r in all_records)}")

    except Exception as e:
        print(f"\nError: {e}")
        raise
    finally:
        print("\nDisconnecting...")
        await client.disconnect()
        print("Done.")

    print(f"\n{'=' * 70}")
    print("Next steps:")
    print("  1. To save to database: pdm run python tools/sync_records.py")
    print("  2. To upload to Garmin: pdm run python -m src.main sync")
    print(f"{'=' * 70}\n")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Read blood pressure records from OMRON device",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  pdm run python tools/read_device.py
  pdm run python tools/read_device.py --mac 00:5F:BF:91:9B:4B
  pdm run python tools/read_device.py --new-only
  pdm run python tools/read_device.py --sync-time
        """,
    )
    parser.add_argument(
        "--mac",
        "-m",
        type=str,
        default="00:5F:BF:91:9B:4B",
        help="Device MAC address (default: 00:5F:BF:91:9B:4B)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="HEM-7361T",
        help="Device model (default: HEM-7361T)",
    )
    parser.add_argument(
        "--new-only",
        "-n",
        action="store_true",
        help="Read only new (unread) records",
    )
    parser.add_argument(
        "--sync-time",
        "-s",
        action="store_true",
        help="Sync device time with system time",
    )
    parser.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Enable debug logging",
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
        asyncio.run(
            read_device(
                mac_address=args.mac,
                model=args.model,
                only_new=args.new_only,
                sync_time=args.sync_time,
            )
        )
    except KeyboardInterrupt:
        print("\nCancelled.")
    except Exception as e:
        print(f"\nFailed: {e}")
        if args.debug:
            raise
        sys.exit(1)


if __name__ == "__main__":
    main()
