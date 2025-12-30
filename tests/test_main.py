"""Tests for src/main.py - main entry point helper functions.

This module tests the helper functions in main.py:
- load_config: Configuration loading from YAML
- DEFAULT_CONFIG: Default configuration values

Note: setup_logging tests are limited due to pytest's log capturing.
"""

import os
import tempfile

import pytest
import yaml

from src.main import DEFAULT_CONFIG, load_config

# ============== FIXTURES ==============


@pytest.fixture
def temp_config_dir():
    """Create temporary directory for config files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_config():
    """Sample configuration dictionary."""
    return {
        "omron": {
            "device_model": "HEM-7361T",
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "poll_interval_minutes": 30,
        },
        "garmin": {
            "enabled": False,
            "tokens_path": "/custom/path",
        },
        "mqtt": {
            "enabled": True,
            "host": "192.168.1.100",
            "port": 1884,
        },
    }


# ============== TEST CLASSES ==============


class TestDefaultConfig:
    """Tests for DEFAULT_CONFIG constant."""

    def test_has_omron_section(self):
        """Test DEFAULT_CONFIG has omron section."""
        assert "omron" in DEFAULT_CONFIG

    def test_has_garmin_section(self):
        """Test DEFAULT_CONFIG has garmin section."""
        assert "garmin" in DEFAULT_CONFIG

    def test_has_mqtt_section(self):
        """Test DEFAULT_CONFIG has mqtt section."""
        assert "mqtt" in DEFAULT_CONFIG

    def test_has_deduplication_section(self):
        """Test DEFAULT_CONFIG has deduplication section."""
        assert "deduplication" in DEFAULT_CONFIG

    def test_has_logging_section(self):
        """Test DEFAULT_CONFIG has logging section."""
        assert "logging" in DEFAULT_CONFIG

    def test_omron_default_model(self):
        """Test default OMRON device model."""
        assert DEFAULT_CONFIG["omron"]["device_model"] == "HEM-7361T"

    def test_omron_default_poll_interval(self):
        """Test default poll interval."""
        assert DEFAULT_CONFIG["omron"]["poll_interval_minutes"] == 60

    def test_omron_default_mac_address_is_none(self):
        """Test default MAC address is None."""
        assert DEFAULT_CONFIG["omron"]["mac_address"] is None

    def test_omron_default_read_mode(self):
        """Test default read mode."""
        assert DEFAULT_CONFIG["omron"]["read_mode"] == "new_only"

    def test_omron_default_sync_time(self):
        """Test default sync_time is True."""
        assert DEFAULT_CONFIG["omron"]["sync_time"] is True

    def test_garmin_enabled_by_default(self):
        """Test Garmin is enabled by default."""
        assert DEFAULT_CONFIG["garmin"]["enabled"] is True

    def test_garmin_default_tokens_path(self):
        """Test default Garmin tokens path."""
        assert DEFAULT_CONFIG["garmin"]["tokens_path"] == "./data/tokens"

    def test_mqtt_enabled_by_default(self):
        """Test MQTT is enabled by default."""
        assert DEFAULT_CONFIG["mqtt"]["enabled"] is True

    def test_mqtt_default_host(self):
        """Test default MQTT host."""
        assert DEFAULT_CONFIG["mqtt"]["host"] == "192.168.40.19"

    def test_mqtt_default_port(self):
        """Test default MQTT port."""
        assert DEFAULT_CONFIG["mqtt"]["port"] == 1883

    def test_mqtt_default_base_topic(self):
        """Test default MQTT base topic."""
        assert DEFAULT_CONFIG["mqtt"]["base_topic"] == "omron/blood_pressure"

    def test_mqtt_default_username_is_none(self):
        """Test default MQTT username is None."""
        assert DEFAULT_CONFIG["mqtt"]["username"] is None

    def test_mqtt_default_password_is_none(self):
        """Test default MQTT password is None."""
        assert DEFAULT_CONFIG["mqtt"]["password"] is None

    def test_deduplication_default_database_path(self):
        """Test default deduplication database path."""
        assert DEFAULT_CONFIG["deduplication"]["database_path"] == "./data/omron.db"

    def test_logging_default_level(self):
        """Test default logging level."""
        assert DEFAULT_CONFIG["logging"]["level"] == "INFO"

    def test_logging_default_file_is_none(self):
        """Test default log file is None."""
        assert DEFAULT_CONFIG["logging"]["file"] is None


class TestLoadConfigNoFile:
    """Tests for load_config when no config file exists."""

    def test_returns_defaults_when_no_path(self):
        """Test returns defaults when config_path is None."""
        config = load_config(None)
        assert config["omron"]["device_model"] == DEFAULT_CONFIG["omron"]["device_model"]
        assert config["mqtt"]["port"] == DEFAULT_CONFIG["mqtt"]["port"]

    def test_returns_defaults_when_file_not_found(self, temp_config_dir):
        """Test returns defaults when config file doesn't exist."""
        missing_path = os.path.join(temp_config_dir, "nonexistent.yaml")
        config = load_config(missing_path)
        assert config["omron"]["device_model"] == DEFAULT_CONFIG["omron"]["device_model"]

    def test_returns_copy_not_reference(self):
        """Test returns a copy, not the DEFAULT_CONFIG reference."""
        config = load_config(None)
        config["test_key"] = "test_value"
        assert "test_key" not in DEFAULT_CONFIG


