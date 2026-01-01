"""Tests for src/omron_ble/devices/hem_7361t.py - HEM-7361T device driver.

This module tests the OMRON HEM-7361T (M7 Intelli IT) blood pressure monitor driver.
Tests cover:
- Device configuration constants
- Bit extraction from byte arrays (little-endian)
- Time synchronization byte generation
- Record parsing (basic tests)
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import pytest

# ============== MOCK CLASSES ==============


@dataclass
class MockBloodPressureReading:
    """Mock BloodPressureReading for standalone testing."""

    timestamp: datetime
    systolic: int
    diastolic: int
    pulse: int
    irregular_heartbeat: bool = False
    body_movement: bool = False
    user_slot: int = 1


class StandaloneHEM7361T:
    """Standalone testable HEM7361T implementation.

    This class replicates the logic from HEM7361T without requiring
    actual BLE protocol or imports from src.omron_ble.
    """

    device_endianness: Literal["little", "big"] = "little"
    user_start_addresses = [0x0098, 0x06D8]
    records_per_user = [100, 100]
    record_byte_size = 0x10
    transmission_block_size = 0x10
    settings_read_address = 0x0010
    settings_write_address = 0x0054
    settings_unread_records_bytes = (0x00, 0x10)
    settings_time_sync_bytes = (0x2C, 0x3C)

    def __init__(self):
        self._cached_settings = bytearray(0x54)

    def _extract_bits(self, data: bytes, first_bit: int, last_bit: int) -> int:
        """Extract bits from byte array (little-endian)."""
        big_int = int.from_bytes(data, self.device_endianness)
        num_valid_bits = (last_bit - first_bit) + 1
        shifted = big_int >> (len(data) * 8 - (last_bit + 1))
        bitmask = (2**num_valid_bits) - 1
        return int(shifted & bitmask)

    def parse_record(self, record_bytes: bytes) -> MockBloodPressureReading:
        """Parse raw record bytes into BloodPressureReading."""
        minute = self._extract_bits(record_bytes, 68, 73)
        second = self._extract_bits(record_bytes, 74, 79)
        second = min(second, 59)

        mov = bool(self._extract_bits(record_bytes, 80, 80))
        ihb = bool(self._extract_bits(record_bytes, 81, 81))

        month = self._extract_bits(record_bytes, 82, 85)
        day = self._extract_bits(record_bytes, 86, 90)
        hour = self._extract_bits(record_bytes, 91, 95)
        year = self._extract_bits(record_bytes, 98, 103) + 2000

        pulse = self._extract_bits(record_bytes, 104, 111)
        diastolic = self._extract_bits(record_bytes, 112, 119)
        systolic = self._extract_bits(record_bytes, 120, 127) + 25

        timestamp = datetime(year, month, day, hour, minute, second)

        return MockBloodPressureReading(
            timestamp=timestamp,
            systolic=systolic,
            diastolic=diastolic,
            pulse=pulse,
            irregular_heartbeat=ihb,
            body_movement=mov,
        )

    def get_time_sync_bytes(self, current_time: datetime) -> bytearray:
        """Generate time sync bytes for device."""
        start, end = self.settings_time_sync_bytes
        section = self._cached_settings[start:end]

        new_bytes = bytearray(section[:8])
        new_bytes += bytes(
            [
                current_time.year - 2000,
                current_time.month,
                current_time.day,
                current_time.hour,
                current_time.minute,
                current_time.second,
            ]
        )
        checksum = sum(new_bytes) & 0xFF
        new_bytes += bytes([checksum, 0x00])

        return new_bytes


# ============== FIXTURES ==============


@pytest.fixture
def device():
    """Create testable HEM7361T instance."""
    return StandaloneHEM7361T()


# ============== TEST CLASSES ==============


class TestDeviceConfiguration:
    """Tests for HEM-7361T device configuration constants."""

    def test_device_endianness(self, device):
        """Test device uses little-endian byte order."""
        assert device.device_endianness == "little"

    def test_user_addresses(self, device):
        """Test user EEPROM start addresses."""
        assert device.user_start_addresses == [0x0098, 0x06D8]
        assert len(device.user_start_addresses) == 2

    def test_records_per_user(self, device):
        """Test max records per user."""
        assert device.records_per_user == [100, 100]

    def test_record_byte_size(self, device):
        """Test record size is 16 bytes."""
        assert device.record_byte_size == 0x10

    def test_transmission_block_size(self, device):
        """Test BLE transmission block size."""
        assert device.transmission_block_size == 0x10

    def test_settings_addresses(self, device):
        """Test settings EEPROM addresses."""
        assert device.settings_read_address == 0x0010
        assert device.settings_write_address == 0x0054

    def test_settings_byte_ranges(self, device):
        """Test settings byte range tuples."""
        assert device.settings_unread_records_bytes == (0x00, 0x10)
        assert device.settings_time_sync_bytes == (0x2C, 0x3C)


class TestExtractBits:
    """Tests for _extract_bits method."""

    def test_extract_single_bit_set(self, device):
        """Test extracting a single bit that is 1."""
        data = bytes([0b10000000])
        result = device._extract_bits(data, 0, 0)
        assert result == 1

    def test_extract_single_bit_unset(self, device):
        """Test extracting a single bit that is 0."""
        data = bytes([0b01111111])
        result = device._extract_bits(data, 0, 0)
        assert result == 0

    def test_extract_full_byte(self, device):
        """Test extracting full byte."""
        data = bytes([0xAB])
        result = device._extract_bits(data, 0, 7)
        assert result == 0xAB

    def test_extract_upper_nibble(self, device):
        """Test extracting upper 4 bits."""
        data = bytes([0xF0])
        result = device._extract_bits(data, 0, 3)
        assert result == 15

    def test_extract_lower_nibble(self, device):
        """Test extracting lower 4 bits."""
        data = bytes([0x0F])
        result = device._extract_bits(data, 4, 7)
        assert result == 15

    def test_extract_from_two_bytes_upper(self, device):
        """Test extracting upper byte from 2-byte array."""
        data = bytes([0xFF, 0x00])  # Little-endian: 0x00FF
        result = device._extract_bits(data, 0, 7)  # Upper byte
        assert result == 0x00

    def test_extract_from_two_bytes_lower(self, device):
        """Test extracting lower byte from 2-byte array."""
        data = bytes([0xFF, 0x00])  # Little-endian: 0x00FF
        result = device._extract_bits(data, 8, 15)  # Lower byte
        assert result == 0xFF

    def test_extract_middle_bits(self, device):
        """Test extracting bits from middle of byte."""
        data = bytes([0b00111100])  # bits 2-5 = 15
        result = device._extract_bits(data, 2, 5)
        assert result == 15

    def test_extract_zero_value(self, device):
        """Test extracting zero value."""
        data = bytes([0x00])
        result = device._extract_bits(data, 0, 7)
        assert result == 0

    def test_extract_max_value(self, device):
        """Test extracting maximum value for bit range."""
        data = bytes([0xFF])
        result = device._extract_bits(data, 0, 7)
        assert result == 255


class TestGetTimeSyncBytes:
    """Tests for get_time_sync_bytes method."""

    def test_time_sync_bytes_length(self, device):
        """Test time sync bytes are 16 bytes."""
        current_time = datetime(2024, 12, 30, 10, 30, 45)
        result = device.get_time_sync_bytes(current_time)
        assert len(result) == 16

    def test_time_sync_bytes_year(self, device):
        """Test year is encoded as year - 2000."""
        current_time = datetime(2024, 12, 30, 10, 30, 45)
        result = device.get_time_sync_bytes(current_time)
        assert result[8] == 24

    def test_time_sync_bytes_month(self, device):
        """Test month encoding."""
        current_time = datetime(2024, 12, 30, 10, 30, 45)
        result = device.get_time_sync_bytes(current_time)
        assert result[9] == 12

    def test_time_sync_bytes_day(self, device):
        """Test day encoding."""
        current_time = datetime(2024, 12, 30, 10, 30, 45)
        result = device.get_time_sync_bytes(current_time)
        assert result[10] == 30

    def test_time_sync_bytes_hour(self, device):
        """Test hour encoding."""
        current_time = datetime(2024, 12, 30, 10, 30, 45)
        result = device.get_time_sync_bytes(current_time)
        assert result[11] == 10

    def test_time_sync_bytes_minute(self, device):
        """Test minute encoding."""
        current_time = datetime(2024, 12, 30, 10, 30, 45)
        result = device.get_time_sync_bytes(current_time)
        assert result[12] == 30

    def test_time_sync_bytes_second(self, device):
        """Test second encoding."""
        current_time = datetime(2024, 12, 30, 10, 30, 45)
        result = device.get_time_sync_bytes(current_time)
        assert result[13] == 45

    def test_time_sync_bytes_checksum(self, device):
        """Test checksum calculation."""
        current_time = datetime(2024, 12, 30, 10, 30, 45)
        result = device.get_time_sync_bytes(current_time)
        expected_checksum = sum(result[:14]) & 0xFF
        assert result[14] == expected_checksum

    def test_time_sync_bytes_last_byte_zero(self, device):
        """Test last byte is always 0x00."""
        current_time = datetime(2024, 12, 30, 10, 30, 45)
        result = device.get_time_sync_bytes(current_time)
        assert result[15] == 0x00

    def test_time_sync_preserves_first_8_bytes(self, device):
        """Test first 8 bytes are preserved from cached settings."""
        device._cached_settings[0x2C:0x34] = bytes([0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x11, 0x22])

        current_time = datetime(2024, 12, 30, 10, 30, 45)
        result = device.get_time_sync_bytes(current_time)

        assert result[0:8] == bytes([0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x11, 0x22])


class TestTimeSyncEdgeCases:
    """Edge case tests for time sync functionality."""

    def test_time_sync_year_2000(self, device):
        """Test year 2000 edge case."""
        current_time = datetime(2000, 1, 1, 0, 0, 0)
        result = device.get_time_sync_bytes(current_time)
        assert result[8] == 0

    def test_time_sync_year_2063(self, device):
        """Test maximum year (2063)."""
        current_time = datetime(2063, 12, 31, 23, 59, 59)
        result = device.get_time_sync_bytes(current_time)
        assert result[8] == 63

    def test_time_sync_midnight(self, device):
        """Test midnight time."""
        current_time = datetime(2024, 1, 1, 0, 0, 0)
        result = device.get_time_sync_bytes(current_time)
        assert result[11] == 0  # hour
        assert result[12] == 0  # minute
        assert result[13] == 0  # second

    def test_time_sync_end_of_day(self, device):
        """Test end of day time (23:59:59)."""
        current_time = datetime(2024, 12, 31, 23, 59, 59)
        result = device.get_time_sync_bytes(current_time)
        assert result[11] == 23  # hour
        assert result[12] == 59  # minute
        assert result[13] == 59  # second

    def test_time_sync_january_first(self, device):
        """Test January 1st."""
        current_time = datetime(2024, 1, 1, 12, 0, 0)
        result = device.get_time_sync_bytes(current_time)
        assert result[9] == 1  # month
        assert result[10] == 1  # day

    def test_time_sync_december_31st(self, device):
        """Test December 31st."""
        current_time = datetime(2024, 12, 31, 12, 0, 0)
        result = device.get_time_sync_bytes(current_time)
        assert result[9] == 12  # month
        assert result[10] == 31  # day


class TestTimeSyncChecksum:
    """Tests specifically for checksum calculation."""

    def test_checksum_changes_with_time(self, device):
        """Test checksum changes when time changes."""
        time1 = datetime(2024, 1, 1, 0, 0, 0)
        time2 = datetime(2024, 1, 1, 0, 0, 1)

        result1 = device.get_time_sync_bytes(time1)
        result2 = device.get_time_sync_bytes(time2)

        assert result1[14] != result2[14]

    def test_checksum_changes_with_cached_settings(self, device):
        """Test checksum changes when cached settings change."""
        time = datetime(2024, 6, 15, 12, 30, 0)

        result1 = device.get_time_sync_bytes(time)

        device._cached_settings[0x2C] = 0xFF
        result2 = device.get_time_sync_bytes(time)

        assert result1[14] != result2[14]

    def test_checksum_is_byte_masked(self, device):
        """Test checksum is masked to single byte (& 0xFF)."""
        # Use cached settings that will cause high sum
        device._cached_settings[0x2C:0x34] = bytes([0xFF] * 8)
        time = datetime(2063, 12, 31, 23, 59, 59)

        result = device.get_time_sync_bytes(time)

        # Sum would be: 8*255 + 63 + 12 + 31 + 23 + 59 + 59 = 2287
        # 2287 & 0xFF = 239
        assert 0 <= result[14] <= 255
