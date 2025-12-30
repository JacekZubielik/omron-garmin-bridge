"""Tests for src/models.py - BloodPressureReading dataclass."""

from datetime import datetime

import pytest

from src.models import BloodPressureReading

# ============== FIXTURES ==============


@pytest.fixture
def sample_timestamp():
    """Standard timestamp for tests."""
    return datetime(2024, 12, 30, 10, 30, 0)


@pytest.fixture
def optimal_reading(sample_timestamp):
    """Optimal BP reading (< 120/80)."""
    return BloodPressureReading(
        timestamp=sample_timestamp,
        systolic=110,
        diastolic=70,
        pulse=65,
    )


@pytest.fixture
def hypertensive_reading(sample_timestamp):
    """Grade 3 hypertension reading (>= 180/110)."""
    return BloodPressureReading(
        timestamp=sample_timestamp,
        systolic=190,
        diastolic=120,
        pulse=90,
        irregular_heartbeat=True,
        body_movement=True,
        user_slot=2,
    )


# ============== TEST CLASSES ==============


class TestBloodPressureReadingCreation:
    """Tests for BloodPressureReading dataclass creation."""

    def test_create_minimal_reading(self, sample_timestamp):
        """Test creating reading with required fields only."""
        reading = BloodPressureReading(
            timestamp=sample_timestamp,
            systolic=120,
            diastolic=80,
            pulse=72,
        )
        assert reading.systolic == 120
        assert reading.diastolic == 80
        assert reading.pulse == 72
        assert reading.irregular_heartbeat is False
        assert reading.body_movement is False
        assert reading.user_slot == 1

    def test_create_full_reading(self, sample_timestamp):
        """Test creating reading with all fields."""
        reading = BloodPressureReading(
            timestamp=sample_timestamp,
            systolic=145,
            diastolic=95,
            pulse=85,
            irregular_heartbeat=True,
            body_movement=True,
            user_slot=2,
        )
        assert reading.systolic == 145
        assert reading.diastolic == 95
        assert reading.pulse == 85
        assert reading.irregular_heartbeat is True
        assert reading.body_movement is True
        assert reading.user_slot == 2


class TestBloodPressureCategory:
    """Tests for category property (WHO/ESC classification)."""

    @pytest.mark.parametrize(
        "systolic,diastolic,expected_category",
        [
            # Optimal: < 120 and < 80
            (110, 70, "optimal"),
            (119, 79, "optimal"),
            (100, 60, "optimal"),
            # Normal: < 130 and < 85 (but not optimal)
            (120, 80, "normal"),
            (125, 82, "normal"),
            (129, 84, "normal"),
            # High Normal: < 140 and < 90 (but not normal)
            (130, 85, "high_normal"),
            (135, 87, "high_normal"),
            (139, 89, "high_normal"),
            # Grade 1 Hypertension: < 160 and < 100
            (140, 90, "grade1_hypertension"),
            (150, 95, "grade1_hypertension"),
            (159, 99, "grade1_hypertension"),
            # Grade 2 Hypertension: < 180 and < 110
            (160, 100, "grade2_hypertension"),
            (170, 105, "grade2_hypertension"),
            (179, 109, "grade2_hypertension"),
            # Grade 3 Hypertension: >= 180 or >= 110
            (180, 110, "grade3_hypertension"),
            (200, 120, "grade3_hypertension"),
            (220, 130, "grade3_hypertension"),
        ],
    )
    def test_category_classification(
        self, sample_timestamp, systolic, diastolic, expected_category
    ):
        """Test BP category classification for various values."""
        reading = BloodPressureReading(
            timestamp=sample_timestamp,
            systolic=systolic,
            diastolic=diastolic,
            pulse=72,
        )
        assert reading.category == expected_category

    def test_category_edge_case_systolic_only_high(self, sample_timestamp):
        """Test when only systolic is high (isolated systolic hypertension)."""
        reading = BloodPressureReading(
            timestamp=sample_timestamp,
            systolic=180,
            diastolic=70,  # Normal diastolic
            pulse=72,
        )
        assert reading.category == "grade3_hypertension"

    def test_category_edge_case_diastolic_only_high(self, sample_timestamp):
        """Test when only diastolic is high."""
        reading = BloodPressureReading(
            timestamp=sample_timestamp,
            systolic=110,  # Normal systolic
            diastolic=110,  # High diastolic
            pulse=72,
        )
        assert reading.category == "grade3_hypertension"


