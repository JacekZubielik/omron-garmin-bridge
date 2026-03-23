#!/usr/bin/env python3
"""SQLite database statistics and management for OMRON Garmin Bridge."""

import argparse
import sqlite3
import sys
from pathlib import Path

import yaml


def _find_project_root() -> Path:
    """Walk up from script to find pyproject.toml."""
    p = Path(__file__).resolve().parent
    for _ in range(10):
        if (p / "pyproject.toml").exists():
            return p
        p = p.parent
    raise RuntimeError("Could not find project root (no pyproject.toml)")


project_root = _find_project_root()


def get_db_path() -> Path:
    config_path = project_root / "config" / "config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
        db_rel = config.get("deduplication", {}).get("database_path", "data/omron.db")
    else:
        db_rel = "data/omron.db"
    db_path = Path(db_rel)
    if not db_path.is_absolute():
        db_path = project_root / db_path
    return db_path


def show_stats(db_path: Path):
    with sqlite3.connect(db_path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM uploaded_records").fetchone()[0]
        garmin = conn.execute(
            "SELECT COUNT(*) FROM uploaded_records WHERE garmin_uploaded = 1"
        ).fetchone()[0]
        mqtt = conn.execute(
            "SELECT COUNT(*) FROM uploaded_records WHERE mqtt_published = 1"
        ).fetchone()[0]
        pending_garmin = conn.execute(
            "SELECT COUNT(*) FROM uploaded_records WHERE garmin_uploaded = 0"
        ).fetchone()[0]
        pending_mqtt = conn.execute(
            "SELECT COUNT(*) FROM uploaded_records WHERE mqtt_published = 0"
        ).fetchone()[0]
        dates = conn.execute(
            "SELECT MIN(timestamp), MAX(timestamp) FROM uploaded_records"
        ).fetchone()
        avgs = conn.execute(
            "SELECT AVG(systolic), AVG(diastolic), AVG(pulse) FROM uploaded_records"
        ).fetchone()

    print(f"Database: {db_path}")
    print(f"Total records: {total}")
    print(f"Garmin uploaded: {garmin} (pending: {pending_garmin})")
    print(f"MQTT published: {mqtt} (pending: {pending_mqtt})")
    if dates[0]:
        print(f"Date range: {dates[0]} — {dates[1]}")
    if avgs[0]:
        print(f"Average BP: {avgs[0]:.0f}/{avgs[1]:.0f} mmHg, pulse {avgs[2]:.0f} bpm")


def show_pending(db_path: Path):
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        garmin = conn.execute(
            "SELECT timestamp, systolic, diastolic, pulse, user_slot "
            "FROM uploaded_records WHERE garmin_uploaded = 0 ORDER BY timestamp"
        ).fetchall()
        mqtt = conn.execute(
            "SELECT timestamp, systolic, diastolic, pulse, user_slot "
            "FROM uploaded_records WHERE mqtt_published = 0 ORDER BY timestamp"
        ).fetchall()

    if garmin:
        print(f"\nPending Garmin uploads ({len(garmin)}):")
        for r in garmin:
            print(
                f"  {r['timestamp']} | {r['systolic']}/{r['diastolic']} | "
                f"pulse {r['pulse']} | user {r['user_slot']}"
            )
    else:
        print("\nNo pending Garmin uploads")

    if mqtt:
        print(f"\nPending MQTT publishes ({len(mqtt)}):")
        for r in mqtt:
            print(
                f"  {r['timestamp']} | {r['systolic']}/{r['diastolic']} | "
                f"pulse {r['pulse']} | user {r['user_slot']}"
            )
    else:
        print("\nNo pending MQTT publishes")


def show_history(db_path: Path, limit: int):
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT timestamp, systolic, diastolic, pulse, category, user_slot, "
            "garmin_uploaded, mqtt_published "
            "FROM uploaded_records ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()

    print(f"\nLast {limit} records:")
    print(
        f"{'Timestamp':<20} {'BP':>7} {'Pulse':>5} {'Category':<22} {'User':>4} {'G':>1} {'M':>1}"
    )
    print("-" * 70)
    for r in rows:
        g = "+" if r["garmin_uploaded"] else "-"
        m = "+" if r["mqtt_published"] else "-"
        print(
            f"{r['timestamp']:<20} {r['systolic']:>3}/{r['diastolic']:<3} "
            f"{r['pulse']:>5} {r['category']:<22} {r['user_slot']:>4} {g:>1} {m:>1}"
        )


def cleanup(db_path: Path, days: int):
    from datetime import datetime, timedelta

    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    with sqlite3.connect(db_path) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM uploaded_records WHERE timestamp < ?", (cutoff,)
        ).fetchone()[0]
        if count == 0:
            print(f"No records older than {days} days")
            return
        print(f"Found {count} records older than {days} days")
        confirm = input(f"Delete {count} records? [y/N] ")
        if confirm.lower() == "y":
            conn.execute("DELETE FROM uploaded_records WHERE timestamp < ?", (cutoff,))
            conn.commit()
            print(f"Deleted {count} records")
        else:
            print("Cancelled")


def main():
    parser = argparse.ArgumentParser(description="OMRON DB statistics and management")
    parser.add_argument("--pending", action="store_true", help="Show pending uploads")
    parser.add_argument("--history", type=int, metavar="N", help="Show last N records")
    parser.add_argument(
        "--cleanup", type=int, metavar="DAYS", help="Delete records older than N days"
    )
    args = parser.parse_args()

    db_path = get_db_path()
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        sys.exit(1)

    show_stats(db_path)

    if args.pending:
        show_pending(db_path)
    if args.history:
        show_history(db_path, args.history)
    if args.cleanup:
        cleanup(db_path, args.cleanup)


if __name__ == "__main__":
    main()
