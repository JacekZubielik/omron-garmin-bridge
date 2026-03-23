# OMRON BLE Protocol Reference

Based on [omblepy](https://github.com/userx14/omblepy) reverse engineering.

## Service UUID

```
PARENT_SERVICE_UUID = "ecbe3980-c9a2-11e1-b1bd-0002a5d5c51b"
```

All OMRON BLE devices expose this service. Connection verification checks for its presence.

## Channel Architecture

Communication uses 4 TX and 4 RX channels, each carrying 16-byte packets:

| Direction | Channel | UUID |
|-----------|---------|------|
| TX 0 | `db5b55e0-aee7-11e1-965e-0002a5d5c51b` | Primary transmit |
| TX 1-3 | See `protocol.py` | Overflow for large packets |
| RX 0-3 | `49123040-...` through `560f1420-...` | Receive channels |

## Packet Structure

```
[packet_size][packet_type:2][eeprom_addr:2][data_length][data...][pad][crc]
```

- **CRC**: XOR of all bytes must equal 0
- **Multi-channel**: Packets > 16 bytes split across channels, reassembled in `_rx_callback`

## Key Commands

| Command | Hex | Purpose |
|---------|-----|---------|
| Start transmission | `0800000000100018` | Begin data readout session |
| End transmission | `080f000000000007` | Close session |
| Read EEPROM | `080100[addr:2][size]` | Read device memory |
| Write EEPROM | `[len]01c0[addr:2][size][data]` | Write device memory |

## Pairing Protocol

1. Enable notifications on unlock UUID (`b305b680-aee7-11e1-a730-0002a5d5c51b`)
2. Send `0x02` + 16 zero bytes → device responds with `0x8200` if in pairing mode
3. Send `0x00` + 16-byte key → device responds with `0x8000` on success
4. Complete with start/end transmission handshake

Default pairing key: `deadbeaf12341234deadbeaf12341234`

## HEM-7361T Memory Layout

| Address | Content |
|---------|---------|
| `0x0010` | Settings read base |
| `0x0054` | Settings write base |
| `0x0098` | User 1 records start (100 records × 16 bytes) |
| `0x06D8` | User 2 records start (100 records × 16 bytes) |

## Record Format (16 bytes, little-endian)

| Bits | Field |
|------|-------|
| 68-73 | Minute |
| 74-79 | Second (clamped to 59) |
| 80 | Body movement flag (MOV) |
| 81 | Irregular heartbeat flag (IHB) |
| 82-85 | Month |
| 86-90 | Day |
| 91-95 | Hour |
| 98-103 | Year (offset from 2000) |
| 104-111 | Pulse (bpm) |
| 112-119 | Diastolic (mmHg) |
| 120-127 | Systolic + 25 (mmHg) |

## Connection Strategies

- **Bonded device** (known MAC): Direct connection first, fallback to scan
- **New device** (no MAC): Scan for OMRON devices, use first found
- **Pairing mode**: 10s stabilization wait, OS-level pair attempt, then OMRON key write

## Error Recovery

- **ATT error 0x0e**: Device timeout — press BT button again
- **CRC failure**: Logged as warning, packet discarded (no crash)
- **Unlock timeout**: 10s max, raises TimeoutError
- **Retry logic**: `_send_and_wait` retries up to 5 times per command