class TestLoadConfigFromFile:
    """Tests for load_config when reading from file."""

    def test_loads_valid_yaml(self, temp_config_dir, sample_config):
        """Test loading valid YAML config file."""
        config_path = os.path.join(temp_config_dir, "config.yaml")
        with open(config_path, "w") as f:
            yaml.dump(sample_config, f)

        config = load_config(config_path)

        assert config["omron"]["mac_address"] == "AA:BB:CC:DD:EE:FF"
        assert config["garmin"]["enabled"] is False
        assert config["mqtt"]["port"] == 1884

    def test_merges_with_defaults_partial_section(self, temp_config_dir):
        """Test partial section config is merged with defaults."""
        partial_config = {
            "omron": {
                "mac_address": "11:22:33:44:55:66",
                # device_model not specified - should use default
            }
        }
        config_path = os.path.join(temp_config_dir, "partial.yaml")
        with open(config_path, "w") as f:
            yaml.dump(partial_config, f)

        config = load_config(config_path)

        # Should have user value
        assert config["omron"]["mac_address"] == "11:22:33:44:55:66"
        # Should keep defaults for unspecified in same section
        assert config["omron"]["device_model"] == "HEM-7361T"

    def test_preserves_unspecified_sections(self, temp_config_dir):
        """Test sections not in file keep defaults."""
        config_only_omron = {
            "omron": {
                "device_model": "Custom-Model",
            }
        }
        config_path = os.path.join(temp_config_dir, "omron_only.yaml")
        with open(config_path, "w") as f:
            yaml.dump(config_only_omron, f)

        config = load_config(config_path)

        # Should have custom omron value
        assert config["omron"]["device_model"] == "Custom-Model"
        # mqtt section should exist (defaults merged in)
        assert "mqtt" in config
        assert "port" in config["mqtt"]

    def test_handles_empty_yaml(self, temp_config_dir):
        """Test handling of empty YAML file."""
        config_path = os.path.join(temp_config_dir, "empty.yaml")
        with open(config_path, "w") as f:
            f.write("")

        config = load_config(config_path)
        assert config["omron"]["device_model"] == DEFAULT_CONFIG["omron"]["device_model"]

    def test_handles_yaml_with_only_comments(self, temp_config_dir):
        """Test handling of YAML file with only comments."""
        config_path = os.path.join(temp_config_dir, "comments.yaml")
        with open(config_path, "w") as f:
            f.write("# This is a comment\n# Another comment\n")

        config = load_config(config_path)
        assert config["omron"]["device_model"] == DEFAULT_CONFIG["omron"]["device_model"]


