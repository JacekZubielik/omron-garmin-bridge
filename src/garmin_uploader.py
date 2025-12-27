"""Garmin Connect uploader for blood pressure readings.

This module handles uploading blood pressure measurements to Garmin Connect,
with duplicate detection both locally (SQLite) and remotely (Garmin API).
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path

from garminconnect import Garmin, GarminConnectAuthenticationError

from src.models import BloodPressureReading

logger = logging.getLogger(__name__)

# Default token storage path
DEFAULT_TOKENS_PATH = Path("~/.garminconnect").expanduser()


class GarminUploader:
    """Upload blood pressure readings to Garmin Connect.

    Features:
    - OAuth token-based authentication (tokens valid for 1 year)
    - Duplicate detection via Garmin Connect API
    - Automatic token refresh
    - Support for multiple user accounts
    """

    def __init__(self, tokens_path: str | None = None):
        """Initialize Garmin uploader.

        Args:
            tokens_path: Path to directory with OAuth tokens.
                        If None, uses ~/.garminconnect
        """
        self.tokens_path = Path(tokens_path) if tokens_path else DEFAULT_TOKENS_PATH
        self._client: Garmin | None = None
        self._current_email: str | None = None
        self._logged_in = False

    def login(self, email: str | None = None) -> bool:
        """Login to Garmin Connect using stored OAuth tokens.

        Args:
            email: Optional email for multi-user support.
                   If provided, tokens are loaded from tokens_path/email/

        Returns:
            True if login successful

        Raises:
            GarminConnectAuthenticationError: If authentication fails
            FileNotFoundError: If token files not found
        """
        # Determine token location
        token_dir = self.tokens_path / email.replace("@", "_at_") if email else self.tokens_path

        if not token_dir.exists():
            raise FileNotFoundError(
                f"Token directory not found: {token_dir}\n"
                f"Run 'pdm run python tools/import_tokens.py' to generate tokens."
            )

        try:
            self._client = Garmin()
            self._client.login(tokenstore=str(token_dir))
            self._current_email = email
            self._logged_in = True

            display_name = self._client.display_name or "Unknown"
            logger.info(f"Logged in to Garmin Connect as {display_name}")
            return True

        except GarminConnectAuthenticationError as e:
            logger.error(f"Garmin authentication failed: {e}")
            self._client = None
            self._logged_in = False
            raise

        except Exception as e:
            logger.error(f"Garmin login error: {e}")
            self._client = None
            self._logged_in = False
            raise

    def logout(self) -> None:
        """Logout from Garmin Connect."""
        self._client = None
        self._current_email = None
        self._logged_in = False
        logger.info("Logged out from Garmin Connect")

    @property
    def is_logged_in(self) -> bool:
        """Check if currently logged in."""
        return self._logged_in and self._client is not None

    def get_existing_readings(
        self,
        start_date: datetime,
        end_date: datetime | None = None,
    ) -> list[dict]:
        """Get existing blood pressure readings from Garmin Connect.

        Args:
            start_date: Start date for query
            end_date: End date for query (defaults to start_date)

        Returns:
            List of blood pressure readings from Garmin
        """
        if not self.is_logged_in or self._client is None:
            raise RuntimeError("Not logged in. Call login() first.")

        start_str = start_date.strftime("%Y-%m-%d")
        end_str = (end_date or start_date).strftime("%Y-%m-%d")

        logger.debug(f"Fetching Garmin BP readings from {start_str} to {end_str}")

        try:
            response = self._client.get_blood_pressure(start_str, end_str)

            # Response structure:
            # {"measurementSummaries": [
            #     {"startDate": "...", "measurements": [
            #         {"systolic": 120, "diastolic": 80, "pulse": 70,
            #          "measurementTimestampLocal": "2025-12-26T23:00:00.0", ...},
            #         ...
            #     ]},
            #     ...
            # ]}
            if not response:
                return []

            # Flatten all measurements from all daily summaries
            all_readings: list[dict] = []
            for summary in response.get("measurementSummaries", []):
                measurements = summary.get("measurements", [])
                all_readings.extend(measurements)

            logger.debug(f"Found {len(all_readings)} existing readings in Garmin")
            return all_readings

        except Exception as e:
            logger.warning(f"Failed to fetch Garmin readings: {e}")
            return []

    def is_duplicate_in_garmin(
        self,
        reading: BloodPressureReading,
        existing_readings: list[dict] | None = None,
    ) -> bool:
        """Check if a reading already exists in Garmin Connect.

        Compares by timestamp (within 1 minute tolerance) and values.

        Args:
            reading: Reading to check
            existing_readings: Pre-fetched readings (optional, for batch checking)

        Returns:
            True if reading appears to be a duplicate
        """
        if existing_readings is None:
            # Fetch readings for the day of this measurement
            existing_readings = self.get_existing_readings(
                reading.timestamp,
                reading.timestamp,
            )

        if not existing_readings:
            return False

        for existing in existing_readings:
            # Parse Garmin timestamp
            # Format: "2025-12-26T22:59:00.0" or similar
            garmin_ts_str = existing.get("measurementTimestampLocal", "")
            if not garmin_ts_str:
                continue

            try:
                # Handle various timestamp formats
                garmin_ts_str = garmin_ts_str.replace("Z", "+00:00")
                if "." in garmin_ts_str:
                    # Remove fractional seconds for parsing
                    base, frac = garmin_ts_str.split(".")
                    # Parse base regardless of timezone presence in frac
                    garmin_ts = datetime.fromisoformat(base)
                    del frac  # Unused after split
                else:
                    garmin_ts = datetime.fromisoformat(garmin_ts_str)
            except (ValueError, TypeError) as e:
                logger.debug(f"Failed to parse Garmin timestamp '{garmin_ts_str}': {e}")
                continue

            # Check if timestamps are within 1 minute
            time_diff = abs((reading.timestamp - garmin_ts).total_seconds())
            if time_diff > 60:
                continue

            # Check if values match
            garmin_sys = existing.get("systolic")
            garmin_dia = existing.get("diastolic")
            garmin_pulse = existing.get("pulse")

            if (
                garmin_sys == reading.systolic
                and garmin_dia == reading.diastolic
                and garmin_pulse == reading.pulse
            ):
                logger.debug(
                    f"Found duplicate in Garmin: {reading.systolic}/{reading.diastolic} "
                    f"at {reading.timestamp}"
                )
                return True

        return False

    def upload_reading(
        self,
        reading: BloodPressureReading,
        check_duplicate: bool = True,
        existing_readings: list[dict] | None = None,
    ) -> bool:
        """Upload a single blood pressure reading to Garmin Connect.

        Args:
            reading: Blood pressure reading to upload
            check_duplicate: Whether to check for duplicates in Garmin first
            existing_readings: Pre-fetched readings for duplicate check

        Returns:
            True if upload successful, False if skipped (duplicate)
        """
        if not self.is_logged_in or self._client is None:
            raise RuntimeError("Not logged in. Call login() first.")

        # Check for duplicate in Garmin
        if check_duplicate and self.is_duplicate_in_garmin(reading, existing_readings):
            logger.info(
                f"Skipping duplicate: {reading.systolic}/{reading.diastolic} at {reading.timestamp}"
            )
            return False

        # Build notes with flags
        notes_parts = [f"OMRON BLE import (slot {reading.user_slot})"]
        if reading.irregular_heartbeat:
            notes_parts.append("IHB detected")
        if reading.body_movement:
            notes_parts.append("Body movement detected")
        notes = " | ".join(notes_parts)

        try:
            self._client.set_blood_pressure(
                systolic=reading.systolic,
                diastolic=reading.diastolic,
                pulse=reading.pulse,
                timestamp=reading.timestamp.isoformat(),
                notes=notes,
            )

            logger.info(
                f"Uploaded to Garmin: {reading.systolic}/{reading.diastolic} mmHg, "
                f"pulse {reading.pulse} bpm @ {reading.timestamp}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to upload reading: {e}")
            raise

    def upload_readings(
        self,
        readings: list[BloodPressureReading],
        check_duplicates: bool = True,
    ) -> tuple[int, int]:
        """Upload multiple blood pressure readings to Garmin Connect.

        Optimized for batch uploads by pre-fetching existing readings.

        Args:
            readings: List of readings to upload
            check_duplicates: Whether to check for duplicates in Garmin

        Returns:
            Tuple of (uploaded_count, skipped_count)
        """
        if not self.is_logged_in:
            raise RuntimeError("Not logged in. Call login() first.")

        if not readings:
            return (0, 0)

        uploaded = 0
        skipped = 0

        # Pre-fetch existing readings for the date range
        existing_readings: list[dict] = []
        if check_duplicates:
            # Find date range
            min_date = min(r.timestamp for r in readings)
            max_date = max(r.timestamp for r in readings)

            # Add 1 day buffer on each side
            start_date = min_date - timedelta(days=1)
            end_date = max_date + timedelta(days=1)

            existing_readings = self.get_existing_readings(start_date, end_date)
            logger.info(
                f"Found {len(existing_readings)} existing readings in Garmin "
                f"for date range {start_date.date()} to {end_date.date()}"
            )

        # Upload each reading
        for reading in readings:
            try:
                success = self.upload_reading(
                    reading,
                    check_duplicate=check_duplicates,
                    existing_readings=existing_readings,
                )
                if success:
                    uploaded += 1
                else:
                    skipped += 1
            except Exception as e:
                logger.error(f"Failed to upload {reading}: {e}")
                # Continue with next reading
                continue

        logger.info(f"Upload complete: {uploaded} uploaded, {skipped} skipped")
        return (uploaded, skipped)

    def filter_new_readings(
        self,
        readings: list[BloodPressureReading],
    ) -> list[BloodPressureReading]:
        """Filter readings to only those not already in Garmin Connect.

        Args:
            readings: List of readings to filter

        Returns:
            List of readings not found in Garmin
        """
        if not readings:
            return []

        # Find date range
        min_date = min(r.timestamp for r in readings)
        max_date = max(r.timestamp for r in readings)

        # Add 1 day buffer
        start_date = min_date - timedelta(days=1)
        end_date = max_date + timedelta(days=1)

        # Fetch existing readings
        existing_readings = self.get_existing_readings(start_date, end_date)

        # Filter out duplicates
        new_readings = []
        for reading in readings:
            if not self.is_duplicate_in_garmin(reading, existing_readings):
                new_readings.append(reading)

        logger.info(
            f"Filtered readings: {len(new_readings)} new, "
            f"{len(readings) - len(new_readings)} already in Garmin"
        )
        return new_readings


def create_garmin_uploader(
    tokens_path: str | None = None,
    email: str | None = None,
) -> GarminUploader:
    """Factory function to create and login a GarminUploader.

    Args:
        tokens_path: Path to token storage directory
        email: Optional email for multi-user support

    Returns:
        Logged-in GarminUploader instance
    """
    uploader = GarminUploader(tokens_path)
    uploader.login(email)
    return uploader
