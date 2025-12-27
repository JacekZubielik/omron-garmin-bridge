"""OMRON BLE Client - Main interface for communicating with OMRON devices.

Based on omblepy by userx14 (https://github.com/userx14/omblepy)
"""

import asyncio
import contextlib
import logging

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice

from src.models import BloodPressureReading
from src.omron_ble.devices.base import BaseOmronDevice
from src.omron_ble.devices.hem_7361t import HEM7361T
from src.omron_ble.protocol import PARENT_SERVICE_UUID, OmronBLEProtocol

logger = logging.getLogger(__name__)

# Supported device models
SUPPORTED_DEVICES: dict[str, type[BaseOmronDevice]] = {
    "HEM-7361T": HEM7361T,
    "HEM-7361T-D": HEM7361T,  # Regional variant
    # Add more devices here as they are implemented
}


class OmronBLEClient:
    """High-level client for OMRON blood pressure monitors.

    This class provides a simple interface for:
    - Scanning for OMRON devices
    - Connecting and pairing
    - Reading blood pressure records
    - Syncing device time
    """

    def __init__(
        self,
        device_model: str,
        mac_address: str | None = None,
    ):
        """Initialize OMRON BLE client.

        Args:
            device_model: Device model name (e.g., "HEM-7361T")
            mac_address: Optional MAC address (if known)
        """
        self.device_model = device_model.upper()
        self.mac_address = mac_address
        self._client: BleakClient | None = None
        self._protocol: OmronBLEProtocol | None = None
        self._device_driver: BaseOmronDevice | None = None

        if self.device_model not in SUPPORTED_DEVICES:
            supported = ", ".join(SUPPORTED_DEVICES.keys())
            raise ValueError(
                f"Unsupported device model: {device_model}. Supported models: {supported}"
            )

    @staticmethod
    async def scan_devices(timeout: float = 10.0) -> list[BLEDevice]:
        """Scan for nearby BLE devices.

        Args:
            timeout: Scan timeout in seconds

        Returns:
            List of discovered BLE devices
        """
        logger.info(f"Scanning for BLE devices ({timeout}s)...")
        devices = await BleakScanner.discover(timeout=timeout, return_adv=True)

        # Sort by signal strength (RSSI)
        sorted_devices = sorted(
            devices.items(),
            key=lambda x: x[1][1].rssi,
            reverse=True,
        )

        result = []
        for mac, (device, adv_data) in sorted_devices:
            logger.debug(f"Found: {mac} - {device.name} (RSSI: {adv_data.rssi})")
            result.append(device)

        logger.info(f"Found {len(result)} devices")
        return result

    @staticmethod
    async def find_omron_devices(timeout: float = 10.0) -> list[BLEDevice]:
        """Scan for OMRON devices specifically.

        Args:
            timeout: Scan timeout in seconds

        Returns:
            List of OMRON BLE devices
        """
        all_devices = await OmronBLEClient.scan_devices(timeout)

        omron_devices = []
        for device in all_devices:
            # OMRON devices typically have "BLESmart_" prefix or "OMRON" in name
            if device.name and (
                "BLESmart" in device.name
                or "OMRON" in device.name.upper()
                or "HEM-" in device.name.upper()
            ):
                omron_devices.append(device)
                logger.info(f"OMRON device found: {device.address} - {device.name}")

        return omron_devices

    async def connect(self, pairing_mode: bool = False, scan_timeout: float = 10.0) -> bool:
        """Connect to the OMRON device.

        Args:
            pairing_mode: If True, expect device to be in pairing mode (showing 'P')
            scan_timeout: Timeout for scanning in seconds

        Returns:
            True if connection successful
        """
        device: BLEDevice | None = None

        if not self.mac_address:
            # Scan for device
            logger.info("No MAC address provided, scanning for OMRON devices...")
            devices = await self.find_omron_devices(timeout=scan_timeout)
            if not devices:
                raise ConnectionError("No OMRON devices found. Press Bluetooth button on device.")

            # Use first found device
            device = devices[0]
            self.mac_address = device.address
            logger.info(f"Using device: {self.mac_address} - {device.name}")

            # Create client from scanned device
            self._client = BleakClient(device)
        else:
            # For bonded devices, try direct connection first without scanning
            # This avoids the "Discovering: no" problem where adapter stops scanning
            # before OMRON can respond
            logger.info(f"Attempting direct connection to {self.mac_address}...")

            # Try direct connection using MAC address (works for bonded devices)
            self._client = BleakClient(self.mac_address)
            try:
                await asyncio.wait_for(self._client.connect(), timeout=15.0)
                if self._client.is_connected:
                    logger.info("Direct connection successful!")
                else:
                    raise ConnectionError("Connection returned but not connected")
            except (TimeoutError, ConnectionError, OSError) as direct_err:
                logger.debug(f"Direct connection failed: {direct_err}, falling back to scan")
                # Fall back to scanning
                logger.info(f"Scanning for device {self.mac_address}...")
                device = await BleakScanner.find_device_by_address(
                    self.mac_address,
                    timeout=scan_timeout,
                )
                if not device:
                    raise ConnectionError(
                        f"Device {self.mac_address} not found. "
                        "Make sure Bluetooth is enabled on the device (press BT button)."
                    ) from direct_err
                logger.info(f"Found device: {device.name}")
                self._client = BleakClient(device)

        self._pairing_mode = pairing_mode

        try:
            # Connect if not already connected (direct connection case)
            if not self._client.is_connected:
                logger.info(f"Connecting to {self.mac_address}...")
                await self._client.connect()
            logger.debug("BLE connection established")

            if pairing_mode:
                # In pairing mode, just a short delay to let services be discovered.
                # The longer wait and OS-level pair() call happens in pair() method.
                logger.info("Pairing mode: waiting for connection to stabilize...")
                await asyncio.sleep(2)

            # Verify this is an OMRON device by checking for required service
            service_uuids = [s.uuid for s in self._client.services]
            if PARENT_SERVICE_UUID not in service_uuids:
                raise ConnectionError(
                    "Connected device does not appear to be an OMRON device. "
                    "Required BLE service not found."
                )

            # Initialize protocol and device driver
            self._protocol = OmronBLEProtocol(self._client)
            device_class = SUPPORTED_DEVICES[self.device_model]
            self._device_driver = device_class(self._protocol)

            logger.info("Connected successfully!")
            return True

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            if self._client and self._client.is_connected:
                await self._client.disconnect()
            raise

    async def disconnect(self) -> None:
        """Disconnect from the device."""
        if self._client and self._client.is_connected:
            logger.info("Disconnecting...")

            # NOTE: We do NOT unpair here. Original omblepy does unpair(),
            # but that removes the pairing key from the device, which means
            # you need to re-pair every time. We keep the pairing intact
            # so subsequent connections work without pairing mode.

            try:
                await self._client.disconnect()
            except AssertionError as e:
                # Known issue with bluezdbus adapter
                logger.warning(f"Disconnect assertion error (can be ignored): {e}")
            except Exception as e:
                logger.warning(f"Disconnect error: {e}")

            logger.info("Disconnected")

        self._client = None
        self._protocol = None
        self._device_driver = None
        self._pairing_mode = False

    async def pair(self, skip_os_pair: bool = False) -> bool:
        """Pair with the device (device must be in pairing mode).

        The device should display blinking "P" on the screen.
        To enter pairing mode: hold Bluetooth button for 3+ seconds.

        Args:
            skip_os_pair: If True, skip OS-level pairing (for Linux troubleshooting)

        Returns:
            True if pairing successful
        """
        if not self._protocol or not self._client:
            raise RuntimeError("Not connected. Call connect() first.")

        logger.info("Starting OMRON pairing process...")
        logger.info("Device should show blinking 'P'. If not, hold BT button for 3+ seconds.")

        try:
            # Wait for connection to stabilize (as per omblepy)
            logger.info("Waiting 10s for connection to stabilize...")
            await asyncio.sleep(10)

            # Step 1: OS-level Bluetooth pairing (as per omblepy)
            # On Windows this is required, on Linux it often fails but may still be needed
            if not skip_os_pair:
                logger.info("Attempting OS-level Bluetooth pairing...")
                try:
                    await self._client.pair(protection_level=2)
                    logger.info("OS-level pairing completed")
                except Exception as e:
                    logger.warning(f"OS-level pairing error: {e}")
                    # On Linux, if pair() fails, the connection often becomes unstable
                    # We need to reconnect before trying OMRON protocol
                    logger.info("Reconnecting after failed OS pairing...")
                    with contextlib.suppress(Exception):
                        await self._client.disconnect()
                    await asyncio.sleep(2)

                    # Reconnect
                    await self._client.connect()
                    logger.info("Reconnected, waiting for services...")
                    await asyncio.sleep(5)
            else:
                logger.info("Skipping OS-level pairing (skip_os_pair=True)")

            await asyncio.sleep(1.0)

            # Step 2: Write the pairing key via OMRON protocol
            # This is the OMRON-specific protocol pairing
            logger.info("Writing OMRON pairing key...")
            await self._protocol.write_pairing_key()
            logger.info("OMRON pairing key written to device")

            await asyncio.sleep(0.5)

            # Step 3: Complete pairing handshake with start/end transmission
            logger.info("Completing pairing handshake...")
            await self._protocol.start_transmission()
            await self._protocol.end_transmission()

            logger.info("Pairing completed successfully!")
            logger.info("Device should now show a square symbol instead of 'P'.")
            return True

        except Exception as e:
            logger.error(f"Pairing failed: {e}")
            logger.error("Make sure device shows blinking 'P' (pairing mode).")
            raise

    async def read_records(
        self,
        only_new: bool = False,
        sync_time: bool = False,
    ) -> list[list[BloodPressureReading]]:
        """Read blood pressure records from the device.

        Args:
            only_new: Only read new (unread) records
            sync_time: Sync device time with system time

        Returns:
            List of readings per user slot
        """
        if not self._device_driver:
            raise RuntimeError("Not connected. Call connect() first.")

        logger.info("Reading records from device...")
        records = await self._device_driver.get_all_records(
            use_unread_counter=only_new,
            sync_time=sync_time,
        )

        total = sum(len(r) for r in records)
        logger.info(f"Read {total} records total")

        return records

    async def read_all_records_flat(
        self,
        only_new: bool = False,
        sync_time: bool = False,
    ) -> list[BloodPressureReading]:
        """Read all records as a flat list.

        Args:
            only_new: Only read new (unread) records
            sync_time: Sync device time with system time

        Returns:
            Flat list of all readings
        """
        records_by_user = await self.read_records(only_new, sync_time)

        all_records: list[BloodPressureReading] = []
        for user_records in records_by_user:
            all_records.extend(user_records)

        # Sort by timestamp
        all_records.sort(key=lambda r: r.timestamp)
        return all_records

    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._client is not None and self._client.is_connected


async def read_omron_device(
    device_model: str,
    mac_address: str | None = None,
    only_new: bool = False,
    sync_time: bool = False,
) -> list[BloodPressureReading]:
    """Convenience function to read records from an OMRON device.

    Args:
        device_model: Device model (e.g., "HEM-7361T")
        mac_address: Optional MAC address
        only_new: Only read new records
        sync_time: Sync device time

    Returns:
        List of blood pressure readings
    """
    client = OmronBLEClient(device_model, mac_address)

    try:
        await client.connect()
        records = await client.read_all_records_flat(only_new, sync_time)
        return records
    finally:
        await client.disconnect()