class TestLoadConfigDeepMerge:
    """Tests for deep merge behavior in load_config."""

    def test_updates_nested_dict_values(self, temp_config_dir):
        """Test updating specific values in nested dict."""
        user_config = {
            "mqtt": {
                "host": "custom.host.com",
            }
        }
        config_path = os.path.join(temp_config_dir, "mqtt_host.yaml")
        with open(config_path, "w") as f:
            yaml.dump(user_config, f)

        config = load_config(config_path)

        assert config["mqtt"]["host"] == "custom.host.com"
        # port should be from user config if section was fully replaced,
        # or default if deep merge is used
        # Based on the load_config implementation, it does section.update()
        # which means other keys in mqtt remain from default

    def test_adds_custom_section(self, temp_config_dir):
        """Test adding entirely custom section."""
        user_config = {
            "custom_section": {
                "key1": "value1",
                "key2": 42,
            }
        }
        config_path = os.path.join(temp_config_dir, "custom.yaml")
        with open(config_path, "w") as f:
            yaml.dump(user_config, f)

        config = load_config(config_path)

        assert config["custom_section"]["key1"] == "value1"
        assert config["custom_section"]["key2"] == 42


class TestLoadConfigEdgeCases:
    """Edge case tests for load_config."""

    def test_handles_none_values_in_yaml(self, temp_config_dir):
        """Test handling of null/None values in YAML."""
        config_with_nulls = {
            "omron": {
                "mac_address": None,
            }
        }
        config_path = os.path.join(temp_config_dir, "nulls.yaml")
        with open(config_path, "w") as f:
            yaml.dump(config_with_nulls, f)

        config = load_config(config_path)
        assert config["omron"]["mac_address"] is None

    def test_handles_list_values(self, temp_config_dir):
        """Test handling of list values in YAML."""
        config_with_list = {
            "custom": {
                "items": ["a", "b", "c"],
            }
        }
        config_path = os.path.join(temp_config_dir, "list.yaml")
        with open(config_path, "w") as f:
            yaml.dump(config_with_list, f)

        config = load_config(config_path)
        assert config["custom"]["items"] == ["a", "b", "c"]

    def test_handles_integer_values(self, temp_config_dir):
        """Test handling of integer values in YAML."""
        config_with_int = {
            "mqtt": {
                "port": 8883,
            }
        }
        config_path = os.path.join(temp_config_dir, "int.yaml")
        with open(config_path, "w") as f:
            yaml.dump(config_with_int, f)

        config = load_config(config_path)
        assert config["mqtt"]["port"] == 8883
        assert isinstance(config["mqtt"]["port"], int)

    def test_handles_boolean_values(self, temp_config_dir):
        """Test handling of boolean values in YAML."""
        config_with_bool = {
            "garmin": {
                "enabled": False,
            },
            "mqtt": {
                "enabled": True,
            },
        }
        config_path = os.path.join(temp_config_dir, "bool.yaml")
        with open(config_path, "w") as f:
            yaml.dump(config_with_bool, f)

        config = load_config(config_path)
        assert config["garmin"]["enabled"] is False
        assert config["mqtt"]["enabled"] is True

    def test_handles_string_with_special_chars(self, temp_config_dir):
        """Test handling of strings with special characters."""
        config_with_special = {
            "mqtt": {
                "password": "p@ss:w0rd!#$%",
            }
        }
        config_path = os.path.join(temp_config_dir, "special.yaml")
        with open(config_path, "w") as f:
            yaml.dump(config_with_special, f)

        config = load_config(config_path)
        assert config["mqtt"]["password"] == "p@ss:w0rd!#$%"


class TestLoadConfigOverrides:
    """Tests for config value overrides."""

    def test_override_poll_interval(self, temp_config_dir):
        """Test overriding poll interval."""
        config = {
            "omron": {
                "poll_interval_minutes": 5,
            }
        }
        config_path = os.path.join(temp_config_dir, "poll.yaml")
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        result = load_config(config_path)
        assert result["omron"]["poll_interval_minutes"] == 5

    def test_override_database_path(self, temp_config_dir):
        """Test overriding database path."""
        config = {
            "deduplication": {
                "database_path": "/custom/path/db.sqlite",
            }
        }
        config_path = os.path.join(temp_config_dir, "db.yaml")
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        result = load_config(config_path)
        assert result["deduplication"]["database_path"] == "/custom/path/db.sqlite"

    def test_override_logging_level(self, temp_config_dir):
        """Test overriding logging level."""
        config = {
            "logging": {
                "level": "DEBUG",
            }
        }
        config_path = os.path.join(temp_config_dir, "log.yaml")
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        result = load_config(config_path)
        assert result["logging"]["level"] == "DEBUG"
