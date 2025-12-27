"""OMRON BLE Protocol Handler.

Based on omblepy by userx14 (https://github.com/userx14/omblepy)
Handles low-level BLE communication with OMRON blood pressure monitors.
"""

import asyncio
import logging

from bleak import BleakClient

logger = logging.getLogger(__name__)

# OMRON BLE Service UUID
PARENT_SERVICE_UUID = "ecbe3980-c9a2-11e1-b1bd-0002a5d5c51b"

# Default pairing key (can be customized)
DEFAULT_PAIRING_KEY = bytearray.fromhex("deadbeaf12341234deadbeaf12341234")


def bytes_to_hex(array: bytes | bytearray) -> str:
    """Convert byte array to hex string."""
    return bytes(array).hex()


class OmronBLEProtocol:
    """Handles BLE TX/RX communication with OMRON devices.

    This class manages the low-level protocol for reading/writing
    data to OMRON blood pressure monitors over Bluetooth LE.
    """

    # BTLE Characteristic UUIDs for receiving data
    DEVICE_RX_CHANNEL_UUIDS = [
        "49123040-aee8-11e1-a74d-0002a5d5c51b",
        "4d0bf320-aee8-11e1-a0d9-0002a5d5c51b",
        "5128ce60-aee8-11e1-b84b-0002a5d5c51b",
        "560f1420-aee8-11e1-8184-0002a5d5c51b",
    ]

    # BTLE Characteristic UUIDs for transmitting data
    DEVICE_TX_CHANNEL_UUIDS = [
        "db5b55e0-aee7-11e1-965e-0002a5d5c51b",
        "e0b8a060-aee7-11e1-92f4-0002a5d5c51b",
        "0ae12b00-aee8-11e1-a192-0002a5d5c51b",
        "10e1ba60-aee8-11e1-89e5-0002a5d5c51b",
    ]

    # Integer handles for RX channels
    DEVICE_RX_CHANNEL_HANDLES = [0x360, 0x370, 0x380, 0x390]

    # UUID for unlock/pairing operations
    DEVICE_UNLOCK_UUID = "b305b680-aee7-11e1-a730-0002a5d5c51b"

    def __init__(self, client: BleakClient):
        """Initialize protocol handler.

        Args:
            client: Connected BleakClient instance
        """
        self.client = client
        self._rx_notify_enabled = False
        self._rx_packet_type: bytearray | None = None
        self._rx_eeprom_address: bytearray | None = None
        self._rx_data_bytes: bytes | bytearray | None = None
        self._rx_finished = False
        self._rx_channel_buffer: list[bytes | None] = [None] * 4

    async def _enable_rx_notifications(self) -> None:
        """Enable notifications on all RX channels."""
        if not self._rx_notify_enabled:
            for rx_uuid in self.DEVICE_RX_CHANNEL_UUIDS:
                await self.client.start_notify(rx_uuid, self._rx_callback)
            self._rx_notify_enabled = True

    async def _disable_rx_notifications(self) -> None:
        """Disable notifications on all RX channels."""
        if self._rx_notify_enabled:
            for rx_uuid in self.DEVICE_RX_CHANNEL_UUIDS:
                await self.client.stop_notify(rx_uuid)
            self._rx_notify_enabled = False

    def _rx_callback(self, char_handle, rx_bytes: bytes) -> None:
        """Callback for received data on RX channels.

        Args:
            char_handle: BLE characteristic handle (int or BleakGATTChar)
            rx_bytes: Received bytes
        """
        # Determine channel ID from handle
        if isinstance(char_handle, int):
            channel_id = self.DEVICE_RX_CHANNEL_HANDLES.index(char_handle)
        else:
            channel_id = self.DEVICE_RX_CHANNEL_HANDLES.index(char_handle.handle)

        self._rx_channel_buffer[channel_id] = rx_bytes
        logger.debug(f"RX ch{channel_id} < {bytes_to_hex(rx_bytes)}")

        # Check if we have data in first buffer
        if self._rx_channel_buffer[0] is None:
            return

        packet_size = self._rx_channel_buffer[0][0]
        required_channels = range((packet_size + 15) // 16)

        # Check if all required channels are received
        for ch_idx in required_channels:
            if self._rx_channel_buffer[ch_idx] is None:
                return  # Wait for more packets

        # Combine data from all channels
        combined_rx = bytearray()
        for ch_idx in required_channels:
            combined_rx += self._rx_channel_buffer[ch_idx]  # type: ignore
        combined_rx = combined_rx[:packet_size]

        # Verify CRC (XOR of all bytes should be 0)
        xor_crc = 0
        for byte in combined_rx:
            xor_crc ^= byte
        if xor_crc:
            raise ValueError(
                f"Data corruption in RX - CRC: {xor_crc}, buffer: {bytes_to_hex(combined_rx)}"
            )

        # Extract packet information
        self._rx_packet_type = combined_rx[1:3]
        self._rx_eeprom_address = combined_rx[3:5]
        expected_data_bytes = combined_rx[5]

        if expected_data_bytes > (len(combined_rx) - 8):
            self._rx_data_bytes = b"\xff" * expected_data_bytes
        else:
            # Special case for end of transmission packet
            if self._rx_packet_type == bytearray.fromhex("8f00"):
                self._rx_data_bytes = combined_rx[6:7]
            else:
                self._rx_data_bytes = combined_rx[6 : 6 + expected_data_bytes]

        # Clear buffers and set finished flag
        self._rx_channel_buffer = [None] * 4
        self._rx_finished = True

    async def _send_and_wait(self, command: bytearray, timeout_s: float = 1.0) -> None:
        """Send command and wait for response with retry logic.

        Args:
            command: Command bytes to send
            timeout_s: Timeout in seconds for response
        """
        self._rx_finished = False
        retries = 0
        max_retries = 5

        while True:
            command_copy = command[:]
            required_tx_channels = range((len(command) + 15) // 16)

            for ch_idx in required_tx_channels:
                chunk = command_copy[:16]
                logger.debug(f"TX ch{ch_idx} > {bytes_to_hex(chunk)}")
                await self.client.write_gatt_char(self.DEVICE_TX_CHANNEL_UUIDS[ch_idx], chunk)
                command_copy = command_copy[16:]

            current_timeout = timeout_s
            while not self._rx_finished:
                await asyncio.sleep(0.1)
                current_timeout -= 0.1
                if current_timeout < 0:
                    break

            if current_timeout >= 0:
                break

            retries += 1
            logger.warning(f"Transmission failed, retry {retries}/{max_retries}")
            if retries >= max_retries:
                raise TimeoutError("Transmission failed after 5 retries")

    async def start_transmission(self) -> None:
        """Start data readout session with the device."""
        await self._enable_rx_notifications()
        start_cmd = bytearray.fromhex("0800000000100018")
        await self._send_and_wait(start_cmd)

        if self._rx_packet_type != bytearray.fromhex("8000"):
            raise ValueError("Invalid response to data readout start")

    async def end_transmission(self) -> None:
        """End data readout session with the device."""
        stop_cmd = bytearray.fromhex("080f000000000007")
        await self._send_and_wait(stop_cmd)

        if self._rx_packet_type != bytearray.fromhex("8f00"):
            raise ValueError("Invalid response to data readout end")

        if self._rx_data_bytes and self._rx_data_bytes[0]:
            raise ValueError(
                f"Device reported error code {self._rx_data_bytes[0]} during end transmission"
            )

        await self._disable_rx_notifications()

    async def read_eeprom_block(self, address: int, block_size: int) -> bytes:
        """Read a block of data from device EEPROM.

        Args:
            address: EEPROM address to read from
            block_size: Number of bytes to read

        Returns:
            Read bytes
        """
        read_cmd = bytearray.fromhex("080100")
        read_cmd += address.to_bytes(2, "big")
        read_cmd += block_size.to_bytes(1, "big")

        # Calculate and append CRC
        xor_crc = 0
        for byte in read_cmd:
            xor_crc ^= byte
        read_cmd += b"\x00"
        read_cmd.append(xor_crc)

        await self._send_and_wait(read_cmd)

        if self._rx_eeprom_address != address.to_bytes(2, "big"):
            raise ValueError(
                f"Received address {self._rx_eeprom_address} doesn't match requested {address}"
            )

        if self._rx_packet_type != bytearray.fromhex("8100"):
            raise ValueError("Invalid packet type in EEPROM read")

        return self._rx_data_bytes or b""

    async def write_eeprom_block(self, address: int, data: bytearray) -> None:
        """Write a block of data to device EEPROM.

        Args:
            address: EEPROM address to write to
            data: Data bytes to write
        """
        write_cmd = bytearray()
        write_cmd += (len(data) + 8).to_bytes(1, "big")
        write_cmd += bytearray.fromhex("01c0")
        write_cmd += address.to_bytes(2, "big")
        write_cmd += len(data).to_bytes(1, "big")
        write_cmd += data

        # Calculate and append CRC
        xor_crc = 0
        for byte in write_cmd:
            xor_crc ^= byte
        write_cmd += b"\x00"
        write_cmd.append(xor_crc)

        await self._send_and_wait(write_cmd)

        if self._rx_eeprom_address != address.to_bytes(2, "big"):
            raise ValueError(
                f"Received address {self._rx_eeprom_address} doesn't match written {address}"
            )

        if self._rx_packet_type != bytearray.fromhex("81c0"):
            raise ValueError("Invalid packet type in EEPROM write")

    async def read_continuous(
        self, start_address: int, bytes_to_read: int, block_size: int = 0x10
    ) -> bytearray:
        """Read continuous data from EEPROM.

        Args:
            start_address: Starting EEPROM address
            bytes_to_read: Total bytes to read
            block_size: Size of each read block

        Returns:
            Combined read data
        """
        data = bytearray()
        while bytes_to_read > 0:
            next_block_size = min(bytes_to_read, block_size)
            logger.debug(f"Read from 0x{start_address:04x} size 0x{next_block_size:02x}")
            data += await self.read_eeprom_block(start_address, next_block_size)
            start_address += next_block_size
            bytes_to_read -= next_block_size
        return data

    async def write_continuous(
        self, start_address: int, data: bytearray, block_size: int = 0x08
    ) -> None:
        """Write continuous data to EEPROM.

        Args:
            start_address: Starting EEPROM address
            data: Data to write
            block_size: Size of each write block
        """
        while len(data) > 0:
            next_block_size = min(len(data), block_size)
            logger.debug(f"Write to 0x{start_address:04x} size 0x{next_block_size:02x}")
            await self.write_eeprom_block(start_address, data[:next_block_size])
            data = data[next_block_size:]
            start_address += next_block_size

    async def write_pairing_key(
        self, key: bytearray = DEFAULT_PAIRING_KEY, timeout_s: float = 5.0
    ) -> None:
        """Program a new pairing key into the device.

        Device must be in pairing mode (P displayed).

        Args:
            key: 16-byte pairing key
            timeout_s: Timeout in seconds for each step
        """
        if len(key) != 16:
            raise ValueError(f"Key must be 16 bytes, got {len(key)}")

        # Reset state
        self._rx_finished = False
        self._rx_data_bytes = None

        # Enable notifications on unlock channel
        logger.debug(f"Starting notify on unlock UUID: {self.DEVICE_UNLOCK_UUID}")
        await self.client.start_notify(self.DEVICE_UNLOCK_UUID, self._unlock_callback)

        # Small delay to ensure notifications are set up
        await asyncio.sleep(0.2)

        # Send command to enter key programming mode (0x02 + 16 zero bytes)
        enter_pairing_cmd = b"\x02" + b"\x00" * 16
        logger.debug(f"Sending enter pairing mode command: {bytes_to_hex(enter_pairing_cmd)}")
        await self.client.write_gatt_char(self.DEVICE_UNLOCK_UUID, enter_pairing_cmd, response=True)

        # Wait for response with timeout
        elapsed = 0.0
        while not self._rx_finished and elapsed < timeout_s:
            await asyncio.sleep(0.1)
            elapsed += 0.1

        if not self._rx_finished:
            await self.client.stop_notify(self.DEVICE_UNLOCK_UUID)
            raise ValueError(
                f"Timeout waiting for pairing mode response after {timeout_s}s. "
                "Is the device in pairing mode (P displayed)?"
            )

        logger.debug(f"Received pairing mode response: {bytes_to_hex(self._rx_data_bytes or b'')}")

        rx_data = self._rx_data_bytes
        if rx_data is None:
            await self.client.stop_notify(self.DEVICE_UNLOCK_UUID)
            raise ValueError(
                "Could not enter key programming mode. Got response: None. "
                "Is the device in pairing mode (P displayed)?"
            )
        if rx_data[:2] != bytearray.fromhex("8200"):
            await self.client.stop_notify(self.DEVICE_UNLOCK_UUID)
            raise ValueError(
                f"Could not enter key programming mode. Got response: {bytes_to_hex(rx_data)}. "
                "Is the device in pairing mode (P displayed)?"
            )

        # Program new key (0x00 + 16-byte key)
        self._rx_finished = False
        program_key_cmd = b"\x00" + key
        logger.debug(f"Sending program key command: {bytes_to_hex(program_key_cmd)}")
        await self.client.write_gatt_char(self.DEVICE_UNLOCK_UUID, program_key_cmd, response=True)

        # Wait for response with timeout
        elapsed = 0.0
        while not self._rx_finished and elapsed < timeout_s:
            await asyncio.sleep(0.1)
            elapsed += 0.1

        if not self._rx_finished:
            await self.client.stop_notify(self.DEVICE_UNLOCK_UUID)
            raise ValueError(f"Timeout waiting for key programming response after {timeout_s}s")

        logger.debug(
            f"Received key programming response: {bytes_to_hex(self._rx_data_bytes or b'')}"
        )

        if self._rx_data_bytes is None or self._rx_data_bytes[:2] != bytearray.fromhex("8000"):
            await self.client.stop_notify(self.DEVICE_UNLOCK_UUID)
            response_hex = bytes_to_hex(self._rx_data_bytes) if self._rx_data_bytes else "None"
            raise ValueError(f"Failed to program new key. Response: {response_hex}")

        await self.client.stop_notify(self.DEVICE_UNLOCK_UUID)
        logger.info(f"Device paired successfully with key {bytes_to_hex(key)}")

    async def unlock_with_key(self, key: bytearray = DEFAULT_PAIRING_KEY) -> None:
        """Unlock device with stored pairing key.

        Args:
            key: 16-byte pairing key
        """
        await self.client.start_notify(self.DEVICE_UNLOCK_UUID, self._unlock_callback)
        self._rx_finished = False
        await self.client.write_gatt_char(self.DEVICE_UNLOCK_UUID, b"\x01" + key, response=True)

        while not self._rx_finished:
            await asyncio.sleep(0.1)

        if self._rx_data_bytes is None or self._rx_data_bytes[:2] != bytearray.fromhex("8100"):
            raise ValueError("Pairing key does not match stored key")

        await self.client.stop_notify(self.DEVICE_UNLOCK_UUID)

    def _unlock_callback(self, _uuid_or_handle, rx_bytes: bytes) -> None:
        """Callback for unlock channel responses."""
        self._rx_data_bytes = rx_bytes
        self._rx_finished = True
