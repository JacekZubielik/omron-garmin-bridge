"""Tests for MQTT publisher module."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.mqtt_publisher import (
    DEFAULT_BASE_TOPIC,
    DEFAULT_HOST,
    DEFAULT_PORT,
    MQTTPublisher,
    create_mqtt_publisher,
)


class TestMQTTPublisherInit:
    """Tests for MQTTPublisher initialization."""

    def test_init_defaults(self):
        """Test initialization with default values."""
        publisher = MQTTPublisher()

        assert publisher.host == DEFAULT_HOST
        assert publisher.port == DEFAULT_PORT
        assert publisher.base_topic == DEFAULT_BASE_TOPIC
        assert publisher._connected is False

    def test_init_custom_values(self):
        """Test initialization with custom values."""
        publisher = MQTTPublisher(
            host="mqtt.example.com",
            port=8883,
            username="user",
            password="pass",
            base_topic="custom/topic",
            client_id="my-client",
        )

        assert publisher.host == "mqtt.example.com"
        assert publisher.port == 8883
        assert publisher.base_topic == "custom/topic"
        assert publisher._username == "user"
        assert publisher._password == "pass"

    def test_init_creates_mqtt_client(self):
        """Test that MQTT client is created with correct API version."""
        publisher = MQTTPublisher()

        assert publisher._client is not None
        # Client should have callbacks set
        assert publisher._client.on_connect is not None
        assert publisher._client.on_disconnect is not None
        assert publisher._client.on_publish is not None


class TestMQTTPublisherConnect:
    """Tests for connection handling."""

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_connect_success(self, mock_client_class):
        """Test successful connection."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        publisher = MQTTPublisher()

        # Simulate successful connection by triggering callback
        def connect_side_effect(*args, **kwargs):
            # Simulate the on_connect callback being called
            publisher._connected = True

        mock_client.connect.side_effect = connect_side_effect

        result = publisher.connect(timeout=0.1)

        mock_client.connect.assert_called_once()
        mock_client.loop_start.assert_called_once()
        assert result is True

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_connect_timeout(self, mock_client_class):
        """Test connection timeout."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        publisher = MQTTPublisher()

        # Don't set _connected to True - simulates timeout
        result = publisher.connect(timeout=0.1)

        assert result is False
        assert publisher._connected is False

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_connect_exception(self, mock_client_class):
        """Test connection exception handling."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.connect.side_effect = Exception("Connection refused")

        publisher = MQTTPublisher()
        result = publisher.connect(timeout=0.1)

        assert result is False
        assert publisher._last_error == "Connection refused"

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_disconnect(self, mock_client_class):
        """Test disconnect."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        publisher = MQTTPublisher()
        publisher._connected = True

        publisher.disconnect()

        mock_client.loop_stop.assert_called_once()
        mock_client.disconnect.assert_called_once()
        assert publisher._connected is False


class TestMQTTPublisherTopics:
    """Tests for topic generation."""

    def test_get_topic_no_user(self):
        """Test topic without user identifier."""
        publisher = MQTTPublisher(base_topic="omron/bp")

        topic = publisher._get_topic()

        assert topic == "omron/bp"

    def test_get_topic_with_user(self):
        """Test topic with user identifier."""
        publisher = MQTTPublisher(base_topic="omron/bp")

        topic = publisher._get_topic("user1")

        assert topic == "omron/bp/user1"

    def test_get_topic_sanitizes_email(self):
        """Test topic sanitizes email addresses."""
        publisher = MQTTPublisher(base_topic="omron/bp")

        topic = publisher._get_topic("user@example.com")

        assert topic == "omron/bp/user_at_example.com"

    def test_get_topic_sanitizes_spaces(self):
        """Test topic sanitizes spaces."""
        publisher = MQTTPublisher(base_topic="omron/bp")

        topic = publisher._get_topic("John Doe")

        assert topic == "omron/bp/John_Doe"

    def test_get_topic_sanitizes_slashes(self):
        """Test topic sanitizes slashes."""
        publisher = MQTTPublisher(base_topic="omron/bp")

        topic = publisher._get_topic("user/slot/1")

        assert topic == "omron/bp/user_slot_1"


class TestMQTTPublisherPayload:
    """Tests for payload building."""

    def test_build_payload_basic(self, sample_reading):
        """Test basic payload building."""
        publisher = MQTTPublisher()

        payload = publisher._build_payload(sample_reading)

        assert payload["systolic"] == 120
        assert payload["diastolic"] == 80
        assert payload["pulse"] == 72
        assert payload["category"] == "normal"
        assert payload["irregular_heartbeat"] is False
        assert payload["body_movement"] is False
        assert payload["user_slot"] == 1
        assert payload["device"] == "OMRON"
        assert "timestamp" in payload
        assert "published_at" in payload

    def test_build_payload_with_flags(self, high_bp_reading):
        """Test payload with irregular heartbeat flag."""
        publisher = MQTTPublisher()

        payload = publisher._build_payload(high_bp_reading)

        assert payload["systolic"] == 160
        assert payload["diastolic"] == 100
        assert payload["category"] == "grade2_hypertension"
        assert payload["irregular_heartbeat"] is True

    def test_build_payload_with_extra_data(self, sample_reading):
        """Test payload with extra data."""
        publisher = MQTTPublisher()

        payload = publisher._build_payload(
            sample_reading,
            extra_data={"source": "test", "custom_field": 123},
        )

        assert payload["source"] == "test"
        assert payload["custom_field"] == 123
        assert payload["systolic"] == 120


class TestMQTTPublisherPublish:
    """Tests for publishing readings."""

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_publish_reading_not_connected(self, mock_client_class, sample_reading):
        """Test publish fails when not connected."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        publisher = MQTTPublisher()
        publisher._connected = False

        result = publisher.publish_reading(sample_reading)

        assert result is False
        mock_client.publish.assert_not_called()

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_publish_reading_success(self, mock_client_class, sample_reading):
        """Test successful publish."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Setup mock publish result
        mock_result = MagicMock()
        mock_result.rc = 0  # MQTT_ERR_SUCCESS
        mock_client.publish.return_value = mock_result

        publisher = MQTTPublisher()
        publisher._connected = True

        result = publisher.publish_reading(sample_reading)

        assert result is True
        mock_client.publish.assert_called_once()

        # Check publish arguments
        call_args = mock_client.publish.call_args
        topic = call_args[0][0]
        payload_json = call_args[0][1]
        kwargs = call_args[1]

        assert topic == DEFAULT_BASE_TOPIC
        assert kwargs["qos"] == 1
        assert kwargs["retain"] is True

        payload = json.loads(payload_json)
        assert payload["systolic"] == 120

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_publish_reading_with_user(self, mock_client_class, sample_reading):
        """Test publish with user identifier."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_result = MagicMock()
        mock_result.rc = 0
        mock_client.publish.return_value = mock_result

        publisher = MQTTPublisher()
        publisher._connected = True

        result = publisher.publish_reading(sample_reading, user_identifier="user1")

        assert result is True
        call_args = mock_client.publish.call_args
        topic = call_args[0][0]
        assert topic == f"{DEFAULT_BASE_TOPIC}/user1"

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_publish_reading_custom_qos(self, mock_client_class, sample_reading):
        """Test publish with custom QoS."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_result = MagicMock()
        mock_result.rc = 0
        mock_client.publish.return_value = mock_result

        publisher = MQTTPublisher()
        publisher._connected = True

        publisher.publish_reading(sample_reading, qos=2, retain=False)

        call_args = mock_client.publish.call_args
        assert call_args[1]["qos"] == 2
        assert call_args[1]["retain"] is False

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_publish_reading_failure(self, mock_client_class, sample_reading):
        """Test publish failure."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_result = MagicMock()
        mock_result.rc = 4  # Some error code
        mock_client.publish.return_value = mock_result

        publisher = MQTTPublisher()
        publisher._connected = True

        result = publisher.publish_reading(sample_reading)

        assert result is False


