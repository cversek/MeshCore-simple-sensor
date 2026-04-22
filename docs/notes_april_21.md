# Development Notes — 2026-04-21

Status snapshot of the `companion_sensor` / `companion_sensor_receiver` work and the next planned changes.

## Current Status

### Firmware in the field
- **Sensor** (Rook / Heltec V3): `companion_sensor` v1, last flashed build has node_id support, multi-target (up to 4), auto-evict + purge, Rook TX power 22 dBm.
- **Receiver** (Heltec V3): `companion_sensor_receiver` v1, last flashed build has:
  - `aux_1` hop count field in Bayou JSON (partially working — see "Known Issues")
  - `show_settings` / `settings` command
  - `favourite <name>` / `unfavourite <name>` commands
  - Auto-favourite on `import` (pub_key matched in loopback)
  - `list` shows `*` marker for favourites
  - `purge` command
  - `MAX_CONTACTS=128`, auto-evict oldest non-favourite when full
  - Serial output field renamed `hops=` → `radio_hops=`

### Nodes flashed this session
- New Heltec on `/dev/ttyUSB0` — receiver firmware (latest)
- Another Heltec on `/dev/ttyUSB0` earlier — `Heltec_v3_companion_radio_ble` (standard companion radio BLE build, not sensor/receiver)

### Data flow (confirmed working)
```
DS18B20 → sensor: [SENSOR] node_id=N temp=T.TTC batt=B.BBV
                → LoRa (up to 4 targets)
                → receiver: parse → JSON POST to Bayou
                                    {node_id, temperature_c, battery_volts,
                                     aux_1 (hops), source}
```

## Known Issues

### `aux_1` / `radio_hops` always reads 0 for DIRECT arrivals
**Root cause** (understood, not yet fixed):

- For FLOOD packets: each repeater appends its hash in `Mesh::routeRecvPacket`, so at the destination `pkt->getPathHashCount()` = actual hop count. Works correctly.
- For DIRECT packets: each repeater strips its hash via `removeSelfFromPath` (Mesh.cpp:98) before forwarding. At the destination the path is empty — `getPathHashCount()` returns 0.

**My first attempted fix** (fall back to `from.out_path_len` on DIRECT): doesn't work. The receiver never learns the reverse path back to the sender — only the sender gets a PATH-return after the initial FLOOD, so `from.out_path_len` on the receiver side stays `OUT_PATH_UNKNOWN`.

**Conclusion**: the receiver cannot recover hop count for DIRECT packets from the packet alone. Only the **sender** knows (via `recipient.out_path_len` at send time, which may be slightly stale but is the best available estimate).

### Sensor went silent / got evicted
Debugged earlier: WFS14 contact import showed "ADVERT from -> WFS14" confirmation but didn't appear in `list` because the list was full and `onAdvertRecv` calls `onDiscoveredContact` even when `allocateContactSlot()` returns NULL. Fix shipped: `shouldOverwriteWhenFull() = true`, `MAX_CONTACTS=128`, auto-favourite on import.

### Firmware flash upload fails when `screen` is connected
Recurring workflow friction: `screen /dev/ttyUSB0 115200` holds the port and PIO can't flash. Solution: use `pio device monitor -b 115200` instead (auto-releases on upload), or quit screen with `Ctrl-A k` before flashing.

## Shipped: `companion_sensor_receiver_route` (route-diagnosis variant)

### What it is
A drop-in variant of `companion_sensor_receiver` for diagnosing how sensor messages are actually arriving at the receiver. Built and flashed this session.

### What it adds on top of the base receiver
- `aux_2` field in the Bayou JSON: `0` = packet arrived via FLOOD, `1` = packet arrived via DIRECT (stored-path).
- `log` field in the Bayou JSON: for FLOOD arrivals, hex-encoded bytes of `pkt->path[]` (the accumulated repeater hash trail). Empty for DIRECT (path is stripped in transit and unrecoverable from the packet alone on the receiver side).
- Serial output on `[SENSOR DATA]` and `status` now includes `path=<hex>` for FLOOD arrivals.
- `ADVERT_NAME="RouteReceiver"` so it doesn't collide with the base receiver in contact lists if running both simultaneously.

### Example Bayou JSON
```
{
  "private_key": "...",
  "node_id": 1,
  "temperature_c": 22.50,
  "battery_volts": 3.85,
  "aux_1": 2,         // hop count (accurate for FLOOD, 0 for DIRECT)
  "aux_2": 0,         // 0 = FLOOD, 1 = DIRECT
  "log": "a37f02",    // repeater hash trail (FLOOD only)
  "source": "FarmSensor"
}
```

### Purpose
Answer the question "how is my remote sensor actually reaching me?" — once the sender has handshook, it mostly sends DIRECT (with stale path risk). The `aux_2` field lets the Bayou consumer see the FLOOD/DIRECT ratio over time; the `log` field lets external analysis correlate FLOOD path bytes with repeater identities (1-byte hash prefixes of pub_keys).

### Files
- `examples/companion_sensor_receiver_route/main.cpp`
- `[env:Heltec_v3_companion_sensor_receiver_route]` in `variants/heltec_v3/platformio.ini`
- `bin/Heltec_v3_companion_sensor_receiver_route.bin`

