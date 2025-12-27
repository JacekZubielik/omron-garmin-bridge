#!/usr/bin/env python3
"""Main entry point for Omron Garmin Bridge.

This module provides the main sync functionality that:
1. Reads blood pressure records from OMRON device via BLE
2. Filters duplicates using local SQLite database
3. Uploads new readings to Garmin Connect
4. Publishes readings to MQTT broker

Usage:
    # One-time sync
    pdm run python -m src.main sync

    # Sync only to Garmin
    pdm run python -m src.main sync --garmin-only

    # Sync only to MQTT
    pdm run python -m src.main sync --mqtt-only

    # Continuous sync every N minutes
    pdm run python -m src.main daemon --interval 60
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from src.duplicate_filter import DuplicateFilter
from src.garmin_uploader import GarminUploader
from src.models import BloodPressureReading
from src.mqtt_publisher import MQTTPublisher
from src.omron_ble.client import OmronBLEClient

logger = logging.getLogger(__name__)

# Type alias for sync summary
SyncSummary = dict[str, Any]

# Default configuration
DEFAULT_CONFIG = {
    "omron": {
        "device_model": "HEM-7361T",
        "mac_address": None,
        "poll_interval_minutes": 60,
        "read_mode": "new_only",
        "sync_time": True,
    },
    "garmin": {
        "enabled": True,
        "tokens_path": "./data/tokens",
    },
    "mqtt": {
        "enabled": True,
        "host": "192.168.40.19",
        "port": 1883,
        "username": None,
        "password": None,
        "base_topic": "omron/blood_pressure",
    },
    "deduplication": {
        "database_path": "./data/omron.db",
    },
    "logging": {
        "level": "INFO",
        "file": None,
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    },
}


class OmronGarminBridge:
    """Main orchestrator for OMRON to Garmin/MQTT sync."""

    def __init__(self, config: dict):
        """Initialize the bridge with configuration.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self._running = False

        # Initialize components
        self.dup_filter = DuplicateFilter(
            config.get("deduplication", {}).get("database_path", "./data/omron.db")
        )

        self.garmin: GarminUploader | None = None
        self.mqtt: MQTTPublisher | None = None

    def _init_garmin(self) -> bool:
        """Initialize Garmin uploader.

        Returns:
            True if initialization successful
        """
        garmin_config = self.config.get("garmin", {})
        if not garmin_config.get("enabled", True):
            logger.info("Garmin upload disabled in config")
            return False

        tokens_path = garmin_config.get("tokens_path", "./data/tokens")
        self.garmin = GarminUploader(tokens_path=tokens_path)

        try:
            self.garmin.login()
            logger.info("Garmin login successful")
            return True
        except Exception as e:
            logger.error(f"Garmin login failed: {e}")
            return False

    def _init_mqtt(self) -> bool:
        """Initialize MQTT publisher.

        Returns:
            True if connection successful
        """
        mqtt_config = self.config.get("mqtt", {})
        if not mqtt_config.get("enabled", True):
            logger.info("MQTT publishing disabled in config")
            return False

        self.mqtt = MQTTPublisher(
            host=mqtt_config.get("host", "192.168.40.19"),
            port=mqtt_config.get("port", 1883),
            username=mqtt_config.get("username"),
            password=mqtt_config.get("password"),
            base_topic=mqtt_config.get("base_topic", "omron/blood_pressure"),
        )

        if self.mqtt.connect():
            logger.info(f"Connected to MQTT broker at {self.mqtt.host}:{self.mqtt.port}")
            self.mqtt.publish_status("online", "Bridge started")
            return True
        else:
            logger.error("Failed to connect to MQTT broker")
            return False

    async def read_from_device(self) -> list[BloodPressureReading]:
        """Read blood pressure records from OMRON device.

        Returns:
            List of blood pressure readings
        """
        omron_config = self.config.get("omron", {})
        model = omron_config.get("device_model", "HEM-7361T")
        mac = omron_config.get("mac_address")
        sync_time = omron_config.get("sync_time", True)

        client = OmronBLEClient(model, mac)

        try:
            logger.info(f"Connecting to OMRON {model}...")
            await client.connect()
            logger.info("Connected to device")

            logger.info("Reading records...")
            records = await client.read_all_records_flat(only_new=False, sync_time=sync_time)
            logger.info(f"Read {len(records)} records from device")

            return records

        finally:
            await client.disconnect()
            logger.info("Disconnected from device")

    def filter_new_records(self, records: list[BloodPressureReading]) -> list[BloodPressureReading]:
        """Filter out records already in local database.

        Args:
            records: All records from device

        Returns:
            Only new records not in database
        """
        new_records = self.dup_filter.filter_new_records(records)
        duplicate_count = len(records) - len(new_records)

        logger.info(f"New records: {len(new_records)}, duplicates: {duplicate_count}")
        return new_records

    def upload_to_garmin(self, records: list[BloodPressureReading]) -> tuple[int, int, int]:
        """Upload records to Garmin Connect.

        Args:
            records: Records to upload

        Returns:
            Tuple of (uploaded, skipped_duplicates, failed)
        """
        if not self.garmin or not self.garmin.is_logged_in:
            logger.warning("Garmin not initialized, skipping upload")
            return (0, 0, len(records))

        uploaded, skipped = self.garmin.upload_readings(records)
        failed = len(records) - uploaded - skipped
        logger.info(
            f"Garmin upload: {uploaded} uploaded, {skipped} skipped (duplicates), {failed} failed"
        )

        # Mark successfully uploaded in local database
        for record in records[:uploaded]:
            self.dup_filter.mark_as_uploaded(record, garmin=True, mqtt=False)

        return (uploaded, skipped, failed)

    def publish_to_mqtt(self, records: list[BloodPressureReading]) -> tuple[int, int]:
        """Publish records to MQTT broker.

        Args:
            records: Records to publish

        Returns:
            Tuple of (success_count, failure_count)
        """
        if not self.mqtt or not self.mqtt.is_connected:
            logger.warning("MQTT not connected, skipping publish")
            return (0, len(records))

        success, failure = self.mqtt.publish_readings(records)
        logger.info(f"MQTT publish: {success} success, {failure} failed")

        # Mark successfully published in local database
        for record in records[:success]:
            self.dup_filter.mark_as_uploaded(record, garmin=False, mqtt=True)

        return (success, failure)

    async def sync(
        self,
        garmin_enabled: bool = True,
        mqtt_enabled: bool = True,
        dry_run: bool = False,
    ) -> SyncSummary:
        """Perform a full sync cycle.

        Args:
            garmin_enabled: Whether to upload to Garmin
            mqtt_enabled: Whether to publish to MQTT
            dry_run: If True, don't actually upload/publish

        Returns:
            Summary dictionary with results
        """
        summary: SyncSummary = {
            "timestamp": datetime.now().isoformat(),
            "device_records": 0,
            "new_records": 0,
            "garmin": {"uploaded": 0, "skipped": 0, "failed": 0},
            "mqtt": {"success": 0, "failed": 0},
            "errors": [],
        }

        try:
            # Read from device
            records = await self.read_from_device()
            summary["device_records"] = len(records)

            if not records:
                logger.info("No records on device")
                return summary

            # Filter new records
            new_records = self.filter_new_records(records)
            summary["new_records"] = len(new_records)

            if not new_records:
                logger.info("No new records to sync")
                return summary

            # Print new records
            for i, r in enumerate(new_records, 1):
                flags = []
                if r.irregular_heartbeat:
                    flags.append("IHB")
                if r.body_movement:
                    flags.append("MOV")
                logger.info(
                    f"  {i}. {r.timestamp:%Y-%m-%d %H:%M} | "
                    f"{r.systolic}/{r.diastolic} mmHg | "
                    f"{r.pulse} bpm | User {r.user_slot} | "
                    f"{r.category}{' [' + ', '.join(flags) + ']' if flags else ''}"
                )

            if dry_run:
                logger.info("DRY RUN - No changes made")
                return summary

            # Upload to Garmin
            if garmin_enabled:
                try:
                    uploaded, skipped, failed = self.upload_to_garmin(new_records)
                    summary["garmin"]["uploaded"] = uploaded
                    summary["garmin"]["skipped"] = skipped
                    summary["garmin"]["failed"] = failed
                except Exception as e:
                    logger.error(f"Garmin upload error: {e}")
                    summary["errors"].append(f"Garmin: {e}")

            # Publish to MQTT
            if mqtt_enabled:
                try:
                    success, failed = self.publish_to_mqtt(new_records)
                    summary["mqtt"]["success"] = success
                    summary["mqtt"]["failed"] = failed
                except Exception as e:
                    logger.error(f"MQTT publish error: {e}")
                    summary["errors"].append(f"MQTT: {e}")

            # Publish sync status to MQTT
            if self.mqtt and self.mqtt.is_connected:
                self.mqtt.publish_status(
                    "synced",
                    f"Synced {len(new_records)} new records",
                )

        except Exception as e:
            logger.error(f"Sync error: {e}")
            summary["errors"].append(str(e))

        return summary

    async def run_daemon(self, interval_minutes: int = 60) -> None:
        """Run continuous sync daemon.

        Args:
            interval_minutes: Minutes between sync cycles
        """
        self._running = True
        logger.info(f"Starting daemon with {interval_minutes} minute interval")

        # Handle shutdown signals
        def handle_signal(_signum, _frame):
            logger.info("Shutdown signal received")
            self._running = False

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        while self._running:
            try:
                logger.info("Starting sync cycle...")
                summary = await self.sync()

                logger.info(
                    f"Sync complete: {summary['new_records']} new records, "
                    f"Garmin: {summary['garmin']['uploaded']} uploaded, "
                    f"MQTT: {summary['mqtt']['success']} published"
                )

            except Exception as e:
                logger.error(f"Sync cycle failed: {e}")
                if self.mqtt and self.mqtt.is_connected:
                    self.mqtt.publish_status("error", str(e))

            if self._running:
                logger.info(f"Sleeping for {interval_minutes} minutes...")
                for _ in range(interval_minutes * 60):
                    if not self._running:
                        break
                    await asyncio.sleep(1)

        logger.info("Daemon stopped")

    def cleanup(self) -> None:
        """Clean up resources."""
        if self.mqtt:
            self.mqtt.publish_status("offline", "Bridge stopped")
            self.mqtt.disconnect()

        if self.garmin:
            self.garmin.logout()


