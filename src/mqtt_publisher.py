"""MQTT publisher for blood pressure readings.

This module handles publishing blood pressure measurements to an MQTT broker
for integration with home automation systems (Home Assistant, OpenHAB, etc.).
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from paho.mqtt.properties import Properties
from paho.mqtt.reasoncodes import ReasonCode

from src.models import BloodPressureReading

logger = logging.getLogger(__name__)

# Default MQTT settings
DEFAULT_HOST = "192.168.40.19"
DEFAULT_PORT = 1883
DEFAULT_BASE_TOPIC = "omron/blood_pressure"


class MQTTPublisher:
    """Publish blood pressure readings to MQTT broker.

    Features:
    - Configurable broker connection
    - JSON payload format
    - QoS 1 for reliable delivery
    - Retained messages for last-known-value
    - Per-user topics
    """

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        username: str | None = None,
        password: str | None = None,
        base_topic: str = DEFAULT_BASE_TOPIC,
        client_id: str | None = None,
    ):
        """Initialize MQTT publisher.

        Args:
            host: MQTT broker hostname/IP
            port: MQTT broker port
            username: Optional authentication username
            password: Optional authentication password
            base_topic: Base topic for all messages
            client_id: Optional client ID (auto-generated if not provided)
        """
        self.host = host
        self.port = port
        self.base_topic = base_topic
        self._username = username
        self._password = password

        # Create MQTT client
        client_id = client_id or f"omron-garmin-bridge-{datetime.now().timestamp():.0f}"
        self._client = mqtt.Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=client_id,
        )

        # Setup authentication if provided
        if username and password:
            self._client.username_pw_set(username, password)

        # Setup callbacks
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_publish = self._on_publish

        self._connected = False
        self._last_error: str | None = None

    def _on_connect(
        self,
        _client: mqtt.Client,
        _userdata: Any,
        _flags: mqtt.ConnectFlags,
        reason_code: ReasonCode,
        _properties: Properties | None = None,
    ) -> None:
        """Callback when connected to broker."""
        if reason_code == mqtt.CONNACK_ACCEPTED or reason_code.is_failure is False:
            self._connected = True
            self._last_error = None
            logger.info("Connected to MQTT broker %s:%s", self.host, self.port)
        else:
            self._connected = False
            self._last_error = str(reason_code)
            logger.error("MQTT connection failed: %s", reason_code)

    def _on_disconnect(
        self,
        _client: mqtt.Client,
        _userdata: Any,
        _disconnect_flags: mqtt.DisconnectFlags,
        reason_code: ReasonCode,
        _properties: Properties | None = None,
    ) -> None:
        """Callback when disconnected from broker."""
        self._connected = False
        if reason_code != mqtt.MQTT_ERR_SUCCESS:
            logger.warning("MQTT disconnected unexpectedly: %s", reason_code)
        else:
            logger.info("Disconnected from MQTT broker")

    def _on_publish(
        self,
        _client: mqtt.Client,
        _userdata: Any,
        mid: int,
        _reason_code: ReasonCode,
        _properties: Properties | None = None,
    ) -> None:
        """Callback when message is published."""
        logger.debug("MQTT message %d published", mid)

    def connect(self, timeout: float = 10.0) -> bool:
        """Connect to MQTT broker.

        Args:
            timeout: Connection timeout in seconds

        Returns:
            True if connection successful
        """
        try:
            self._client.connect(self.host, self.port, keepalive=60)
            self._client.loop_start()

            # Wait for connection with timeout
            start = time.time()
            while not self._connected and (time.time() - start) < timeout:
                time.sleep(0.1)

            if not self._connected:
                logger.error(
                    "MQTT connection timeout after %ss. Last error: %s", timeout, self._last_error
                )
                return False

            return True

        except Exception as e:
            logger.error("Failed to connect to MQTT broker: %s", e)
            self._last_error = str(e)
            return False

    def disconnect(self) -> None:
        """Disconnect from MQTT broker."""
        try:
            self._client.loop_stop()
            self._client.disconnect()
        except Exception as e:
            logger.warning("Error during MQTT disconnect: %s", e)
        finally:
            self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if connected to broker."""
        return self._connected

    def _get_topic(self, user_identifier: str | None = None) -> str:
        """Build topic path for a user.

        Args:
            user_identifier: User email or slot number

        Returns:
            Full topic path
        """
        if user_identifier:
            # Sanitize for MQTT topic (replace @ and other special chars)
            safe_id = str(user_identifier).replace("@", "_at_").replace(" ", "_").replace("/", "_")
            return f"{self.base_topic}/{safe_id}"
        return self.base_topic

    def _build_payload(
        self,
        reading: BloodPressureReading,
        extra_data: dict | None = None,
    ) -> dict:
        """Build JSON payload for MQTT message.

        Args:
            reading: Blood pressure reading
            extra_data: Optional extra fields to include

        Returns:
            Dictionary payload
        """
        payload = {
            "timestamp": reading.timestamp.isoformat(),
            "systolic": reading.systolic,
            "diastolic": reading.diastolic,
            "pulse": reading.pulse,
            "category": reading.category,
            "irregular_heartbeat": reading.irregular_heartbeat,
            "body_movement": reading.body_movement,
            "user_slot": reading.user_slot,
            "device": "OMRON",
            "published_at": datetime.now().isoformat(),
        }

        if extra_data:
            payload.update(extra_data)

        return payload

    def publish_reading(
        self,
        reading: BloodPressureReading,
        user_identifier: str | None = None,
        retain: bool = True,
        qos: int = 1,
        extra_data: dict | None = None,
    ) -> bool:
        """Publish a blood pressure reading to MQTT.

        Args:
            reading: Blood pressure reading to publish
            user_identifier: Optional user email or identifier for topic
            retain: Whether to retain message on broker
            qos: Quality of Service level (0, 1, or 2)
            extra_data: Optional extra fields for payload

        Returns:
            True if publish successful
        """
        if not self._connected:
            logger.error("Not connected to MQTT broker")
            return False

        topic = self._get_topic(user_identifier)
        payload = self._build_payload(reading, extra_data)

        try:
            result = self._client.publish(
                topic,
                json.dumps(payload),
                qos=qos,
                retain=retain,
            )

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(
                    "Published to %s: %d/%d mmHg, pulse %d bpm",
                    topic,
                    reading.systolic,
                    reading.diastolic,
                    reading.pulse,
                )
                return True
            else:
                logger.error("Failed to publish: %s", mqtt.error_string(result.rc))
                return False

        except Exception as e:
            logger.error("MQTT publish error: %s", e)
            return False

    def publish_readings(
        self,
        readings: list[BloodPressureReading],
        user_identifier: str | None = None,
        retain: bool = True,
        qos: int = 1,
    ) -> tuple[int, int]:
        """Publish multiple readings to MQTT.

        Args:
            readings: List of readings to publish
            user_identifier: Optional user identifier
            retain: Whether to retain messages
            qos: Quality of Service level

        Returns:
            Tuple of (success_count, failure_count)
        """
        success = 0
        failure = 0

        for reading in readings:
            if self.publish_reading(reading, user_identifier, retain, qos):
                success += 1
            else:
                failure += 1

        logger.info("MQTT publish complete: %d success, %d failed", success, failure)
        return (success, failure)

    def publish_status(
        self,
        status: str,
        message: str | None = None,
        retain: bool = True,
    ) -> bool:
        """Publish bridge status message.

        Args:
            status: Status string (e.g., "online", "offline", "syncing")
            message: Optional status message
            retain: Whether to retain message

        Returns:
            True if publish successful
        """
        if not self._connected:
            return False

        topic = f"{self.base_topic}/status"
        payload = {
            "status": status,
            "message": message,
            "timestamp": datetime.now().isoformat(),
        }

        try:
            result = self._client.publish(
                topic,
                json.dumps(payload),
                qos=1,
                retain=retain,
            )
            return bool(result.rc == mqtt.MQTT_ERR_SUCCESS)
        except Exception as e:
            logger.error("Failed to publish status: %s", e)
            return False


def create_mqtt_publisher(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    username: str | None = None,
    password: str | None = None,
    base_topic: str = DEFAULT_BASE_TOPIC,
) -> MQTTPublisher:
    """Factory function to create and connect an MQTTPublisher.

    Args:
        host: MQTT broker hostname/IP
        port: MQTT broker port
        username: Optional authentication username
        password: Optional authentication password
        base_topic: Base topic for messages

    Returns:
        Connected MQTTPublisher instance

    Raises:
        ConnectionError: If connection fails
    """
    publisher = MQTTPublisher(
        host=host,
        port=port,
        username=username,
        password=password,
        base_topic=base_topic,
    )

    if not publisher.connect():
        raise ConnectionError(f"Failed to connect to MQTT broker at {host}:{port}")

    return publisher
