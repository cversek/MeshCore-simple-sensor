# Firmware build — 2026-05-24

Two pieces of MeshCore v2 firmware built this day. Together they form the **sensor → receiver → Bayou** pipeline: the Rook sends `[SENSOR]` direct messages over LoRa, the Heltec V4 receives them and POSTs each reading to bayou.pvos.org.

## Files

| File | Board | Role |
|------|-------|------|
| `Rook_companion_sensor_v2.uf2` | Rook (nRF52840 + SX1262) | Sensor — reads DS18B20, DMs to receiver |
| `Rook_companion_sensor_v2.zip` | Rook | DFU package (same firmware, for `adafruit-nrfutil` / PlatformIO upload) |
| `heltec_v4_companion_sensor_receiver_v2.bin` | Heltec WiFi LoRa 32 V4 (ESP32-S3) | Receiver — parses incoming sensor DMs, posts JSON to Bayou |

---

## What v2 is

The **v2** sensor/receiver pair from `examples/v2/` (vs the v1 pair in `examples/companion_sensor/` + `examples/companion_sensor_receiver/`). Pair design notes are in `examples/v2/README.md`.

Key v2 additions vs v1:
- Sender embeds its cached path into the payload: `[SENSOR] node_id=N temp=T batt=B fwd_hops=F fwd_path=aa.bb.cc`.
- Sender invalidates its cached `out_path` on send timeout, so the next send floods and re-discovers a path.
- Receiver parses `fwd_hops` / `fwd_path` and posts them to Bayou as `aux_2` (numeric hops the sender claimed) and `log = "path=… route=DIRECT|FLOOD"`.
- Receiver does duplicate-message detection: if a DIRECT message arrives whose `(sender, timestamp)` matches a recent one, it infers its own previous ACK didn't land and floods the next ACK to rebuild the reverse path.

### Local patch in this build (sensor only)

`onSendTimeout` now early-returns when `expected_ack_crc == 0`. Without this guard, a successful-but-slow FLOOD round-trip (e.g. 3000ms+ over SF7/BW62.5) could fire the timeout just as the ACK arrived, causing the sender to invalidate the path it had just learned from the receiver's PATH-return. Symptom in serial log: `Got ACK!` immediately followed by `ERROR: timed out, no ACK. Invalidating cached path…`. Patched in `examples/v2/companion_sensor/main.cpp` `onSendTimeout()`.

Firmware version strings (from `main.cpp`):
- Sensor: `companion_sensor v2 (build: Apr 2026) [hop logging + timeout-invalidates-path]`
- Receiver: `companion_sensor_receiver v2 (build: Apr 2026) [fwd_hops + dup-detect flood-ACK]`

---

## Build provenance

| | Sensor (Rook) | Receiver (Heltec V4) |
|---|---|---|
| PlatformIO env | `Rook_companion_sensor_v2` | `heltec_v4_companion_sensor_receiver_v2` |
| Source dir | `examples/v2/companion_sensor` | `examples/v2/companion_sensor_receiver` |
| Variant config | `variants/rook/platformio.ini` | `variants/heltec_v4/platformio.ini` |
| Git commit (working tree base) | `e4390655` | `e4390655` |
| Flash usage | 377 KB / 815 KB (46.3%) | 1.20 MB / 6.55 MB (18.4%) |
| RAM usage | 28 KB / 235 KB (12.1%) | 89 KB / 2 MB (4.3%) |

Both envs were added in the working copy on this date and may not be committed yet — `git diff variants/` shows the source of truth.

### Shared radio settings (must match across the pair)

```
-D LORA_FREQ=910.525
-D LORA_BW=62.5
-D LORA_SF=7
-D LORA_CR=5
```

### Sensor-only build flags (Rook)

```
-D MAX_CONTACTS=32
-D ONEWIRE_PIN=9                  # DS18B20 data on P1.06 (Arduino pin 9)
-D ADVERT_NAME='"Sensor"'
-D SENSOR_SEND_INTERVAL_SECS=300  # 5 min default
-D DISPLAY_CLASS=SSD1306Display
```

The user button on the Rook v4 is on **P1.00 (Arduino pin 6)** — set by `PIN_USER_BTN=6`
in the base `[Rook]` env (`variants/rook/platformio.ini`). Both `variant.h:77`
(`PIN_BUTTON1 = 6`) and the platformio default were updated this session to match
Rook v4 hardware (earlier defaults targeted P0.06, which was a previous-revision
button location).

### Receiver-only build flags (Heltec V4)

```
-D MAX_CONTACTS=128
-D ADVERT_NAME='"Receiver"'
-D DISPLAY_CLASS=SSD1306Display
```

