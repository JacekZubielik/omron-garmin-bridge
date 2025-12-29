"""Shared pytest fixtures for omron-garmin-bridge tests."""

from datetime import datetime

import pytest

from src.models import BloodPressureReading


@pytest.fixture
def sample_reading() -> BloodPressureReading:
    """Create a sample blood pressure reading for testing."""
    return BloodPressureReading(
        timestamp=datetime(2025, 1, 15, 10, 30, 0),
        systolic=120,
        diastolic=80,
        pulse=72,
        irregular_heartbeat=False,
        body_movement=False,
        user_slot=1,
    )


@pytest.fixture
def sample_reading_user2() -> BloodPressureReading:
    """Create a sample reading for user slot 2."""
    return BloodPressureReading(
        timestamp=datetime(2025, 1, 15, 11, 0, 0),
        systolic=130,
        diastolic=85,
        pulse=68,
        irregular_heartbeat=False,
        body_movement=False,
        user_slot=2,
    )


@pytest.fixture
def high_bp_reading() -> BloodPressureReading:
    """Create a high blood pressure reading."""
    return BloodPressureReading(
        timestamp=datetime(2025, 1, 15, 12, 0, 0),
        systolic=160,
        diastolic=100,
        pulse=85,
        irregular_heartbeat=True,
        body_movement=False,
        user_slot=1,
    )


@pytest.fixture
def multiple_readings() -> list[BloodPressureReading]:
    """Create multiple readings for testing."""
    return [
        BloodPressureReading(
            timestamp=datetime(2025, 1, 15, 8, 0, 0),
            systolic=118,
            diastolic=78,
            pulse=70,
            user_slot=1,
        ),
        BloodPressureReading(
            timestamp=datetime(2025, 1, 15, 12, 0, 0),
            systolic=122,
            diastolic=82,
            pulse=74,
            user_slot=1,
        ),
        BloodPressureReading(
            timestamp=datetime(2025, 1, 15, 20, 0, 0),
            systolic=125,
            diastolic=80,
            pulse=68,
            user_slot=1,
        ),
    ]


@pytest.fixture
def db_path(tmp_path) -> str:
    """Create a temporary database path for testing."""
    return str(tmp_path / "test_omron.db")
