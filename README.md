# OMRON Garmin Bridge

Bridge between OMRON blood pressure monitors (BLE) and Garmin Connect + MQTT.

## Features

- Read blood pressure data from OMRON devices via Bluetooth LE
- Upload measurements to Garmin Connect
- Publish measurements via MQTT (Home Assistant compatible)
- Local deduplication (SQLite) + Garmin API duplicate check
- Direct connection for bonded devices (no scanning required)
- **Streamlit Web UI** for monitoring and manual sync
- CLI tools for pairing, reading, and syncing
- 72 unit tests with full coverage

## Supported Devices

| Model         | Name          | Status              |
| ------------- | ------------- | ------------------- |
| **HEM-7361T** | M7 Intelli IT | Tested and verified |
| HEM-7155T     | M4            | Supported           |
| HEM-7322T     | M700          | Supported           |
| HEM-7600T     | Evolv         | Supported           |

## Quick Start

```bash
# Install PDM (if not installed)
curl -sSL https://pdm-project.org/install-pdm.py | python3 -

# Clone and install
git clone https://github.com/JacekZubielik/omron-garmin-bridge.git
cd omron-garmin-bridge
pdm install

# Copy and configure
cp config/config.yaml.example config/config.yaml
# Edit config/config.yaml with your settings

# Import Garmin OAuth tokens
pdm run python tools/import_tokens.py

# Run sync (press BT button on OMRON first!)
pdm run python -m src.main sync
```

## Docker

The bridge is available as a Docker image for easy deployment.

### Production

```bash
cd docker

# Pull and run latest stable image
docker compose -f docker-compose.yaml pull
docker compose -f docker-compose.yaml up -d

# View logs
docker compose -f docker-compose.yaml logs -f
```

### Development

```bash
cd docker

# Pull and run dev image (built from feature branches)
docker compose -f docker-compose.dev.yaml pull
docker compose -f docker-compose.dev.yaml up -d
```

### Requirements

- Bluetooth adapter on host (uses `network_mode: host` for BLE access)
- `config/config.yaml` configured
- Garmin tokens generated

The Web UI is available at `http://localhost:8501`.

## Web UI (Streamlit)

The bridge includes a web dashboard for monitoring and manual sync.

```bash
pdm run streamlit run streamlit_app/app.py
```

Open `http://localhost:8501` in your browser.

The UI displays version and environment badge (dev/prod/local) in the sidebar footer.

### Pages

| Page          | Description                                                     |
| ------------- | --------------------------------------------------------------- |
| **Dashboard** | Last reading, average BP metrics, user filter (All/User1/User2) |
| **History**   | BP/pulse charts, filterable table, CSV export                   |
| **Sync**      | Manual sync with step-by-step instructions                      |
| **Settings**  | Configuration, Bluetooth pairing, Garmin tokens, MQTT status    |

### Settings Page Features

- **Bluetooth pairing** - Scan and pair OMRON devices from the sidebar
- **User mapping** - Map OMRON slots (1/2) to Garmin accounts
- **Garmin token generation** - Generate OAuth tokens directly in UI (no CLI needed)
- **MQTT broker status** - Real-time connection indicator
- **Configuration editor** - Edit and save config.yaml

### Icons

