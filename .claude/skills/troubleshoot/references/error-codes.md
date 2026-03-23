# Error Code Reference

## BLE Errors

| Error | Source | Cause | Recovery |
|-------|--------|-------|----------|
| `ATT error 0x0e` | BlueZ | Device timeout (30s BT window expired) | Press BT button, retry |
| `ATT error 0x05` | BlueZ | Authentication failure | Re-pair device |
| `ATT error 0x06` | BlueZ | Request not supported | Wrong device model |
| `org.bluez.Error.Failed` | D-Bus | BlueZ internal error | Restart bluetooth: `sudo systemctl restart bluetooth` |
| `org.bluez.Error.NotReady` | D-Bus | Adapter not ready | `sudo hciconfig hci0 up` |
| `ConnectionError: No OMRON devices found` | client.py | No device in scan range | Press BT button, move closer |
| `ConnectionError: Required BLE service not found` | client.py | Wrong device or service discovery race | Retry, or specify MAC |
| `TimeoutError: Unlock timed out` | protocol.py | Device didn't respond to unlock | Re-pair device |
| `ValueError: Pairing key does not match` | protocol.py | Key mismatch (re-paired elsewhere) | `bluetoothctl remove`, re-pair |
| `ValueError: CRC error` (logged as warning) | protocol.py | Data corruption in BLE packet | Automatic retry (up to 5×) |
| `TimeoutError: Transmission failed after 5 retries` | protocol.py | Persistent communication failure | Move closer, retry |

## Garmin Errors

| Error | Source | Cause | Recovery |
|-------|--------|-------|----------|
| `GarminConnectAuthenticationError` | garminconnect | Expired/invalid tokens | Regenerate with `import_tokens.py` |
| `FileNotFoundError: Token directory not found` | garmin_uploader.py | No tokens for email | Run `import_tokens.py --email <email>` |
| `RuntimeError: Not logged in` | garmin_uploader.py | `login()` not called or failed | Check `_init_garmin()` return value |
| `HTTPError 429` | garminconnect | Rate limiting | Wait 5 minutes, retry |
| `HTTPError 503` | garminconnect | Garmin service outage | Wait and retry later |

## MQTT Errors

| Error | Source | Cause | Recovery |
|-------|--------|-------|----------|
| `MQTT connection timeout after Ns` | mqtt_publisher.py | Broker unreachable | Check host/port, firewall |
| `CONNACK_REFUSED_NOT_AUTHORIZED` | paho-mqtt | Wrong credentials | Check username/password in config |
| `CONNACK_REFUSED_SERVER_UNAVAILABLE` | paho-mqtt | Broker down | Restart MQTT broker |
| `Connection refused` | paho-mqtt | Wrong port or broker not running | Verify broker status |
| `Resource not accessible` | paho-mqtt | TLS required but not configured | Add TLS config if broker requires |

## SQLite Errors

| Error | Source | Cause | Recovery |
|-------|--------|-------|----------|
| `sqlite3.OperationalError: database is locked` | duplicate_filter.py | Concurrent access without WAL | Upgrade to WAL mode (now default) |
| `sqlite3.IntegrityError: UNIQUE constraint` | duplicate_filter.py | Duplicate record_hash | Expected behavior (dedup working) |
| `sqlite3.OperationalError: no such table` | duplicate_filter.py | Corrupted or new DB | `_init_db()` creates table automatically |

## Python Runtime Errors

| Error | Source | Cause | Recovery |
|-------|--------|-------|----------|
| `ModuleNotFoundError: No module named 'bleak'` | import | Missing dependencies | `pdm install` |
| `AttributeError: _pairing_mode` | client.py (old) | Pre-fix version | Update to latest code |
| `ValueError: day is out of range` | duplicate_filter.py (old) | Broken date arithmetic | Update to latest code |