class TestRecordHash:
    """Tests for record_hash property (deduplication)."""

    def test_record_hash_format(self, optimal_reading):
        """Test hash contains all identifying fields."""
        hash_value = optimal_reading.record_hash
        assert "2024-12-30T10:30:00" in hash_value
        assert "110" in hash_value
        assert "70" in hash_value
        assert "65" in hash_value
        assert "_1" in hash_value  # user_slot

    def test_record_hash_uniqueness(self, sample_timestamp):
        """Test different readings produce different hashes."""
        reading1 = BloodPressureReading(
            timestamp=sample_timestamp,
            systolic=120,
            diastolic=80,
            pulse=72,
        )
        reading2 = BloodPressureReading(
            timestamp=sample_timestamp,
            systolic=121,
            diastolic=80,
            pulse=72,  # Different systolic
        )
        assert reading1.record_hash != reading2.record_hash

    def test_record_hash_same_values_same_hash(self, sample_timestamp):
        """Test identical readings produce same hash."""
        reading1 = BloodPressureReading(
            timestamp=sample_timestamp,
            systolic=120,
            diastolic=80,
            pulse=72,
        )
        reading2 = BloodPressureReading(
            timestamp=sample_timestamp,
            systolic=120,
            diastolic=80,
            pulse=72,
        )
        assert reading1.record_hash == reading2.record_hash

    def test_record_hash_different_user_slots(self, sample_timestamp):
        """Test different user slots produce different hashes."""
        reading1 = BloodPressureReading(
            timestamp=sample_timestamp,
            systolic=120,
            diastolic=80,
            pulse=72,
            user_slot=1,
        )
        reading2 = BloodPressureReading(
            timestamp=sample_timestamp,
            systolic=120,
            diastolic=80,
            pulse=72,
            user_slot=2,
        )
        assert reading1.record_hash != reading2.record_hash


class TestToDict:
    """Tests for to_dict method (JSON serialization)."""

    def test_to_dict_contains_all_fields(self, optimal_reading):
        """Test dict contains all required fields."""
        result = optimal_reading.to_dict()

        assert "timestamp" in result
        assert "systolic" in result
        assert "diastolic" in result
        assert "pulse" in result
        assert "category" in result
        assert "irregular_heartbeat" in result
        assert "body_movement" in result
        assert "user_slot" in result

    def test_to_dict_values(self, optimal_reading):
        """Test dict values are correct."""
        result = optimal_reading.to_dict()

        assert result["timestamp"] == "2024-12-30T10:30:00"
        assert result["systolic"] == 110
        assert result["diastolic"] == 70
        assert result["pulse"] == 65
        assert result["category"] == "optimal"
        assert result["irregular_heartbeat"] is False
        assert result["body_movement"] is False
        assert result["user_slot"] == 1

    def test_to_dict_with_flags(self, hypertensive_reading):
        """Test dict with flags set to True."""
        result = hypertensive_reading.to_dict()

        assert result["irregular_heartbeat"] is True
        assert result["body_movement"] is True
        assert result["user_slot"] == 2
        assert result["category"] == "grade3_hypertension"


class TestStrRepresentation:
    """Tests for __str__ method."""

    def test_str_format(self, optimal_reading):
        """Test string representation format."""
        result = str(optimal_reading)

        assert "110/70" in result
        assert "mmHg" in result
        assert "65" in result
        assert "bpm" in result
        assert "optimal" in result

    def test_str_hypertensive(self, hypertensive_reading):
        """Test string for hypertensive reading."""
        result = str(hypertensive_reading)

        assert "190/120" in result
        assert "grade3_hypertension" in result