---

## How to flash

From the repo root:

### Sensor (Rook)

```bash
# Rebuild
pio run -e Rook_companion_sensor_v2

# Flash via PlatformIO (uses adafruit-nrfutil)
pio run -e Rook_companion_sensor_v2 -t upload

# Or copy the saved UF2 — double-tap reset to enter bootloader, then:
cp firmware/2026-05-24/Rook_companion_sensor_v2.uf2 /media/$USER/*/
```

### Receiver (Heltec V4)

```bash
# Rebuild
pio run -e heltec_v4_companion_sensor_receiver_v2

# Flash via PlatformIO
pio run -e heltec_v4_companion_sensor_receiver_v2 -t upload
```

If the upload fails with `OSError: [Errno 71] Protocol error` (an ESP32-S3 native-USB reset glitch on Linux), manually enter download mode: hold the **BOOT** button, tap **RESET**, release BOOT — then retry the upload command.

---

## Setting parameters after flashing

Both nodes use a text serial CLI at **115200 baud**. Open with:

```bash
pio device monitor -b 115200
```

(Use `pio device monitor` rather than `screen` — it auto-releases the port when you reflash.)

On first boot of either node, press **ENTER** to generate the cryptographic identity.

### Sensor (Rook) — required setup

```
set name FarmSensor                 # advertised mesh name
set node_id 1                       # 1-65535; distinguishes multiple sensors on one Bayou feed
import meshcore://<receiver-card>   # paste the receiver's biz card; get it with `card` on the receiver
target FarmReceiver                 # or: target add HomeReceiver / target add MobileReceiver (max 4)
set interval 300                    # send interval in seconds (min 10, default 300)
```

Then `send` to fire a reading immediately. `target` shows the current target list; `list` shows known contacts.

### Receiver (Heltec V4) — required setup

```
set name FarmReceiver
import meshcore://<sensor-card>     # paste the sensor's biz card
set wifi_ssid YourNetwork
set wifi_password YourPassword
set bayou_public_key <feed-public-key>
set bayou_private_key <feed-private-key>
```

WiFi settings need a **reboot** to take effect (reset button or unplug/replug). Bayou keys take effect immediately. Get the Bayou keys from <https://bayou.pvos.org> when you create a feed.

Verify with `status`:
```
   WiFi: connected
   Bayou: ok
   Last: [SENSOR] node_id=1 temp=22.50C batt=3.85V fwd_hops=2 fwd_path=5a.91
```

### Other commands worth knowing

| Command | Where | What it does |
|---------|-------|--------------|
| `card` | both | Print this node's biz card (`meshcore://…`) for exchange |
| `list` | both | List known contacts. `*` = favourite (never auto-evicted) |
| `purge` | both | Clear all stored contacts |
| `favourite <name>` | receiver | Mark a contact as favourite (immune to eviction). Auto-set on `import`. |
| `unfavourite <name>` | receiver | Clear favourite flag |
| `advert` | both | Broadcast a mesh advertisement (also long-press the "Send Advert" display page) |
| `target` / `target add` / `target remove` / `target clear` | sensor | Manage send-target list (max 4) |
| `send` | sensor | Send a reading right now (also long-press the "Send Sensor" page) |
| `settings` / `show_settings` | receiver | Print current settings (password/key fields masked) |
| `ver` | both | Firmware version string |
| `help` | both | List commands |

### Contact exchange must be two-way

Both nodes need each other's pub_key to encrypt/decrypt DMs. On each node, run `card`, copy the `meshcore://…` output, and `import` it on the other node. (Over-the-air advert discovery also works if both are in range with matching radio settings, but manual exchange is more reliable.)

The receiver's MAX_CONTACTS is 128 and the auto-evict-oldest-non-favourite policy is enabled — importing a contact also auto-favourites it so it can't be evicted later.

---

## Verifying the pipeline end-to-end

1. On the sensor: `send` — expect serial output like:
   ```
   [SENSOR] node_id=1 temp=22.50C batt=3.85V fwd_hops=2 fwd_path=5a.91
   -> FarmReceiver: (direct, len=2, hashes=5a.91) sent (DIRECT)
   Got ACK! (round trip: 1234 millis)
   ```
2. On the receiver: expect a `[SENSOR DATA]` line then a `Posting to Bayou:` + `Bayou post OK (200)` line.
3. In Bayou: the new record's `log` field should look like `path=5a.91 route=DIRECT`.

See `docs/sensor_setup.md` for the original (v1) walkthrough — v2 behaves the same operationally, just adds the path/route fields described above.
