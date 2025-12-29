"""Tests for GarminUploader."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.garmin_uploader import GarminUploader
from src.models import BloodPressureReading


@pytest.fixture
def sample_reading():
    """Sample blood pressure reading for tests."""
    return BloodPressureReading(
        timestamp=datetime(2025, 12, 26, 22, 59, 22),
        systolic=139,
        diastolic=83,
        pulse=73,
        irregular_heartbeat=False,
        body_movement=False,
        user_slot=1,
    )


@pytest.fixture
def sample_reading_with_flags():
    """Sample reading with IHB and MOV flags."""
    return BloodPressureReading(
        timestamp=datetime(2025, 12, 26, 12, 26, 0),
        systolic=167,
        diastolic=100,
        pulse=73,
        irregular_heartbeat=True,
        body_movement=True,
        user_slot=1,
    )


@pytest.fixture
def garmin_existing_readings():
    """Mock Garmin API response with existing readings."""
    return [
        {
            "measurementTimestampLocal": "2025-12-26T22:59:22.0",
            "systolic": 139,
            "diastolic": 83,
            "pulse": 73,
            "notes": "OMRON BLE import",
        },
        {
            "measurementTimestampLocal": "2025-12-26T12:16:00.0",
            "systolic": 185,
            "diastolic": 110,
            "pulse": 65,
            "notes": "",
        },
    ]


class TestGarminUploaderInit:
    """Tests for GarminUploader initialization."""

    def test_init_default_tokens_path(self):
        """Test default token path is set."""
        uploader = GarminUploader()
        assert uploader.tokens_path.name == ".garminconnect"
        assert not uploader.is_logged_in

    def test_init_custom_tokens_path(self, tmp_path):
        """Test custom token path."""
        uploader = GarminUploader(tokens_path=str(tmp_path))
        assert uploader.tokens_path == tmp_path
        assert not uploader.is_logged_in


class TestGarminUploaderLogin:
    """Tests for login functionality."""

    def test_login_no_tokens_raises_error(self, tmp_path):
        """Test login fails when no token directory exists."""
        uploader = GarminUploader(tokens_path=str(tmp_path / "nonexistent"))
        with pytest.raises(FileNotFoundError):
            uploader.login()

    @patch("src.garmin_uploader.Garmin")
    def test_login_success(self, mock_garmin_class, tmp_path):
        """Test successful login."""
        # Setup mock
        mock_client = MagicMock()
        mock_client.display_name = "TestUser"
        mock_garmin_class.return_value = mock_client

        # Create token directory
        tmp_path.mkdir(exist_ok=True)

        uploader = GarminUploader(tokens_path=str(tmp_path))
        result = uploader.login()

        assert result is True
        assert uploader.is_logged_in
        mock_client.login.assert_called_once()

    @patch("src.garmin_uploader.Garmin")
    def test_login_with_email(self, mock_garmin_class, tmp_path):
        """Test login with email creates correct token path."""
        mock_client = MagicMock()
        mock_client.display_name = "TestUser"
        mock_garmin_class.return_value = mock_client

        # Create email-specific token directory
        email = "test@example.com"
        email_dir = tmp_path / "test_at_example.com"
        email_dir.mkdir(parents=True)

        uploader = GarminUploader(tokens_path=str(tmp_path))
        uploader.login(email=email)

        assert uploader.is_logged_in
        assert uploader._current_email == email

    def test_logout(self, tmp_path):
        """Test logout clears state."""
        uploader = GarminUploader(tokens_path=str(tmp_path))
        uploader._logged_in = True
        uploader._client = MagicMock()
        uploader._current_email = "test@example.com"

        uploader.logout()

        assert not uploader.is_logged_in
        assert uploader._client is None
        assert uploader._current_email is None


class TestDuplicateDetection:
    """Tests for duplicate detection in Garmin."""

    def test_is_duplicate_exact_match(self, sample_reading, garmin_existing_readings):
        """Test duplicate detection with exact timestamp and values."""
        uploader = GarminUploader()
        uploader._logged_in = True
        uploader._client = MagicMock()

        is_dup = uploader.is_duplicate_in_garmin(sample_reading, garmin_existing_readings)

        assert is_dup is True

    def test_is_duplicate_no_match(self, garmin_existing_readings):
        """Test no duplicate when values differ."""
        uploader = GarminUploader()
        uploader._logged_in = True
        uploader._client = MagicMock()

        # Different values
        reading = BloodPressureReading(
            timestamp=datetime(2025, 12, 26, 22, 59, 22),
            systolic=120,  # Different
            diastolic=80,  # Different
            pulse=70,  # Different
            user_slot=1,
        )

        is_dup = uploader.is_duplicate_in_garmin(reading, garmin_existing_readings)

        assert is_dup is False

    def test_is_duplicate_different_timestamp(self, garmin_existing_readings):
        """Test no duplicate when timestamp differs by more than 1 minute."""
        uploader = GarminUploader()
        uploader._logged_in = True
        uploader._client = MagicMock()

        # Same values but different timestamp
        reading = BloodPressureReading(
            timestamp=datetime(2025, 12, 26, 23, 30, 0),  # 30 min later
            systolic=139,
            diastolic=83,
            pulse=73,
            user_slot=1,
        )

        is_dup = uploader.is_duplicate_in_garmin(reading, garmin_existing_readings)

        assert is_dup is False

    def test_is_duplicate_within_one_minute(self, garmin_existing_readings):
        """Test duplicate detection within 1 minute tolerance."""
        uploader = GarminUploader()
        uploader._logged_in = True
        uploader._client = MagicMock()

        # Same values, 30 seconds different
        reading = BloodPressureReading(
            timestamp=datetime(2025, 12, 26, 22, 59, 52),  # 30 sec later
            systolic=139,
            diastolic=83,
            pulse=73,
            user_slot=1,
        )

        is_dup = uploader.is_duplicate_in_garmin(reading, garmin_existing_readings)

        assert is_dup is True

    def test_is_duplicate_empty_existing(self, sample_reading):
        """Test no duplicate when no existing readings."""
        uploader = GarminUploader()
        uploader._logged_in = True
        uploader._client = MagicMock()

        is_dup = uploader.is_duplicate_in_garmin(sample_reading, [])

        assert is_dup is False


class TestUploadReading:
    """Tests for uploading readings."""

    @patch("src.garmin_uploader.Garmin")
    def test_upload_reading_success(self, mock_garmin_class, sample_reading):
        """Test successful upload."""
        mock_client = MagicMock()
        mock_garmin_class.return_value = mock_client

        uploader = GarminUploader()
        uploader._client = mock_client
        uploader._logged_in = True

        result = uploader.upload_reading(sample_reading, check_duplicate=False)

        assert result is True
        mock_client.set_blood_pressure.assert_called_once_with(
            systolic=139,
            diastolic=83,
            pulse=73,
            timestamp=sample_reading.timestamp.isoformat(),
            notes="OMRON BLE import (slot 1)",
        )

    @patch("src.garmin_uploader.Garmin")
    def test_upload_reading_with_flags(self, mock_garmin_class, sample_reading_with_flags):
        """Test upload includes IHB and MOV in notes."""
        mock_client = MagicMock()
        mock_garmin_class.return_value = mock_client

        uploader = GarminUploader()
        uploader._client = mock_client
        uploader._logged_in = True

        uploader.upload_reading(sample_reading_with_flags, check_duplicate=False)

        call_args = mock_client.set_blood_pressure.call_args
        notes = call_args.kwargs["notes"]
        assert "IHB detected" in notes
        assert "Body movement detected" in notes

    @patch("src.garmin_uploader.Garmin")
    def test_upload_reading_skips_duplicate(
        self, mock_garmin_class, sample_reading, garmin_existing_readings
    ):
        """Test upload skips duplicate."""
        mock_client = MagicMock()
        mock_garmin_class.return_value = mock_client

        uploader = GarminUploader()
        uploader._client = mock_client
        uploader._logged_in = True

        result = uploader.upload_reading(
            sample_reading,
            check_duplicate=True,
            existing_readings=garmin_existing_readings,
        )

        assert result is False
        mock_client.set_blood_pressure.assert_not_called()

    def test_upload_reading_not_logged_in(self, sample_reading):
        """Test upload fails when not logged in."""
        uploader = GarminUploader()

        with pytest.raises(RuntimeError, match="Not logged in"):
            uploader.upload_reading(sample_reading)


class TestUploadReadings:
    """Tests for batch upload."""

    @patch("src.garmin_uploader.Garmin")
    def test_upload_readings_batch(self, mock_garmin_class):
        """Test batch upload with mixed duplicates."""
        mock_client = MagicMock()
        # Garmin API returns nested structure: measurementSummaries[].measurements[]
        mock_client.get_blood_pressure.return_value = {
            "measurementSummaries": [
                {
                    "startDate": "2025-12-26",
                    "measurements": [
                        {
                            "measurementTimestampLocal": "2025-12-26T10:00:00.0",
                            "systolic": 120,
                            "diastolic": 80,
                            "pulse": 70,
                        }
                    ],
                }
            ]
        }
        mock_garmin_class.return_value = mock_client

        uploader = GarminUploader()
        uploader._client = mock_client
        uploader._logged_in = True

        readings = [
            # This one exists (duplicate)
            BloodPressureReading(
                timestamp=datetime(2025, 12, 26, 10, 0, 0),
                systolic=120,
                diastolic=80,
                pulse=70,
                user_slot=1,
            ),
            # This one is new
            BloodPressureReading(
                timestamp=datetime(2025, 12, 26, 12, 0, 0),
                systolic=130,
                diastolic=85,
                pulse=75,
                user_slot=1,
            ),
        ]

        uploaded, skipped = uploader.upload_readings(readings, check_duplicates=True)

        assert uploaded == 1
        assert skipped == 1
        assert mock_client.set_blood_pressure.call_count == 1

    @patch("src.garmin_uploader.Garmin")
    def test_upload_readings_empty_list(self, mock_garmin_class):
        """Test upload with empty list."""
        mock_client = MagicMock()
        mock_garmin_class.return_value = mock_client

        uploader = GarminUploader()
        uploader._client = mock_client
        uploader._logged_in = True

        uploaded, skipped = uploader.upload_readings([])

        assert uploaded == 0
        assert skipped == 0


class TestFilterNewReadings:
    """Tests for filtering new readings."""

    @patch("src.garmin_uploader.Garmin")
    def test_filter_new_readings(self, mock_garmin_class, garmin_existing_readings):
        """Test filtering removes existing readings."""
        mock_client = MagicMock()
        # Garmin API returns nested structure: measurementSummaries[].measurements[]
        mock_client.get_blood_pressure.return_value = {
            "measurementSummaries": [
                {
                    "startDate": "2025-12-26",
                    "measurements": garmin_existing_readings,
                }
            ]
        }
        mock_garmin_class.return_value = mock_client

        uploader = GarminUploader()
        uploader._client = mock_client
        uploader._logged_in = True

        readings = [
            # This one exists
            BloodPressureReading(
                timestamp=datetime(2025, 12, 26, 22, 59, 22),
                systolic=139,
                diastolic=83,
                pulse=73,
                user_slot=1,
            ),
            # This one is new
            BloodPressureReading(
                timestamp=datetime(2025, 12, 26, 23, 30, 0),
                systolic=125,
                diastolic=82,
                pulse=68,
                user_slot=1,
            ),
        ]

        new_readings = uploader.filter_new_readings(readings)

        assert len(new_readings) == 1
        assert new_readings[0].systolic == 125

    def test_filter_empty_list(self):
        """Test filter with empty list."""
        uploader = GarminUploader()
        uploader._logged_in = True
        uploader._client = MagicMock()

        result = uploader.filter_new_readings([])

        assert result == []
