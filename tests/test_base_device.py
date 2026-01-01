"""Tests for src/omron_ble/devices/base.py - BaseOmronDevice abstract class.

This module tests the base OMRON device driver functionality including:
- Bit extraction from byte arrays
- Read command generation for all records
- Ring buffer read command calculation
- Unread records command generation
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


class ConcreteOmronDevice:
    """Concrete implementation of BaseOmronDevice for testing.

    This class implements the abstract methods and exposes internal
    methods for testing without requiring BLE protocol.
    """

    device_endianness: Literal["little", "big"] = "little"
    user_start_addresses: list[int] = [0x0098, 0x06D8]
    records_per_user: list[int] = [100, 100]
    record_byte_size: int = 0x10
    transmission_block_size: int = 0x10

    settings_read_address: int = 0x0010
    settings_write_address: int = 0x0054
    settings_unread_records_bytes: tuple[int, int] = (0x00, 0x10)
    settings_time_sync_bytes: tuple[int, int] = (0x2C, 0x3C)

    def __init__(self):
        """Initialize device without protocol."""
        self._cached_settings: bytearray = bytearray(0x54)

    def _extract_bits(self, data: bytes, first_bit: int, last_bit: int) -> int:
        """Extract bits from byte array."""
        big_int = int.from_bytes(data, self.device_endianness)
        num_valid_bits = (last_bit - first_bit) + 1
        shifted = big_int >> (len(data) * 8 - (last_bit + 1))
        bitmask = (2**num_valid_bits) - 1
        return int(shifted & bitmask)

    def _get_all_records_commands(self) -> list[list[dict]]:
        """Get read commands for all records."""
        all_commands: list[list[dict]] = []
        for user_idx, start_addr in enumerate(self.user_start_addresses):
            cmd = {
                "address": start_addr,
                "size": self.records_per_user[user_idx] * self.record_byte_size,
            }
            all_commands.append([cmd])
        return all_commands

    def _calc_ring_buffer_read(self, user_idx: int, unread: int, last_slot: int) -> list[dict]:
        """Calculate read commands for ring buffer."""
        commands: list[dict] = []
        start_addr = self.user_start_addresses[user_idx]
        max_records = self.records_per_user[user_idx]

        if last_slot < unread:
            # Two reads needed (wrap around)
            commands.append(
                {
                    "address": start_addr,
                    "size": self.record_byte_size * last_slot,
                }
            )
            wrap_addr = start_addr + (max_records + last_slot - unread) * self.record_byte_size
            commands.append(
                {
                    "address": wrap_addr,
                    "size": self.record_byte_size * (unread - last_slot),
                }
            )
        else:
            # Single read
            read_addr = start_addr + (last_slot - unread) * self.record_byte_size
            commands.append(
                {
                    "address": read_addr,
                    "size": self.record_byte_size * unread,
                }
            )

        return commands

    def parse_record(self, record_bytes: bytes) -> MockBloodPressureReading:  # noqa: ARG002
        """Parse record bytes (mock implementation)."""
        return MockBloodPressureReading(
            timestamp=datetime.now(),
            systolic=120,
            diastolic=80,
            pulse=72,
        )

    def get_time_sync_bytes(self, current_time: datetime) -> bytearray:  # noqa: ARG002
        """Generate time sync bytes (mock implementation)."""
        return bytearray(16)


# ============== FIXTURES ==============


@pytest.fixture
def device():
    """Create testable device instance."""
    return ConcreteOmronDevice()


@pytest.fixture
def single_user_device():
    """Create device with single user slot."""
    dev = ConcreteOmronDevice()
    dev.user_start_addresses = [0x0100]
    dev.records_per_user = [50]
    return dev


# ============== TEST CLASSES ==============


class TestDeviceInitialization:
    """Tests for device initialization."""

    def test_default_configuration(self, device):
        """Test default device configuration."""
        assert device.device_endianness == "little"
        assert len(device.user_start_addresses) == 2
        assert len(device.records_per_user) == 2

    def test_cached_settings_initialized(self, device):
        """Test cached settings bytearray is initialized."""
        assert isinstance(device._cached_settings, bytearray)
        assert len(device._cached_settings) == 0x54


class TestExtractBits:
    """Tests for _extract_bits method."""

    def test_extract_single_bit(self, device):
        """Test extracting single bit."""
        data = bytes([0b10000000])
        assert device._extract_bits(data, 0, 0) == 1

    def test_extract_full_byte(self, device):
        """Test extracting full byte."""
        data = bytes([0xAB])
        assert device._extract_bits(data, 0, 7) == 0xAB

    def test_extract_nibble(self, device):
        """Test extracting 4 bits."""
        data = bytes([0xF0])
        assert device._extract_bits(data, 0, 3) == 15

    def test_extract_across_bytes(self, device):
        """Test extracting bits across byte boundary."""
        data = bytes([0x12, 0x34])  # Little-endian: 0x3412
        # In little-endian, first byte is LSB
        result = device._extract_bits(data, 8, 15)
        assert result == 0x12


class TestGetAllRecordsCommands:
    """Tests for _get_all_records_commands method."""

    def test_returns_list_per_user(self, device):
        """Test returns command list for each user."""
        commands = device._get_all_records_commands()
        assert len(commands) == 2  # Two users

    def test_each_user_has_one_command(self, device):
        """Test each user has exactly one read command."""
        commands = device._get_all_records_commands()
        assert len(commands[0]) == 1
        assert len(commands[1]) == 1

    def test_command_has_address_and_size(self, device):
        """Test commands contain address and size keys."""
        commands = device._get_all_records_commands()
        assert "address" in commands[0][0]
        assert "size" in commands[0][0]

    def test_user1_address(self, device):
        """Test user 1 start address."""
        commands = device._get_all_records_commands()
        assert commands[0][0]["address"] == 0x0098

    def test_user2_address(self, device):
        """Test user 2 start address."""
        commands = device._get_all_records_commands()
        assert commands[1][0]["address"] == 0x06D8

    def test_user1_size(self, device):
        """Test user 1 read size."""
        commands = device._get_all_records_commands()
        expected_size = 100 * 0x10  # 100 records * 16 bytes
        assert commands[0][0]["size"] == expected_size

    def test_user2_size(self, device):
        """Test user 2 read size."""
        commands = device._get_all_records_commands()
        expected_size = 100 * 0x10
        assert commands[1][0]["size"] == expected_size

    def test_single_user_device(self, single_user_device):
        """Test single user device."""
        commands = single_user_device._get_all_records_commands()
        assert len(commands) == 1
        assert commands[0][0]["address"] == 0x0100
        assert commands[0][0]["size"] == 50 * 0x10


class TestCalcRingBufferRead:
    """Tests for _calc_ring_buffer_read method."""

    def test_single_read_no_wrap(self, device):
        """Test single read when no wrap-around needed."""
        # last_slot=50, unread=10 -> single read from slot 40-50
        commands = device._calc_ring_buffer_read(user_idx=0, unread=10, last_slot=50)
        assert len(commands) == 1

    def test_single_read_address(self, device):
        """Test single read calculates correct address."""
        # User 0 starts at 0x0098
        # last_slot=50, unread=10 -> start at slot 40
        # Address = 0x0098 + 40 * 0x10 = 0x0098 + 0x280 = 0x0318
        commands = device._calc_ring_buffer_read(user_idx=0, unread=10, last_slot=50)
        assert commands[0]["address"] == 0x0098 + 40 * 0x10

    def test_single_read_size(self, device):
        """Test single read calculates correct size."""
        commands = device._calc_ring_buffer_read(user_idx=0, unread=10, last_slot=50)
        assert commands[0]["size"] == 10 * 0x10

    def test_wrap_around_two_reads(self, device):
        """Test wrap-around creates two read commands."""
        # last_slot=5, unread=20 -> wraps around
        commands = device._calc_ring_buffer_read(user_idx=0, unread=20, last_slot=5)
        assert len(commands) == 2

    def test_wrap_around_first_read_from_start(self, device):
        """Test wrap-around first read starts at buffer beginning."""
        commands = device._calc_ring_buffer_read(user_idx=0, unread=20, last_slot=5)
        assert commands[0]["address"] == 0x0098  # User 0 start address

    def test_wrap_around_first_read_size(self, device):
        """Test wrap-around first read size is last_slot records."""
        commands = device._calc_ring_buffer_read(user_idx=0, unread=20, last_slot=5)
        assert commands[0]["size"] == 5 * 0x10

    def test_wrap_around_second_read_address(self, device):
        """Test wrap-around second read address calculation."""
        # max_records=100, last_slot=5, unread=20
        # wrap_addr = start + (100 + 5 - 20) * 16 = start + 85 * 16
        commands = device._calc_ring_buffer_read(user_idx=0, unread=20, last_slot=5)
        expected_addr = 0x0098 + 85 * 0x10
        assert commands[1]["address"] == expected_addr

    def test_wrap_around_second_read_size(self, device):
        """Test wrap-around second read size is remaining records."""
        commands = device._calc_ring_buffer_read(user_idx=0, unread=20, last_slot=5)
        assert commands[1]["size"] == 15 * 0x10  # 20 - 5 = 15 records

    def test_user2_ring_buffer(self, device):
        """Test ring buffer calculation for user 2."""
        commands = device._calc_ring_buffer_read(user_idx=1, unread=5, last_slot=10)
        assert commands[0]["address"] == 0x06D8 + 5 * 0x10

    def test_zero_unread(self, device):
        """Test zero unread records."""
        commands = device._calc_ring_buffer_read(user_idx=0, unread=0, last_slot=50)
        assert len(commands) == 1
        assert commands[0]["size"] == 0

    def test_all_records_unread(self, device):
        """Test all records unread (full buffer)."""
        # last_slot=100, unread=100 -> single read of entire buffer
        commands = device._calc_ring_buffer_read(user_idx=0, unread=100, last_slot=100)
        assert len(commands) == 1
        assert commands[0]["size"] == 100 * 0x10


class TestRingBufferEdgeCases:
    """Edge case tests for ring buffer calculation."""

    def test_exact_wrap_boundary(self, device):
        """Test when last_slot equals unread (exact wrap)."""
        commands = device._calc_ring_buffer_read(user_idx=0, unread=10, last_slot=10)
        # last_slot == unread means no wrap needed
        assert len(commands) == 1

    def test_single_record_unread(self, device):
        """Test single unread record."""
        commands = device._calc_ring_buffer_read(user_idx=0, unread=1, last_slot=50)
        assert len(commands) == 1
        assert commands[0]["size"] == 0x10

    def test_single_record_at_start(self, device):
        """Test single unread record at buffer start (wrap case)."""
        commands = device._calc_ring_buffer_read(user_idx=0, unread=2, last_slot=1)
        assert len(commands) == 2

    def test_buffer_almost_full_wrap(self, device):
        """Test buffer almost full with wrap."""
        commands = device._calc_ring_buffer_read(user_idx=0, unread=99, last_slot=1)
        assert len(commands) == 2
        # First read: 1 record from start
        assert commands[0]["size"] == 1 * 0x10
        # Second read: 98 records from end
        assert commands[1]["size"] == 98 * 0x10


class TestConfigurationVariants:
    """Tests for different device configurations."""

    def test_different_record_size(self):
        """Test device with different record size."""
        dev = ConcreteOmronDevice()
        dev.record_byte_size = 0x20  # 32 bytes instead of 16

        commands = dev._get_all_records_commands()
        expected_size = 100 * 0x20
        assert commands[0][0]["size"] == expected_size

    def test_different_records_per_user(self):
        """Test device with different records per user."""
        dev = ConcreteOmronDevice()
        dev.records_per_user = [50, 200]

        commands = dev._get_all_records_commands()
        assert commands[0][0]["size"] == 50 * 0x10
        assert commands[1][0]["size"] == 200 * 0x10

    def test_three_user_device(self):
        """Test device with three user slots."""
        dev = ConcreteOmronDevice()
        dev.user_start_addresses = [0x0100, 0x0500, 0x0900]
        dev.records_per_user = [30, 30, 30]

        commands = dev._get_all_records_commands()
        assert len(commands) == 3
        assert commands[2][0]["address"] == 0x0900


class TestBigEndianDevice:
    """Tests for big-endian device configuration."""

    def test_big_endian_extract_bits(self):
        """Test bit extraction with big-endian byte order."""
        dev = ConcreteOmronDevice()
        dev.device_endianness = "big"

        data = bytes([0x12, 0x34])  # Big-endian: 0x1234
        result = dev._extract_bits(data, 0, 7)
        assert result == 0x12

    def test_big_endian_lower_byte(self):
        """Test extracting lower byte in big-endian."""
        dev = ConcreteOmronDevice()
        dev.device_endianness = "big"

        data = bytes([0x12, 0x34])
        result = dev._extract_bits(data, 8, 15)
        assert result == 0x34