The Web UI uses [Font Awesome 6](https://fontawesome.com/) icons for a clean, consistent look. Icons are loaded via CDN and include color-coded status indicators (success, warning, danger).

### Sync Page

The Sync page guides you through the synchronization process:

1. Press **BT button** on OMRON device (Bluetooth icon blinks)
2. Check the confirmation box
3. Click **Start Sync** within 30 seconds
4. View results and logs

**Important:** OMRON stays in Bluetooth mode for only ~30 seconds after pressing the BT button.

## CLI Usage

### Reading from Device

```bash
# Scan for OMRON devices
pdm run python tools/scan_devices.py

# Read all records from device (press BT button on OMRON first!)
pdm run python tools/read_device.py --mac 00:5F:BF:91:9B:4B

# Sync records to local database
pdm run python tools/sync_records.py --mac 00:5F:BF:91:9B:4B
```

### Main Application

```bash
# One-time sync (reads from OMRON -> uploads to Garmin + MQTT)
pdm run python -m src.main sync

# Sync only to MQTT (skip Garmin)
pdm run python -m src.main sync --mqtt-only

# Sync only to Garmin (skip MQTT)
pdm run python -m src.main sync --garmin-only

# Dry run (show what would happen)
pdm run python -m src.main sync --dry-run

# Continuous mode (daemon with scheduler)
pdm run python -m src.main daemon --interval 60
```

### Pairing New Device

```bash
# 1. Put OMRON in pairing mode (hold BT button until "P" appears)
# 2. Run pairing tool
pdm run python tools/pair_device.py --mac 00:5F:BF:91:9B:4B
```

## Configuration

Edit `config/config.yaml`:

```yaml
omron:
  device_model: "HEM-7361T"
  mac_address: "00:5F:BF:91:9B:4B" # Optional - will scan if not set
  poll_interval_minutes: 60

users:
  - name: "User1"
    omron_slot: 1 # Slot in OMRON device (1 or 2)
    garmin_email: "user1@example.com"
  - name: "User2"
    omron_slot: 2
    garmin_email: "user2@example.com"

garmin:
  tokens_path: "./data/tokens" # OAuth tokens stored per user

mqtt:
  host: "192.168.40.19"
  port: 1883
  base_topic: "omron/blood_pressure"

deduplication:
  database_path: "./data/omron.db"
```

### Multi-User Support

The bridge supports multiple users with separate Garmin accounts:

- Each user is mapped to an OMRON device slot (1 or 2)
- OAuth tokens are stored per user in `data/tokens/<email>/`
- Generate tokens via Web UI (Settings > Garmin Connect) or CLI:

```bash
# Generate token for specific user
pdm run python tools/import_tokens.py --email user1@example.com

# Generate tokens for multiple users
pdm run python tools/import_tokens.py --email user1@example.com --email user2@example.com
```

## Data Flow

```
OMRON Device (BLE)
       |
       v
+------------------+
|  OmronBLEClient  | <- Read records via Bluetooth LE
+------------------+
       |
       v
+------------------+
| DuplicateFilter  | <- Check against local SQLite database
|    (SQLite)      |
+------------------+
       |
       +------------------------+
       v                        v
+------------------+    +------------------+
|  GarminUploader  |    |  MQTTPublisher   |
| (+ API dedup)    |    | (QoS 1, retain)  |
+------------------+    +------------------+
       |                        |
       v                        v
  Garmin Connect           MQTT Broker
```

## MQTT Payload

```json
{
  "timestamp": "2025-12-27T10:12:57",
  "systolic": 136,
  "diastolic": 82,
  "pulse": 66,
  "category": "high_normal",
  "irregular_heartbeat": false,
  "body_movement": false,
  "user_slot": 1,
  "device": "OMRON HEM-7361T"
}
```

## Blood Pressure Categories

Based on WHO/ESC classification:

| Category             | Systolic | Diastolic |
| -------------------- | -------- | --------- |
| Optimal              | < 120    | < 80      |
| Normal               | < 130    | < 85      |
| High Normal          | < 140    | < 90      |
| Grade 1 Hypertension | < 160    | < 100     |
| Grade 2 Hypertension | < 180    | < 110     |
| Grade 3 Hypertension | >= 180   | >= 110    |

## Development

```bash
# Install with dev dependencies
pdm install -G test -G lint -G dev

# Run tests (72 tests)
pdm run pytest

# Run tests with coverage
pdm run pytest --cov=src --cov-report=html

# Linting
pdm run ruff check src/
pdm run mypy src/

# Format code
pdm run black src/ tests/
pdm run isort src/ tests/
```

## Project Structure

```
omron-garmin-bridge/
├── src/
│   ├── main.py              # Main entry point (sync, daemon)
│   ├── models.py            # BloodPressureReading dataclass
│   ├── duplicate_filter.py  # SQLite deduplication
│   ├── garmin_uploader.py   # Garmin Connect upload (multi-user)
│   ├── mqtt_publisher.py    # MQTT publishing
│   └── omron_ble/           # BLE communication
│       ├── client.py        # High-level BLE client
│       ├── protocol.py      # Low-level OMRON protocol
│       └── devices/         # Device-specific implementations
├── streamlit_app/           # Web UI
│   ├── app.py               # Router (st.navigation)
│   ├── components/
│   │   ├── icons.py         # Font Awesome icon helper
│   │   └── version.py       # Version display with env badge
│   └── pages/
│       ├── 0_Dashboard.py   # Last reading, averages, user filter
│       ├── 1_History.py     # Charts and history table
│       ├── 2_Sync.py        # Manual sync
│       └── 3_Settings.py    # Config, BT pairing, token generation
├── docker/                  # Docker deployment
│   ├── Dockerfile
│   ├── docker-compose.yaml      # Production
│   └── docker-compose.dev.yaml  # Development
├── tools/                   # CLI utilities
│   ├── import_tokens.py     # Generate Garmin OAuth tokens
│   ├── pair_device.py       # Bluetooth pairing
│   ├── scan_devices.py      # Scan for OMRON devices
│   └── read_device.py       # Read records from device
├── tests/                   # Unit tests (72 tests)
├── config/                  # Configuration files
└── data/                    # SQLite database, tokens per user
```

## Test Results

| Module          | Tests  | Description          |
| --------------- | ------ | -------------------- |
| DuplicateFilter | 22     | SQLite deduplication |
| GarminUploader  | 19     | Garmin Connect API   |
| MQTTPublisher   | 31     | MQTT publishing      |
| **Total**       | **72** | All passing          |

## Troubleshooting

### Device not found

1. Press the **BT button** on OMRON device before connecting
2. Make sure device is in range (~5 meters)
3. Check if device is already paired: `bluetoothctl devices`

### Bluetooth connection lost (ATT error 0x0e)

This error means the OMRON device timed out waiting for connection:

1. Press BT button on OMRON
2. Start sync **within 30 seconds**
3. If using Web UI, check the confirmation box immediately after pressing BT

### Connection fails immediately

For bonded devices, the bridge uses direct connection (no scanning). If this fails:

```bash
# Remove and re-pair
bluetoothctl remove 00:5F:BF:91:9B:4B
pdm run python tools/pair_device.py --mac 00:5F:BF:91:9B:4B
```

### Garmin login fails

Generate OAuth tokens:

```bash
pdm run python tools/import_tokens.py
```

### MQTT connection refused

Check that the MQTT broker is running:

```bash
# Test connection
mosquitto_pub -h 192.168.40.19 -t test -m "hello"
```

## Acknowledgments

This project uses code and concepts from the following projects:

| Project                                                                    | Author          | Usage                                                                                  | License              |
| -------------------------------------------------------------------------- | --------------- | -------------------------------------------------------------------------------------- | -------------------- |
| [omblepy](https://github.com/userx14/omblepy)                              | userx14         | BLE protocol implementation (`src/omron_ble/`) - core communication with OMRON devices | No license specified |
| [UBPM](https://codeberg.org/LazyT/ubpm)                                    | LazyT           | Protocol analysis and multi-channel BLE reception concepts                             | GPL-3.0              |
| [export2garmin](https://github.com/RobertWojtowicz/export2garmin)          | RobertWojtowicz | Garmin Connect integration patterns                                                    | MIT                  |
| [python-garminconnect](https://github.com/cyberjunky/python-garminconnect) | cyberjunky      | Garmin Connect API library (used as dependency)                                        | MIT                  |
| [bleak](https://github.com/hbldh/bleak)                                    | hbldh           | Async BLE library for Python (used as dependency)                                      | MIT                  |

Special thanks to:

- **userx14** for reverse-engineering the OMRON BLE protocol in omblepy
- **LazyT** for UBPM which provided insights into multi-channel BLE communication
- All contributors who tested various OMRON device models

## License

MIT
