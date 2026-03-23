---
name: db-manage
description: >-
  This skill should be used when the user asks to "check database", "database stats",
  "pending uploads", "retry uploads", "cleanup old records", "show history",
  "how many records", "db status", "purge database", "export records",
  or mentions SQLite database operations for blood pressure records.
---

# Database Management

Manage the SQLite deduplication database that tracks all blood pressure readings
and their upload status to Garmin Connect and MQTT.

## Database Location

Default: `data/omron.db` (configurable via `config.yaml` → `deduplication.database_path`)

Docker container: `/app/data/omron.db` (mounted from host `data/`)

## Schema

```sql
CREATE TABLE uploaded_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_hash TEXT UNIQUE NOT NULL,
    timestamp TEXT NOT NULL,
    systolic INTEGER NOT NULL,
    diastolic INTEGER NOT NULL,
    pulse INTEGER NOT NULL,
    irregular_heartbeat BOOLEAN DEFAULT FALSE,
    body_movement BOOLEAN DEFAULT FALSE,
    user_slot INTEGER DEFAULT 1,
    category TEXT,
    uploaded_at TEXT NOT NULL,
    garmin_uploaded BOOLEAN DEFAULT FALSE,
    mqtt_published BOOLEAN DEFAULT FALSE
);
```

Indexes: `record_hash` (unique), `timestamp`, `user_slot`

Journal mode: **WAL** (concurrent read/write safe)

## Quick Stats

```bash
pdm run python scripts/db_stats.py
```

Shows: total records, Garmin uploaded count, MQTT published count, pending counts,
date range, average BP values.

## Common Operations

### View pending uploads

```bash
pdm run python scripts/db_stats.py --pending
```

### Retry pending Garmin uploads

```bash
pdm run python tools/sync_records.py
```

### View recent history

```bash
pdm run python scripts/db_stats.py --history 20
```

### Cleanup old records

```bash
pdm run python scripts/db_stats.py --cleanup 365
```

Deletes records older than N days.

## Record Hash

Deduplication key: `{timestamp_iso}_{systolic}_{diastolic}_{pulse}_{user_slot}`

Two readings with identical timestamp + BP values + user slot are treated as duplicates.

## Upload Tracking

Each record has independent flags:
- `garmin_uploaded` — set to TRUE when successfully uploaded to Garmin
- `mqtt_published` — set to TRUE when successfully published to MQTT

A record may be uploaded to Garmin but not yet published to MQTT (or vice versa).
Retry operations only target records where the specific service flag is FALSE.

## BP Categories (WHO/ESC)

Categories stored in `category` column, classified by max(systolic_grade, diastolic_grade):

| Category | Systolic | Diastolic |
|----------|----------|-----------|
| optimal | < 120 | < 80 |
| normal | 120-129 | 80-84 |
| high_normal | 130-139 | 85-89 |
| grade1_hypertension | 140-159 | 90-99 |
| grade2_hypertension | 160-179 | 100-109 |
| grade3_hypertension | ≥ 180 | ≥ 110 |

## Scripts

- **`scripts/db_stats.py`** — Database statistics, history, pending, and cleanup operations
