# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- version list -->

## v0.2.2 (2026-02-07)

### Bug Fixes

- **logging**: Configure file logging for Streamlit UI
  ([#8](https://github.com/JacekZubielik/omron-garmin-bridge/pull/8),
  [`93e09a5`](https://github.com/JacekZubielik/omron-garmin-bridge/commit/93e09a569f641ad5445469eb8ac8e19fcc908f6c))

### Documentation

- Replace ASCII data flow diagram with Mermaid
  ([#8](https://github.com/JacekZubielik/omron-garmin-bridge/pull/8),
  [`93e09a5`](https://github.com/JacekZubielik/omron-garmin-bridge/commit/93e09a569f641ad5445469eb8ac8e19fcc908f6c))


## v0.2.1 (2026-02-07)

### Bug Fixes

- **ci**: Prevent GitHub Actions command injection in workflows
  ([#7](https://github.com/JacekZubielik/omron-garmin-bridge/pull/7),
  [`4b777a3`](https://github.com/JacekZubielik/omron-garmin-bridge/commit/4b777a396a9f2353d8e876aed882e1f32256f2ea))


## v0.2.0 (2026-01-01)

### Code Style

- **main**: Improve code quality with lazy logging and encoding
  ([#6](https://github.com/JacekZubielik/omron-garmin-bridge/pull/6),
  [`73adba5`](https://github.com/JacekZubielik/omron-garmin-bridge/commit/73adba5ae023dc63b51415a6e14f91ad90ac7040))

- **models**: Remove unnecessary elif after return statements
  ([#6](https://github.com/JacekZubielik/omron-garmin-bridge/pull/6),
  [`73adba5`](https://github.com/JacekZubielik/omron-garmin-bridge/commit/73adba5ae023dc63b51415a6e14f91ad90ac7040))

### Features

- **ui**: Add retry pending uploads feature
  ([#6](https://github.com/JacekZubielik/omron-garmin-bridge/pull/6),
  [`73adba5`](https://github.com/JacekZubielik/omron-garmin-bridge/commit/73adba5ae023dc63b51415a6e14f91ad90ac7040))

### Testing

- **main**: Add unit tests for configuration loading
  ([#6](https://github.com/JacekZubielik/omron-garmin-bridge/pull/6),
  [`73adba5`](https://github.com/JacekZubielik/omron-garmin-bridge/commit/73adba5ae023dc63b51415a6e14f91ad90ac7040))

- **models**: Add comprehensive unit tests for BloodPressureReading
  ([#6](https://github.com/JacekZubielik/omron-garmin-bridge/pull/6),
  [`73adba5`](https://github.com/JacekZubielik/omron-garmin-bridge/commit/73adba5ae023dc63b51415a6e14f91ad90ac7040))

- **omron_ble**: Add unit tests for BaseOmronDevice and HEM-7361T driver
  ([#6](https://github.com/JacekZubielik/omron-garmin-bridge/pull/6),
  [`73adba5`](https://github.com/JacekZubielik/omron-garmin-bridge/commit/73adba5ae023dc63b51415a6e14f91ad90ac7040))


## v0.1.8 (2025-12-30)

### Bug Fixes

- **ui**: Replace deprecated use_container_width with width parameter
  ([#5](https://github.com/JacekZubielik/omron-garmin-bridge/pull/5),
  [`63b4165`](https://github.com/JacekZubielik/omron-garmin-bridge/commit/63b41659ee5ae3724cf147fa4398dc79406d7d04))

### Refactoring

- **ui**: Improve history page charts and default user selection
  ([#5](https://github.com/JacekZubielik/omron-garmin-bridge/pull/5),
  [`63b4165`](https://github.com/JacekZubielik/omron-garmin-bridge/commit/63b41659ee5ae3724cf147fa4398dc79406d7d04))


## v0.1.7 (2025-12-29)

### Bug Fixes

- Add per-user Garmin/MQTT toggle persistence in UI
  ([#4](https://github.com/JacekZubielik/omron-garmin-bridge/pull/4),
  [`f21e26d`](https://github.com/JacekZubielik/omron-garmin-bridge/commit/f21e26d8a81e747b22f4eb3d4095b01c57a37d5a))


## v0.1.6 (2025-12-29)

### Bug Fixes

- Add MQTT broker status and Garmin token generation in UI
  ([#3](https://github.com/JacekZubielik/omron-garmin-bridge/pull/3),
  [`bf1f7c4`](https://github.com/JacekZubielik/omron-garmin-bridge/commit/bf1f7c444aedc9c7c6e82717e4d163e3f20baf09))

### Documentation

- **readme**: Add Docker, multi-user, and UI features documentation
  ([#3](https://github.com/JacekZubielik/omron-garmin-bridge/pull/3),
  [`bf1f7c4`](https://github.com/JacekZubielik/omron-garmin-bridge/commit/bf1f7c444aedc9c7c6e82717e4d163e3f20baf09))


## v0.1.5 (2025-12-29)

### Bug Fixes

- **config**: Replace global enabled flags with per-user garmin_enabled/mqtt_enabled
  ([#2](https://github.com/JacekZubielik/omron-garmin-bridge/pull/2),
  [`513e3d8`](https://github.com/JacekZubielik/omron-garmin-bridge/commit/513e3d85394565a9b13ad50b90339afa84a2f7eb))

- **ui**: Add per-user sync options and fix dev compose volumes
  ([#2](https://github.com/JacekZubielik/omron-garmin-bridge/pull/2),
  [`513e3d8`](https://github.com/JacekZubielik/omron-garmin-bridge/commit/513e3d85394565a9b13ad50b90339afa84a2f7eb))

- **ui**: Add user slot filter and multi-user Garmin token support
  ([#2](https://github.com/JacekZubielik/omron-garmin-bridge/pull/2),
  [`513e3d8`](https://github.com/JacekZubielik/omron-garmin-bridge/commit/513e3d85394565a9b13ad50b90339afa84a2f7eb))

### Refactoring

- **settings**: Remove per-user garmin/mqtt enable options
  ([#2](https://github.com/JacekZubielik/omron-garmin-bridge/pull/2),
  [`513e3d8`](https://github.com/JacekZubielik/omron-garmin-bridge/commit/513e3d85394565a9b13ad50b90339afa84a2f7eb))


## v0.1.4 (2025-12-29)

### Bug Fixes

- **ci**: Use pdm run python in Docker test
  ([#1](https://github.com/JacekZubielik/omron-garmin-bridge/pull/1),
  [`b299a3a`](https://github.com/JacekZubielik/omron-garmin-bridge/commit/b299a3a27f49fca3abbf61f0603cde651042a684))

- **docker**: Add docker-compose files for prod and dev images
  ([#1](https://github.com/JacekZubielik/omron-garmin-bridge/pull/1),
  [`b299a3a`](https://github.com/JacekZubielik/omron-garmin-bridge/commit/b299a3a27f49fca3abbf61f0603cde651042a684))

- **ui**: Add dynamic version display with environment badge
  ([#1](https://github.com/JacekZubielik/omron-garmin-bridge/pull/1),
  [`b299a3a`](https://github.com/JacekZubielik/omron-garmin-bridge/commit/b299a3a27f49fca3abbf61f0603cde651042a684))

### Documentation

- **changelog**: Fix Unreleased section to v0.1.2 [skip ci]
  ([`225ec54`](https://github.com/JacekZubielik/omron-garmin-bridge/commit/225ec545be689c6b7c17710bf41d1a1340340ae2))


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