class TestMQTTPublisherPublishMultiple:
    """Tests for publishing multiple readings."""

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_publish_readings_all_success(self, mock_client_class, multiple_readings):
        """Test publishing multiple readings successfully."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_result = MagicMock()
        mock_result.rc = 0
        mock_client.publish.return_value = mock_result

        publisher = MQTTPublisher()
        publisher._connected = True

        success, failure = publisher.publish_readings(multiple_readings)

        assert success == 3
        assert failure == 0
        assert mock_client.publish.call_count == 3

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_publish_readings_partial_failure(self, mock_client_class, multiple_readings):
        """Test publishing with some failures."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # First two succeed, third fails
        mock_result_ok = MagicMock()
        mock_result_ok.rc = 0
        mock_result_fail = MagicMock()
        mock_result_fail.rc = 4
        mock_client.publish.side_effect = [mock_result_ok, mock_result_ok, mock_result_fail]

        publisher = MQTTPublisher()
        publisher._connected = True

        success, failure = publisher.publish_readings(multiple_readings)

        assert success == 2
        assert failure == 1

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_publish_readings_empty_list(self, mock_client_class):
        """Test publishing empty list."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        publisher = MQTTPublisher()
        publisher._connected = True

        success, failure = publisher.publish_readings([])

        assert success == 0
        assert failure == 0
        mock_client.publish.assert_not_called()


class TestMQTTPublisherStatus:
    """Tests for status publishing."""

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_publish_status_not_connected(self, mock_client_class):
        """Test status publish when not connected."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        publisher = MQTTPublisher()
        publisher._connected = False

        result = publisher.publish_status("online")

        assert result is False

    @patch("src.mqtt_publisher.mqtt.Client")
    def test_publish_status_success(self, mock_client_class):
        """Test successful status publish."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_result = MagicMock()
        mock_result.rc = 0
        mock_client.publish.return_value = mock_result

        publisher = MQTTPublisher(base_topic="omron/bp")
        publisher._connected = True

        result = publisher.publish_status("online", message="Sync complete")

        assert result is True

        call_args = mock_client.publish.call_args
        topic = call_args[0][0]
        payload_json = call_args[0][1]

        assert topic == "omron/bp/status"
        payload = json.loads(payload_json)
        assert payload["status"] == "online"
        assert payload["message"] == "Sync complete"
        assert "timestamp" in payload


class TestCreateMQTTPublisher:
    """Tests for factory function."""

    @patch("src.mqtt_publisher.MQTTPublisher")
    def test_create_mqtt_publisher_success(self, mock_publisher_class):
        """Test factory function success."""
        mock_publisher = MagicMock()
        mock_publisher.connect.return_value = True
        mock_publisher_class.return_value = mock_publisher

        result = create_mqtt_publisher(
            host="test.mqtt.com",
            port=1883,
            username="user",
            password="pass",
        )

        mock_publisher_class.assert_called_once_with(
            host="test.mqtt.com",
            port=1883,
            username="user",
            password="pass",
            base_topic=DEFAULT_BASE_TOPIC,
        )
        mock_publisher.connect.assert_called_once()
        assert result == mock_publisher

    @patch("src.mqtt_publisher.MQTTPublisher")
    def test_create_mqtt_publisher_connection_failure(self, mock_publisher_class):
        """Test factory function with connection failure."""
        mock_publisher = MagicMock()
        mock_publisher.connect.return_value = False
        mock_publisher_class.return_value = mock_publisher

        with pytest.raises(ConnectionError) as exc_info:
            create_mqtt_publisher(host="test.mqtt.com")

        assert "Failed to connect" in str(exc_info.value)


class TestMQTTPublisherCallbacks:
    """Tests for MQTT callbacks."""

    def test_on_connect_success(self):
        """Test on_connect callback with success."""
        publisher = MQTTPublisher()

        # Create mock reason code that indicates success
        mock_reason_code = MagicMock()
        mock_reason_code.is_failure = False

        publisher._on_connect(
            MagicMock(),  # _client
            None,  # _userdata
            MagicMock(),  # _flags
            mock_reason_code,  # reason_code
            None,  # _properties
        )

        assert publisher._connected is True
        assert publisher._last_error is None

    def test_on_connect_failure(self):
        """Test on_connect callback with failure."""
        publisher = MQTTPublisher()

        mock_reason_code = MagicMock()
        mock_reason_code.is_failure = True

        publisher._on_connect(
            MagicMock(),  # _client
            None,  # _userdata
            MagicMock(),  # _flags
            mock_reason_code,  # reason_code
            None,  # _properties
        )

        assert publisher._connected is False
        assert publisher._last_error is not None

    def test_on_disconnect(self):
        """Test on_disconnect callback."""
        publisher = MQTTPublisher()
        publisher._connected = True

        mock_reason_code = MagicMock()

        publisher._on_disconnect(
            MagicMock(),  # _client
            None,  # _userdata
            MagicMock(),  # _disconnect_flags
            mock_reason_code,  # reason_code
            None,  # _properties
        )

        assert publisher._connected is False

    def test_is_connected_property(self):
        """Test is_connected property."""
        publisher = MQTTPublisher()

        assert publisher.is_connected is False

        publisher._connected = True
        assert publisher.is_connected is True
