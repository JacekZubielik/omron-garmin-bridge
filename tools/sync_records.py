#!/usr/bin/env python3
"""Sync blood pressure records from OMRON to local database.

This script:
1. Reads records from OMRON device
2. Filters out duplicates (already in database)
3. Saves new records to SQLite database

Usage:
    pdm run python tools/sync_records.py
    pdm run python tools/sync_records.py --mac 00:5F:BF:91:9B:4B
    pdm run python tools/sync_records.py --dry-run
"""

import argparse
import asyncio
import logging
import sys

# Add src to path
sys.path.insert(0, ".")

from src.duplicate_filter import DuplicateFilter
from src.models import BloodPressureReading
from src.omron_ble.client import OmronBLEClient


def print_reading(reading: BloodPressureReading, index: int, status: str = "") -> None:
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
        f"{reading.category}{flags_str} {status}"
    )


async def sync_records(
    mac_address: str | None = None,
    model: str = "HEM-7361T",
    db_path: str = "data/omron.db",
    dry_run: bool = False,
) -> None:
    """Sync records from OMRON device to database."""
    print(f"\n{'=' * 70}")
    print(f"Syncing records from OMRON {model}")
    if mac_address:
        print(f"MAC Address: {mac_address}")
    print(f"Database: {db_path}")
    if dry_run:
        print("Mode: DRY RUN (no changes will be saved)")
    print(f"{'=' * 70}\n")

    # Initialize duplicate filter
    dup_filter = DuplicateFilter(db_path)

    # Show current database stats
    stats = dup_filter.get_statistics()
    print(f"Database status: {stats['total_records']} records stored")
    if stats["last_record"]:
        print(f"Last record: {stats['last_record']}")
    print()

    # Connect to device
    client = OmronBLEClient(model, mac_address)

    try:
        print("Connecting to device...")
        await client.connect()
        print("Connected!\n")

        print("Reading records from device...")
        records = await client.read_all_records_flat(only_new=False, sync_time=False)
        print(f"Read {len(records)} records from device.\n")

        if not records:
            print("No records on device.")
            return

        # Filter new records
        new_records = dup_filter.filter_new_records(records)
        duplicate_count = len(records) - len(new_records)

        print(f"New records: {len(new_records)}")
        print(f"Duplicates (already in DB): {duplicate_count}\n")

        if not new_records:
            print("All records already in database. Nothing to sync.")
            return

        # Show new records
        print("New records to save:")
        for i, reading in enumerate(new_records, start=1):
            print_reading(reading, i)

        print()

        if dry_run:
            print("DRY RUN - No changes saved.")
        else:
            # Save new records
            print("Saving to database...")
            for reading in new_records:
                dup_filter.mark_as_uploaded(reading, garmin=False, mqtt=False)
            print(f"Saved {len(new_records)} new records.\n")

            # Show updated stats
            stats = dup_filter.get_statistics()
            print(f"Database now has {stats['total_records']} total records.")
            if stats["avg_systolic"]:
                print(
                    f"Average BP: {stats['avg_systolic']:.0f}/{stats['avg_diastolic']:.0f} mmHg, "
                    f"{stats['avg_pulse']:.0f} bpm"
                )

    except Exception as e:
        print(f"\nError: {e}")
        raise
    finally:
        print("\nDisconnecting...")
        await client.disconnect()
        print("Done.")

    print(f"\n{'=' * 70}")
    print("Next steps:")
    print("  1. Upload to Garmin: pdm run python -m src.main garmin")
    print("  2. Publish to MQTT:  pdm run python -m src.main mqtt")
    print("  3. View history:     pdm run python tools/show_history.py")
    print(f"{'=' * 70}\n")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Sync blood pressure records from OMRON to local database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  pdm run python tools/sync_records.py
  pdm run python tools/sync_records.py --dry-run
  pdm run python tools/sync_records.py --mac 00:5F:BF:91:9B:4B
        """,
    )
    parser.add_argument(
        "--mac",
        "-m",
        type=str,
        default="00:5F:BF:91:9B:4B",
        help="Device MAC address",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="HEM-7361T",
        help="Device model (default: HEM-7361T)",
    )
    parser.add_argument(
        "--db",
        type=str,
        default="data/omron.db",
        help="Database path (default: data/omron.db)",
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Show what would be saved without saving",
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
            sync_records(
                mac_address=args.mac,
                model=args.model,
                db_path=args.db,
                dry_run=args.dry_run,
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
