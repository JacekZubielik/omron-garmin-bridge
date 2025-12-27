"""Base device driver for OMRON blood pressure monitors.

Based on omblepy by userx14 (https://github.com/userx14/omblepy)
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Literal

from src.models import BloodPressureReading
from src.omron_ble.protocol import OmronBLEProtocol

logger = logging.getLogger(__name__)


class BaseOmronDevice(ABC):
    """Abstract base class for OMRON device drivers.

    Each device model should inherit from this class and implement
    the abstract methods with device-specific logic.
    """

    # Device-specific constants (must be overridden by subclasses)
    device_endianness: Literal["little", "big"] = "little"
    user_start_addresses: list[int] = []  # EEPROM start addresses per user
    records_per_user: list[int] = []  # Max records per user
    record_byte_size: int = 0x10  # Size of each record in bytes
    transmission_block_size: int = 0x10  # BLE transmission block size

    # Settings addresses
    settings_read_address: int = 0
    settings_write_address: int = 0
    settings_unread_records_bytes: tuple[int, int] = (0, 0)
    settings_time_sync_bytes: tuple[int, int] = (0, 0)

    def __init__(self, protocol: OmronBLEProtocol):
        """Initialize device driver.

        Args:
            protocol: BLE protocol handler
        """
        self.protocol = protocol
        self._cached_settings: bytearray = bytearray()

    @abstractmethod
    def parse_record(self, record_bytes: bytes) -> BloodPressureReading:
        """Parse raw record bytes into BloodPressureReading.

        Args:
            record_bytes: Raw bytes from device EEPROM

        Returns:
            Parsed blood pressure reading
        """
        raise NotImplementedError

    @abstractmethod
    def get_time_sync_bytes(self, current_time: datetime) -> bytearray:
        """Generate time sync bytes for device.

        Args:
            current_time: Current system time

        Returns:
            Bytes to write to device for time sync
        """
        raise NotImplementedError

    def _extract_bits(self, data: bytes, first_bit: int, last_bit: int) -> int:
        """Extract bits from byte array.

        Args:
            data: Source byte array
            first_bit: First bit index (MSB = 0)
            last_bit: Last bit index (inclusive)

        Returns:
            Extracted integer value
        """
        big_int = int.from_bytes(data, self.device_endianness)
        num_valid_bits = (last_bit - first_bit) + 1
        shifted = big_int >> (len(data) * 8 - (last_bit + 1))
        bitmask = (2**num_valid_bits) - 1
        return int(shifted & bitmask)

    async def get_all_records(
        self,
        use_unread_counter: bool = False,
        sync_time: bool = False,
    ) -> list[list[BloodPressureReading]]:
        """Read all records from device.

        Args:
            use_unread_counter: Only read new (unread) records
            sync_time: Sync device time with system time

        Returns:
            List of readings per user slot
        """
        await self.protocol.unlock_with_key()
        await self.protocol.start_transmission()

        # Cache settings if needed
        if sync_time or use_unread_counter:
            await self._cache_settings()

        # Determine what to read
        if use_unread_counter:
            read_commands = self._get_unread_records_commands()
        else:
            read_commands = self._get_all_records_commands()

        # Read records for all users
        logger.info("Reading data from device...")
        all_user_records: list[list[BloodPressureReading]] = []

        for user_idx, user_commands in enumerate(read_commands):
            user_data = bytearray()
            for cmd in user_commands:
                user_data += await self.protocol.read_continuous(
                    cmd["address"],
                    cmd["size"],
                    self.transmission_block_size,
                )

            # Parse individual records
            user_records: list[BloodPressureReading] = []
            for offset in range(0, len(user_data), self.record_byte_size):
                record_bytes = user_data[offset : offset + self.record_byte_size]

                # Skip empty records (all 0xFF)
                if record_bytes == b"\xff" * self.record_byte_size:
                    continue

                try:
                    reading = self.parse_record(bytes(record_bytes))
                    # Set user slot (1-indexed)
                    reading.user_slot = user_idx + 1
                    user_records.append(reading)
                except Exception as e:
                    logger.warning(
                        f"Error parsing record for user{user_idx + 1} at offset {offset}: {e}"
                    )

            all_user_records.append(user_records)
            logger.info(f"User {user_idx + 1}: {len(user_records)} records")

        # Update device settings if needed
        if use_unread_counter:
            await self._reset_unread_counters()

        if sync_time:
            await self._sync_device_time()

        await self.protocol.end_transmission()
        return all_user_records

    async def _cache_settings(self) -> None:
        """Cache device settings from EEPROM."""
        settings_size = self.settings_write_address - self.settings_read_address
        self._cached_settings = bytearray(b"\x00" * settings_size)

        # Read unread records section
        start, end = self.settings_unread_records_bytes
        section_size = end - start
        if section_size > 0:
            data = await self.protocol.read_continuous(
                self.settings_read_address + start,
                section_size,
                section_size,
            )
            self._cached_settings[start:end] = data

        # Read time sync section
        start, end = self.settings_time_sync_bytes
        section_size = end - start
        if section_size > 0:
            data = await self.protocol.read_continuous(
                self.settings_read_address + start,
                section_size,
                section_size,
            )
            self._cached_settings[start:end] = data

    def _get_all_records_commands(self) -> list[list[dict]]:
        """Get read commands for all records.

        Returns:
            List of read commands per user
        """
        all_commands: list[list[dict]] = []
        for user_idx, start_addr in enumerate(self.user_start_addresses):
            cmd = {
                "address": start_addr,
                "size": self.records_per_user[user_idx] * self.record_byte_size,
            }
            all_commands.append([cmd])
        return all_commands

    def _get_unread_records_commands(self) -> list[list[dict]]:
        """Get read commands for unread records only.

        Returns:
            List of read commands per user
        """
        all_commands: list[list[dict]] = []
        start, end = self.settings_unread_records_bytes
        info_bytes = self._cached_settings[start:end]

        for user_idx in range(len(self.user_start_addresses)):
            # Extract ring buffer position and unread count
            last_slot = self._extract_bits(info_bytes[2 * user_idx : 2 * user_idx + 2], 8, 15)
            unread_count = self._extract_bits(
                info_bytes[2 * user_idx + 4 : 2 * user_idx + 6], 8, 15
            )

            logger.info(f"User {user_idx + 1}: slot={last_slot}, unread={unread_count}")

            commands = self._calc_ring_buffer_read(user_idx, unread_count, last_slot)
            all_commands.append(commands)

        return all_commands

    def _calc_ring_buffer_read(self, user_idx: int, unread: int, last_slot: int) -> list[dict]:
        """Calculate read commands for ring buffer.

        Args:
            user_idx: User index (0-based)
            unread: Number of unread records
            last_slot: Last written slot in ring buffer

        Returns:
            List of read commands
        """
        commands: list[dict] = []
        start_addr = self.user_start_addresses[user_idx]
        max_records = self.records_per_user[user_idx]

        if last_slot < unread:
            # Two reads needed (wrap around)
            # Read from start of buffer
            commands.append(
                {
                    "address": start_addr,
                    "size": self.record_byte_size * last_slot,
                }
            )
            # Read from end of buffer
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

    async def _reset_unread_counters(self) -> None:
        """Reset unread record counters on device."""
        start, end = self.settings_unread_records_bytes
        section = self._cached_settings[start:end]

        # Set unread counters to 0x8000 (special "no new records" code)
        reset_bytes = (0x8000).to_bytes(2, byteorder=self.device_endianness)
        new_section = section[:4] + reset_bytes * 2 + section[8:]
        self._cached_settings[start:end] = new_section

        await self.protocol.write_continuous(
            self.settings_write_address + start,
            new_section,
            block_size=len(new_section),
        )

    async def _sync_device_time(self) -> None:
        """Sync device time with system time."""
        time_bytes = self.get_time_sync_bytes(datetime.now())
        start, _ = self.settings_time_sync_bytes

        await self.protocol.write_continuous(
            self.settings_write_address + start,
            time_bytes,
            block_size=len(time_bytes),
        )
        logger.info(f"Device time synced to {datetime.now()}")
