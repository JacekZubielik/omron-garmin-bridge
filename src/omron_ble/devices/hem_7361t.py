"""OMRON HEM-7361T (M7 Intelli IT) device driver.

Based on omblepy by userx14 (https://github.com/userx14/omblepy)
"""

import logging
from datetime import datetime
from typing import Literal

from src.models import BloodPressureReading
from src.omron_ble.devices.base import BaseOmronDevice

logger = logging.getLogger(__name__)


class HEM7361T(BaseOmronDevice):
    """Driver for OMRON HEM-7361T blood pressure monitor.

    Also known as M7 Intelli IT.
    Supports 2 users with 100 records each.
    """

    # Device-specific configuration
    device_endianness: Literal["little", "big"] = "little"
    user_start_addresses = [0x0098, 0x06D8]
    records_per_user = [100, 100]
    record_byte_size = 0x10
    transmission_block_size = 0x10

    # Settings addresses
    settings_read_address = 0x0010
    settings_write_address = 0x0054
    settings_unread_records_bytes = (0x00, 0x10)
    settings_time_sync_bytes = (0x2C, 0x3C)

    def parse_record(self, record_bytes: bytes) -> BloodPressureReading:
        """Parse raw record bytes into BloodPressureReading.

        Record format (16 bytes, little-endian):
        - Bits 68-73: minute
        - Bits 74-79: second
        - Bit 80: MOV (body movement flag)
        - Bit 81: IHB (irregular heartbeat flag)
        - Bits 82-85: month
        - Bits 86-90: day
        - Bits 91-95: hour
        - Bits 98-103: year (offset from 2000)
        - Bits 104-111: pulse (bpm)
        - Bits 112-119: diastolic
        - Bits 120-127: systolic (add 25 to get actual value)

        Args:
            record_bytes: 16 bytes of raw record data

        Returns:
            Parsed BloodPressureReading
        """
        minute = self._extract_bits(record_bytes, 68, 73)
        second = self._extract_bits(record_bytes, 74, 79)
        second = min(second, 59)  # Second can be up to 63 for some reason

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

        return BloodPressureReading(
            timestamp=timestamp,
            systolic=systolic,
            diastolic=diastolic,
            pulse=pulse,
            irregular_heartbeat=ihb,
            body_movement=mov,
        )

    def get_time_sync_bytes(self, current_time: datetime) -> bytearray:
        """Generate time sync bytes for device.

        Time sync section format (16 bytes):
        - Bytes 0-7: Unchanged (copied from device)
        - Byte 8: Year - 2000
        - Byte 9: Month
        - Byte 10: Day
        - Byte 11: Hour
        - Byte 12: Minute
        - Byte 13: Second
        - Byte 14: Checksum (sum of bytes 0-13, lower 8 bits)
        - Byte 15: 0x00

        Args:
            current_time: Current system time

        Returns:
            16 bytes to write for time sync
        """
        start, end = self.settings_time_sync_bytes
        section = self._cached_settings[start:end]

        # Keep first 8 bytes unchanged
        new_bytes = bytearray(section[:8])

        # Add current time
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

        # Calculate checksum
        checksum = sum(new_bytes) & 0xFF
        new_bytes += bytes([checksum, 0x00])

        logger.info(f"Time sync prepared: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        return new_bytes
