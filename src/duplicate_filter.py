"""Duplicate filter for blood pressure records using SQLite.

This module provides deduplication functionality to prevent uploading
the same blood pressure records multiple times. OMRON devices store
~100-200 records in a ring buffer, and each read may return all or
only new records depending on the mode.
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from src.models import BloodPressureReading

logger = logging.getLogger(__name__)


class DuplicateFilter:
    """Filter duplicate blood pressure records using SQLite storage.

    This class tracks which records have been uploaded to Garmin/MQTT
    and provides filtering to ensure each record is processed only once.
    """

    def __init__(self, db_path: str = "data/omron.db"):
        """Initialize the duplicate filter.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS uploaded_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_hash TEXT UNIQUE NOT NULL,
                    timestamp TEXT NOT NULL,
                    systolic INTEGER NOT NULL,
                    diastolic INTEGER NOT NULL,
                    pulse INTEGER NOT NULL,
                    irregular_heartbeat BOOLEAN DEFAULT FALSE,
                    body_movement BOOLEAN DEFAULT FALSE,
                    user_slot INTEGER DEFAULT 1,
                    category TEXT,
                    uploaded_at TEXT NOT NULL,
                    garmin_uploaded BOOLEAN DEFAULT FALSE,
                    mqtt_published BOOLEAN DEFAULT FALSE
                )
            """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_record_hash ON uploaded_records(record_hash)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON uploaded_records(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_user_slot ON uploaded_records(user_slot)")
            conn.commit()
            logger.debug(f"Database initialized at {self.db_path}")

    def is_duplicate(self, record: BloodPressureReading) -> bool:
        """Check if a record has already been processed.

        Args:
            record: Blood pressure reading to check

        Returns:
            True if record exists in database
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM uploaded_records WHERE record_hash = ?",
                (record.record_hash,),
            )
            return cursor.fetchone() is not None

    def filter_new_records(self, records: list[BloodPressureReading]) -> list[BloodPressureReading]:
        """Filter out records that have already been processed.

        Args:
            records: List of blood pressure readings

        Returns:
            List of new (not yet processed) records
        """
        if not records:
            return []

        new_records = []
        with sqlite3.connect(self.db_path) as conn:
            for record in records:
                cursor = conn.execute(
                    "SELECT 1 FROM uploaded_records WHERE record_hash = ?",
                    (record.record_hash,),
                )
                if cursor.fetchone() is None:
                    new_records.append(record)

        logger.info(
            f"Filtered {len(records)} records: {len(new_records)} new, "
            f"{len(records) - len(new_records)} duplicates"
        )
        return new_records

    def mark_as_uploaded(
        self,
        record: BloodPressureReading,
        garmin: bool = False,
        mqtt: bool = False,
    ) -> None:
        """Mark a record as uploaded/processed.

        Args:
            record: Blood pressure reading to mark
            garmin: Whether uploaded to Garmin
            mqtt: Whether published to MQTT
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO uploaded_records
                (record_hash, timestamp, systolic, diastolic, pulse,
                 irregular_heartbeat, body_movement, user_slot, category,
                 uploaded_at, garmin_uploaded, mqtt_published)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(record_hash) DO UPDATE SET
                    garmin_uploaded = garmin_uploaded OR excluded.garmin_uploaded,
                    mqtt_published = mqtt_published OR excluded.mqtt_published
                """,
                (
                    record.record_hash,
                    record.timestamp.isoformat(),
                    record.systolic,
                    record.diastolic,
                    record.pulse,
                    record.irregular_heartbeat,
                    record.body_movement,
                    record.user_slot,
                    record.category,
                    datetime.now().isoformat(),
                    garmin,
                    mqtt,
                ),
            )
            conn.commit()
            logger.debug(f"Marked record as uploaded: {record.record_hash}")

    def update_upload_status(
        self,
        record: BloodPressureReading,
        garmin: bool | None = None,
        mqtt: bool | None = None,
    ) -> None:
        """Update upload status for an existing record.

        Args:
            record: Blood pressure reading to update
            garmin: New Garmin upload status (None to keep current)
            mqtt: New MQTT publish status (None to keep current)
        """
        updates: list[str] = []
        params: list[bool | str] = []

        if garmin is not None:
            updates.append("garmin_uploaded = ?")
            params.append(garmin)

        if mqtt is not None:
            updates.append("mqtt_published = ?")
            params.append(mqtt)

        if not updates:
            return

        params.append(record.record_hash)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                f"UPDATE uploaded_records SET {', '.join(updates)} WHERE record_hash = ?",  # nosec B608
                params,
            )
            conn.commit()

    def get_history(
        self,
        limit: int = 100,
        user_slot: int | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict]:
        """Get history of uploaded records.

        Args:
            limit: Maximum number of records to return
            user_slot: Filter by user slot (1 or 2)
            start_date: Filter records after this date
            end_date: Filter records before this date

        Returns:
            List of record dictionaries
        """
        query = "SELECT * FROM uploaded_records WHERE 1=1"
        params: list = []

        if user_slot is not None:
            query += " AND user_slot = ?"
            params.append(user_slot)

        if start_date is not None:
            query += " AND timestamp >= ?"
            params.append(start_date.isoformat())

        if end_date is not None:
            query += " AND timestamp <= ?"
            params.append(end_date.isoformat())

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_statistics(self, user_slot: int | None = None) -> dict:
        """Get statistics about stored records.

        Args:
            user_slot: Filter by user slot (1 or 2)

        Returns:
            Dictionary with statistics
        """
        where_clause = ""
        params: list = []

        if user_slot is not None:
            where_clause = "WHERE user_slot = ?"
            params.append(user_slot)

        with sqlite3.connect(self.db_path) as conn:
            # Total count
            # Note: where_clause is built from controlled values, not user input
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM uploaded_records {where_clause}",  # nosec B608
                params,
            )
            total_count = cursor.fetchone()[0]

            # Garmin uploaded count
            garmin_where = (
                f"{where_clause} {'AND' if where_clause else 'WHERE'} garmin_uploaded = 1"
            )
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM uploaded_records {garmin_where}",  # nosec B608
                params,
            )
            garmin_count = cursor.fetchone()[0]

            # MQTT published count
            mqtt_where = f"{where_clause} {'AND' if where_clause else 'WHERE'} mqtt_published = 1"
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM uploaded_records {mqtt_where}",  # nosec B608
                params,
            )
            mqtt_count = cursor.fetchone()[0]

            # Date range
            cursor = conn.execute(
                f"SELECT MIN(timestamp), MAX(timestamp) FROM uploaded_records {where_clause}",  # nosec B608
                params,
            )
            row = cursor.fetchone()
            first_record = row[0]
            last_record = row[1]

            # Average values
            cursor = conn.execute(
                f"""
                SELECT
                    AVG(systolic) as avg_systolic,
                    AVG(diastolic) as avg_diastolic,
                    AVG(pulse) as avg_pulse
                FROM uploaded_records {where_clause}
                """,  # nosec B608
                params,
            )
            row = cursor.fetchone()

            return {
                "total_records": total_count,
                "garmin_uploaded": garmin_count,
                "mqtt_published": mqtt_count,
                "first_record": first_record,
                "last_record": last_record,
                "avg_systolic": round(row[0], 1) if row[0] else None,
                "avg_diastolic": round(row[1], 1) if row[1] else None,
                "avg_pulse": round(row[2], 1) if row[2] else None,
            }

    def get_pending_garmin(self, limit: int = 100) -> list[dict]:
        """Get records not yet uploaded to Garmin.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of pending record dictionaries
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM uploaded_records
                WHERE garmin_uploaded = 0
                ORDER BY timestamp ASC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_pending_mqtt(self, limit: int = 100) -> list[dict]:
        """Get records not yet published to MQTT.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of pending record dictionaries
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM uploaded_records
                WHERE mqtt_published = 0
                ORDER BY timestamp ASC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def delete_old_records(self, days: int = 365) -> int:
        """Delete records older than specified days.

        Args:
            days: Delete records older than this many days

        Returns:
            Number of deleted records
        """
        cutoff_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff_date = cutoff_date.replace(
            day=cutoff_date.day - days if cutoff_date.day > days else 1
        )

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM uploaded_records WHERE timestamp < ?",
                (cutoff_date.isoformat(),),
            )
            deleted = cursor.rowcount
            conn.commit()

        if deleted > 0:
            logger.info(f"Deleted {deleted} records older than {days} days")

        return deleted

    def clear_all(self) -> int:
        """Clear all records from database.

        Returns:
            Number of deleted records
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM uploaded_records")
            deleted = cursor.rowcount
            conn.commit()

        logger.warning(f"Cleared all {deleted} records from database")
        return deleted