def load_config(config_path: str | None = None) -> dict:
    """Load configuration from file or use defaults.

    Args:
        config_path: Path to YAML config file

    Returns:
        Configuration dictionary
    """
    config = DEFAULT_CONFIG.copy()

    if config_path and Path(config_path).exists():
        with open(config_path) as f:
            user_config = yaml.safe_load(f)
            if user_config and isinstance(user_config, dict):
                # Deep merge user config into defaults
                for section, values in user_config.items():
                    section_config = config.get(section)
                    if (
                        section_config is not None
                        and isinstance(section_config, dict)
                        and isinstance(values, dict)
                    ):
                        section_config.update(values)
                    else:
                        config[section] = values

    return config


def setup_logging(config: dict) -> None:
    """Setup logging based on configuration.

    Args:
        config: Configuration dictionary
    """
    log_config = config.get("logging", {})
    level = getattr(logging, log_config.get("level", "INFO").upper())
    format_str = log_config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    handlers: list[logging.Handler] = [logging.StreamHandler()]

    log_file = log_config.get("file")
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(level=level, format=format_str, handlers=handlers)


async def cmd_sync(args: argparse.Namespace, config: dict) -> int:
    """Handle sync command.

    Args:
        args: Parsed command line arguments
        config: Configuration dictionary

    Returns:
        Exit code
    """
    bridge = OmronGarminBridge(config)

    try:
        # Initialize services
        garmin_ok = False
        mqtt_ok = False

        if not args.mqtt_only:
            garmin_ok = bridge._init_garmin()
        if not args.garmin_only:
            mqtt_ok = bridge._init_mqtt()

        if not garmin_ok and not mqtt_ok and not args.dry_run:
            logger.error("No services available for sync")
            return 1

        # Run sync
        summary = await bridge.sync(
            garmin_enabled=not args.mqtt_only,
            mqtt_enabled=not args.garmin_only,
            dry_run=args.dry_run,
        )

        # Print summary
        print(f"\n{'=' * 60}")
        print("Sync Summary")
        print(f"{'=' * 60}")
        print(f"Device records: {summary['device_records']}")
        print(f"New records:    {summary['new_records']}")
        print(
            f"Garmin:         {summary['garmin']['uploaded']} uploaded, "
            f"{summary['garmin']['skipped']} skipped, "
            f"{summary['garmin']['failed']} failed"
        )
        print(
            f"MQTT:           {summary['mqtt']['success']} published, "
            f"{summary['mqtt']['failed']} failed"
        )
        if summary["errors"]:
            print(f"Errors:         {', '.join(summary['errors'])}")
        print(f"{'=' * 60}\n")

        return 0 if not summary["errors"] else 1

    finally:
        bridge.cleanup()


