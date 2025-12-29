"""Tests for DuplicateFilter class."""

from datetime import datetime

from src.duplicate_filter import DuplicateFilter
from src.models import BloodPressureReading


class TestDuplicateFilter:
    """Test suite for DuplicateFilter."""

    def test_init_creates_database(self, db_path):
        """Database should be created on initialization."""
        filter_instance = DuplicateFilter(db_path)
        assert filter_instance.db_path.exists()

    def test_init_creates_parent_directories(self, tmp_path):
        """Should create parent directories if they don't exist."""
        nested_path = tmp_path / "nested" / "path" / "test.db"
        DuplicateFilter(str(nested_path))  # Creates parent dirs on init
        assert nested_path.parent.exists()

    def test_is_duplicate_returns_false_for_new_record(self, db_path, sample_reading):
        """New record should not be marked as duplicate."""
        filter_instance = DuplicateFilter(db_path)
        assert filter_instance.is_duplicate(sample_reading) is False

    def test_is_duplicate_returns_true_after_marking(self, db_path, sample_reading):
        """Record should be duplicate after being marked as uploaded."""
        filter_instance = DuplicateFilter(db_path)
        filter_instance.mark_as_uploaded(sample_reading, garmin=True)
        assert filter_instance.is_duplicate(sample_reading) is True

    def test_filter_new_records_returns_all_new(self, db_path, multiple_readings):
        """All records should be returned when none are uploaded."""
        filter_instance = DuplicateFilter(db_path)
        new_records = filter_instance.filter_new_records(multiple_readings)
        assert len(new_records) == len(multiple_readings)

    def test_filter_new_records_removes_duplicates(self, db_path, multiple_readings):
        """Already uploaded records should be filtered out."""
        filter_instance = DuplicateFilter(db_path)

        # Mark first record as uploaded
        filter_instance.mark_as_uploaded(multiple_readings[0], garmin=True)

        new_records = filter_instance.filter_new_records(multiple_readings)
        assert len(new_records) == len(multiple_readings) - 1
        assert multiple_readings[0] not in new_records

    def test_filter_new_records_empty_list(self, db_path):
        """Empty list should return empty list."""
        filter_instance = DuplicateFilter(db_path)
        new_records = filter_instance.filter_new_records([])
        assert new_records == []

    def test_mark_as_uploaded_garmin_only(self, db_path, sample_reading):
        """Record should be marked as uploaded to Garmin only."""
        filter_instance = DuplicateFilter(db_path)
        filter_instance.mark_as_uploaded(sample_reading, garmin=True, mqtt=False)

        history = filter_instance.get_history(limit=1)
        assert len(history) == 1
        assert history[0]["garmin_uploaded"] == 1
        assert history[0]["mqtt_published"] == 0

    def test_mark_as_uploaded_mqtt_only(self, db_path, sample_reading):
        """Record should be marked as published to MQTT only."""
        filter_instance = DuplicateFilter(db_path)
        filter_instance.mark_as_uploaded(sample_reading, garmin=False, mqtt=True)

        history = filter_instance.get_history(limit=1)
        assert len(history) == 1
        assert history[0]["garmin_uploaded"] == 0
        assert history[0]["mqtt_published"] == 1

    def test_mark_as_uploaded_both(self, db_path, sample_reading):
        """Record should be marked as uploaded to both services."""
        filter_instance = DuplicateFilter(db_path)
        filter_instance.mark_as_uploaded(sample_reading, garmin=True, mqtt=True)

        history = filter_instance.get_history(limit=1)
        assert len(history) == 1
        assert history[0]["garmin_uploaded"] == 1
        assert history[0]["mqtt_published"] == 1

    def test_mark_as_uploaded_updates_existing(self, db_path, sample_reading):
        """Subsequent uploads should update existing record."""
        filter_instance = DuplicateFilter(db_path)

        # First upload: Garmin only
        filter_instance.mark_as_uploaded(sample_reading, garmin=True, mqtt=False)

        # Second upload: MQTT
        filter_instance.mark_as_uploaded(sample_reading, garmin=False, mqtt=True)

        # Should have only one record with both flags set
        history = filter_instance.get_history(limit=10)
        assert len(history) == 1
        assert history[0]["garmin_uploaded"] == 1
        assert history[0]["mqtt_published"] == 1

    def test_get_history_returns_recent_first(self, db_path, multiple_readings):
        """History should return most recent records first."""
        filter_instance = DuplicateFilter(db_path)

        for reading in multiple_readings:
            filter_instance.mark_as_uploaded(reading, garmin=True)

        history = filter_instance.get_history(limit=10)
        assert len(history) == 3

        # Most recent should be first
        timestamps = [h["timestamp"] for h in history]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_get_history_respects_limit(self, db_path, multiple_readings):
        """History should respect the limit parameter."""
        filter_instance = DuplicateFilter(db_path)

        for reading in multiple_readings:
            filter_instance.mark_as_uploaded(reading, garmin=True)

        history = filter_instance.get_history(limit=2)
        assert len(history) == 2

    def test_get_history_filters_by_user_slot(self, db_path, sample_reading, sample_reading_user2):
        """History should filter by user slot."""
        filter_instance = DuplicateFilter(db_path)

        filter_instance.mark_as_uploaded(sample_reading, garmin=True)
        filter_instance.mark_as_uploaded(sample_reading_user2, garmin=True)

        history_user1 = filter_instance.get_history(user_slot=1)
        history_user2 = filter_instance.get_history(user_slot=2)

        assert len(history_user1) == 1
        assert len(history_user2) == 1
        assert history_user1[0]["user_slot"] == 1
        assert history_user2[0]["user_slot"] == 2

    def test_get_statistics_empty_database(self, db_path):
        """Statistics should handle empty database."""
        filter_instance = DuplicateFilter(db_path)
        stats = filter_instance.get_statistics()

        assert stats["total_records"] == 0
        assert stats["garmin_uploaded"] == 0
        assert stats["mqtt_published"] == 0
        assert stats["first_record"] is None
        assert stats["last_record"] is None

    def test_get_statistics_with_records(self, db_path, multiple_readings):
        """Statistics should return correct values."""
        filter_instance = DuplicateFilter(db_path)

        filter_instance.mark_as_uploaded(multiple_readings[0], garmin=True, mqtt=True)
        filter_instance.mark_as_uploaded(multiple_readings[1], garmin=True, mqtt=False)
        filter_instance.mark_as_uploaded(multiple_readings[2], garmin=False, mqtt=True)

        stats = filter_instance.get_statistics()

        assert stats["total_records"] == 3
        assert stats["garmin_uploaded"] == 2
        assert stats["mqtt_published"] == 2
        assert stats["first_record"] is not None
        assert stats["last_record"] is not None
        assert stats["avg_systolic"] is not None

    def test_get_pending_garmin(self, db_path, multiple_readings):
        """Should return records not uploaded to Garmin."""
        filter_instance = DuplicateFilter(db_path)

        # Upload first to Garmin, others only to MQTT
        filter_instance.mark_as_uploaded(multiple_readings[0], garmin=True, mqtt=True)
        filter_instance.mark_as_uploaded(multiple_readings[1], garmin=False, mqtt=True)
        filter_instance.mark_as_uploaded(multiple_readings[2], garmin=False, mqtt=True)

        pending = filter_instance.get_pending_garmin()
        assert len(pending) == 2

    def test_get_pending_mqtt(self, db_path, multiple_readings):
        """Should return records not published to MQTT."""
        filter_instance = DuplicateFilter(db_path)

        # Publish first to MQTT, others only to Garmin
        filter_instance.mark_as_uploaded(multiple_readings[0], garmin=True, mqtt=True)
        filter_instance.mark_as_uploaded(multiple_readings[1], garmin=True, mqtt=False)
        filter_instance.mark_as_uploaded(multiple_readings[2], garmin=True, mqtt=False)

        pending = filter_instance.get_pending_mqtt()
        assert len(pending) == 2

    def test_clear_all(self, db_path, multiple_readings):
        """Should clear all records."""
        filter_instance = DuplicateFilter(db_path)

        for reading in multiple_readings:
            filter_instance.mark_as_uploaded(reading, garmin=True)

        deleted = filter_instance.clear_all()
        assert deleted == 3

        history = filter_instance.get_history()
        assert len(history) == 0

    def test_record_hash_uniqueness(self, db_path):
        """Different readings should have different hashes."""
        _ = db_path  # Unused but required for fixture
        reading1 = BloodPressureReading(
            timestamp=datetime(2025, 1, 15, 10, 30, 0),
            systolic=120,
            diastolic=80,
            pulse=72,
            user_slot=1,
        )
        reading2 = BloodPressureReading(
            timestamp=datetime(2025, 1, 15, 10, 35, 0),  # Different time
            systolic=120,
            diastolic=80,
            pulse=72,
            user_slot=1,
        )

        assert reading1.record_hash != reading2.record_hash

    def test_same_values_different_user_slots(self, db_path):
        """Same values but different user slots should have different hashes."""
        _ = db_path  # Unused but required for fixture
        reading1 = BloodPressureReading(
            timestamp=datetime(2025, 1, 15, 10, 30, 0),
            systolic=120,
            diastolic=80,
            pulse=72,
            user_slot=1,
        )
        reading2 = BloodPressureReading(
            timestamp=datetime(2025, 1, 15, 10, 30, 0),
            systolic=120,
            diastolic=80,
            pulse=72,
            user_slot=2,  # Different user slot
        )

        assert reading1.record_hash != reading2.record_hash

    def test_stored_record_contains_all_fields(self, db_path, high_bp_reading):
        """All record fields should be stored correctly."""
        filter_instance = DuplicateFilter(db_path)
        filter_instance.mark_as_uploaded(high_bp_reading, garmin=True, mqtt=True)

        history = filter_instance.get_history(limit=1)
        record = history[0]

        assert record["systolic"] == 160
        assert record["diastolic"] == 100
        assert record["pulse"] == 85
        assert record["irregular_heartbeat"] == 1  # SQLite stores as int
        assert record["body_movement"] == 0
        assert record["user_slot"] == 1
        assert record["category"] == "grade2_hypertension"
