# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- version list -->

## v0.1.3 (2025-12-29)

### Bug Fixes

- **ci**: Fix changelog generation and release workflow
  ([`a9703d4`](https://github.com/JacekZubielik/omron-garmin-bridge/commit/a9703d4ce7e76512c2988d48ddfa2062a357cac7))

## v0.1.2 (2025-12-29)

### Bug Fixes

- **docker**: Add README.md to Dockerfile for pdm install
  ([`a0253ac`](https://github.com/JacekZubielik/omron-garmin-bridge/commit/a0253aca0837dd1494d58de341f22ae5b1e0c5e4))

## v0.1.1 (2025-12-29)

### Bug Fixes

- **ci**: Add allow_zero_version=true for semantic-release
  ([`69683c4`](https://github.com/JacekZubielik/omron-garmin-bridge/commit/69683c45b15e651a7e5864d6433ebc6f251bea60))

- **docs**: Test semantic-release v0.1.1
  ([`3db9a7b`](https://github.com/JacekZubielik/omron-garmin-bridge/commit/3db9a7bc734c7e19b7225b5273d918161fcc9087))

## [0.1.0] - 2025-12-28

First beta release with full core functionality.

### Added

- **OMRON BLE Communication**
  - Support for HEM-7361T (M7 Intelli IT) - tested and verified
  - Support for HEM-7155T, HEM-7322T, HEM-7600T (untested)
  - Direct connection for bonded devices (no scanning required)
  - Read all records or new-only mode
  - Device pairing via CLI tool

- **Garmin Connect Integration**
  - OAuth token-based authentication
  - Blood pressure upload with automatic deduplication
  - Two-layer dedup: local SQLite + Garmin API check
  - IHB/MOV flags saved in notes (Garmin has no dedicated fields)

- **MQTT Publishing**
  - QoS 1 for reliable delivery
  - Retained messages for last-known-value
  - JSON payload with all measurement data
  - Configurable topics

- **Local Storage**
  - SQLite database for deduplication and history
  - CSV backup support

- **Streamlit Web UI**
  - Dashboard: last reading, average BP metrics
  - History: charts (Plotly), filterable table, CSV export
  - Sync: step-by-step manual synchronization
  - Settings: configuration, Bluetooth pairing, user mapping
  - Font Awesome 6 icons, dark/light theme support

- **CLI Tools**
  - `scan_devices.py` - scan for BLE devices
  - `pair_device.py` - pair OMRON device
  - `read_device.py` - one-time read from device
  - `sync_records.py` - sync to local database
  - `import_tokens.py` - generate Garmin OAuth tokens

- **Testing**
  - 72 unit tests (pytest)
  - Full coverage for DuplicateFilter, GarminUploader, MQTTPublisher