async def cmd_daemon(args: argparse.Namespace, config: dict) -> int:
    """Handle daemon command.

    Args:
        args: Parsed command line arguments
        config: Configuration dictionary

    Returns:
        Exit code
    """
    bridge = OmronGarminBridge(config)

    try:
        # Initialize services
        bridge._init_garmin()
        bridge._init_mqtt()

        # Run daemon
        interval = args.interval or config.get("omron", {}).get("poll_interval_minutes", 60)
        await bridge.run_daemon(interval_minutes=interval)

        return 0

    finally:
        bridge.cleanup()


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="OMRON to Garmin/MQTT Blood Pressure Bridge",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default="config/config.yaml",
        help="Path to config file (default: config/config.yaml)",
    )
    parser.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Enable debug logging",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Sync command
    sync_parser = subparsers.add_parser("sync", help="Sync records once")
    sync_parser.add_argument(
        "--garmin-only",
        action="store_true",
        help="Only upload to Garmin",
    )
    sync_parser.add_argument(
        "--mqtt-only",
        action="store_true",
        help="Only publish to MQTT",
    )
    sync_parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Show what would happen without making changes",
    )

    # Daemon command
    daemon_parser = subparsers.add_parser("daemon", help="Run continuous sync")
    daemon_parser.add_argument(
        "--interval",
        "-i",
        type=int,
        help="Sync interval in minutes (overrides config)",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Load config
    config = load_config(args.config)

    # Setup logging
    if args.debug:
        config["logging"]["level"] = "DEBUG"
    setup_logging(config)

    # Run command
    try:
        if args.command == "sync":
            exit_code = asyncio.run(cmd_sync(args, config))
        elif args.command == "daemon":
            exit_code = asyncio.run(cmd_daemon(args, config))
        else:
            parser.print_help()
            exit_code = 1

        sys.exit(exit_code)

    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        if args.debug:
            raise
        sys.exit(1)


if __name__ == "__main__":
    main()