### Not yet implemented
Sender-embedded path for DIRECT arrivals — see next section.

## Future Plan: Sender-Embedded Path

### Rationale
The receiver cannot recover hop count or repeater identities for DIRECT packets from the packet alone — repeaters strip their hash in transit. The sender, however, has `recipient.out_path[]` (bytes = 1-byte hashes of the repeaters along the forward path). Embed those bytes directly in the `[SENSOR]` message payload. Benefits:

- **Hop count**: derived from path length (1 byte per hop, since `PATH_HASH_SIZE=1`).
- **Repeater identity correlation**: each path byte is a 1-byte prefix of a pub_key. The receiver (or Bayou consumer) can match each byte against known repeater contacts to identify the route.

### Message format

**When path is known (DIRECT sends):**
```
[SENSOR] node_id=1 temp=22.5C batt=3.8V path=a37f02
```

**When path unknown (first FLOOD send, before handshake):**
```
[SENSOR] node_id=1 temp=22.5C batt=3.8V
```
Receiver falls back to `pkt->getPathHashCount()` / `pkt->path[]` (both accurate for FLOOD arrivals).

### Sensor changes
- Move message `snprintf` inside the per-recipient loop (path is recipient-specific).
- Hex-encode `recipient->out_path[0..out_path_len-1]` and append as `path=...` when `out_path_len != OUT_PATH_UNKNOWN`.

### Receiver changes
- Parse `path=HEX` from incoming messages.
- If present: hop count = `strlen(hex)/2`; path bytes = decoded hex.
- If absent: fall back to `pkt->path[]` + `pkt->getPathHashCount()` (FLOOD arrivals).
- Resolve each path byte against local contacts via `contact.id.isHashMatch(byte)`. First match = candidate name (note 1/256 collision rate).
- Print to serial: `path=a37f02 (Repeater1?, ?, NodeX)`.
- Include raw hex in Bayou JSON as `path_hex` field, alongside existing `aux_1` hop count.

### Caveats
- `out_path` can be stale (not auto-refreshed in this fork). If the message arrives, the path is still valid — so the embedded path reflects actual routing. If topology has shifted, reported path may lag reality.
- Best-effort repeater matching: 1-byte hash collides ~1/256, so with many repeater contacts multiple candidates may exist. Report first match only.
- Max message length: 160 bytes. Path hex could in principle consume up to 128 chars (64 bytes × 2), but typical 1–5 hops = 2–10 chars, well within budget.

## Superseded: Earlier hop-count plan

### Problem
Receiver needs to log hop count to Bayou as `aux_1`, but DIRECT packets arrive with `path_len=0` (path stripped in transit).

### Proposed fix
Have the sensor include its best estimate of the hop count in the message payload itself:

```
[SENSOR] node_id=1 temp=22.5C batt=3.8V hops=3
```

- At send time, sensor reads `recipient->out_path_len` (bytes == hops since `PATH_HASH_SIZE=1`).
- If `out_path_len == OUT_PATH_UNKNOWN` (first send, FLOOD), include `hops=0` — receiver falls back to `pkt->getPathHashCount()` which works for FLOOD arrivals.
- Receiver: add `hops=` to the parser; use embedded value when present, otherwise fall back to `getPathHashCount()`.

### Caveats
- `out_path_len` can be stale (not auto-refreshed; this fork doesn't invalidate on timeout). But: if the message arrives, the path is still valid, so the reported count should match reality.
- When `out_path_len` is slightly stale after a topology change, the count could be off by 1–2 hops. Acceptable for mesh-health monitoring.

### Requires re-flashing
- Sensor (Rook + Heltec V3 sensor builds): add `hops=` to the `[SENSOR]` message format in `sendSensorReading()`.
- Receiver: parser change + fallback logic in `onMessageRecv`.

### Not started yet
Waiting for user go-ahead.

## Open Questions / Future Ideas

- **Repeater identity in the path**: for FLOOD arrivals, the path contains a 1-byte hash of each repeater's pub_key. Could be resolved (best-effort) against the receiver's contacts list. 1/256 collision rate — not unique with 128 contacts but could show candidate names.
- **Periodic path refresh**: sender could occasionally force a FLOOD send to re-learn the path. Currently relies on initial handshake only.
- **Favourite flag backup**: currently lives in `flags` byte, persisted via `saveContacts`. Fine, just noting.

## File Pointers

- Sensor main: `examples/companion_sensor/main.cpp`
- Base receiver main: `examples/companion_sensor_receiver/main.cpp`
- Route-diagnosis receiver: `examples/companion_sensor_receiver_route/main.cpp`
- Firmware binaries: `bin/Rook_companion_sensor.uf2`, `bin/Heltec_v3_companion_sensor_receiver.bin`, `bin/Heltec_v3_companion_sensor_receiver_route.bin`
- Setup guide: `docs/sensor_setup.md`
- Detailed firmware notes: `docs/sensor_firmware_notes.md`
- PlatformIO envs: `variants/heltec_v3/platformio.ini`, `variants/rook/platformio.ini`
