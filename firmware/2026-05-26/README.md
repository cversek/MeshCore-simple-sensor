# Firmware build — 2026-05-26 (v3 pair)

v3 of the sensor/receiver pair. Forked from v2 (see `firmware/2026-05-24/`)
to add OLED feedback on button-triggered sends — the sensor's status page
now reports whether the receiver actually ACK'd the long-press send.

## Files

| File | Board | Role |
|------|-------|------|
| `Rook_companion_sensor_v3.uf2` | Rook v4 (nRF52840 + SX1262) | Sensor |
| `Rook_companion_sensor_v3.zip` | Rook v4 | DFU package (PIO upload) |
| `heltec_v4_companion_sensor_receiver_v3.bin` | Heltec WiFi LoRa 32 V4 | Receiver |

---

## What's new in v3 (vs v2)

**Sensor only.** Receiver is functionally identical to v2 — only the
version label is bumped so the pair reads as v3 when you type `ver`.

1. **OLED status page now shows last-ACK status.** Bottom line of the
   status page is one of:
   - `Last: sending...` — packet went out, waiting on ACK
   - `Last: ACK 3s ago` — receiver ACK'd; the line updates live, scaling
     `s` → `m` → `h` → `d` as time passes (round-trip ms is still printed
     to serial for debugging)
   - `Last: no ACK` — timeout (cached path was invalidated, next send floods)
   - `Every 300s` — fallback shown only at boot, before any send has happened

2. **Long-press on the Send page switches back to status.** Press-and-hold
   the button on the "Send Sensor" page: an overlay alert briefly confirms
   `Sent` (or `Sent N/N` for multi-target), then the page flips to the
   status view so you can watch the bottom line transition through
   sending → ACK Xs ago / no ACK.

3. **"Target not set" alert.** If you long-press send without having run
   `target add <name>`, an alert pops up so you know why nothing happened.

4. **Periodic auto-sends update the same status line.** If you happen to be
   looking at the status page when the 5-min timer fires, you'll see the
   send/ACK cycle too.

The v2 timeout-invalidates-path behavior is preserved. The late-ACK race
guard from v2 (early-return in `onSendTimeout` when `expected_ack_crc == 0`)
is also preserved.

---

## Source

| | Sensor | Receiver |
|---|---|---|
| PlatformIO env | `Rook_companion_sensor_v3` | `heltec_v4_companion_sensor_receiver_v3` |
| Source dir | `examples/v3/companion_sensor/` | `examples/v3/companion_sensor_receiver/` |
| Variant config | `variants/rook/platformio.ini` | `variants/heltec_v4/platformio.ini` |
| Flash usage | 378 KB / 815 KB (46.4%) | 1.21 MB / 6.55 MB (18.4%) |
| RAM usage | 28 KB / 235 KB (11.8%) | 91 KB / 2 MB (4.3%) |

`examples/v3/` is a clean fork of `examples/v2/` made on this date. The v2
sources are untouched — you can still build either pair from this repo.

### Shared radio settings (must match across the pair)

```
-D LORA_FREQ=910.525
-D LORA_BW=62.5
-D LORA_SF=7
-D LORA_CR=5
```

### Sensor-only build flags (Rook v4)

```
-D MAX_CONTACTS=32
-D ONEWIRE_PIN=9                  # DS18B20 on P1.06 (Arduino pin 9)
-D ADVERT_NAME='"Sensor"'
-D SENSOR_SEND_INTERVAL_SECS=300  # 5 min default
-D DISPLAY_CLASS=SSD1306Display
```

User button is on P1.00 (Arduino pin 6); set in the `[Rook]` base env as
`PIN_USER_BTN=6`. No per-env override needed.

### Receiver-only build flags (Heltec V4)

```
-D MAX_CONTACTS=128
-D ADVERT_NAME='"Receiver"'
-D DISPLAY_CLASS=SSD1306Display
```

---

## How to flash

### Sensor (Rook v4)

```bash
pio run -e Rook_companion_sensor_v3 -t upload
# Or drop the UF2 manually: double-tap reset to enter bootloader, then:
cp firmware/2026-05-26/Rook_companion_sensor_v3.uf2 /media/$USER/*/
```

If PlatformIO upload fails with "Attempting to use a port that is not open"
or similar, the device isn't in DFU mode. Double-tap RESET to force the
nRF52 bootloader (`/dev/ttyACM0` should re-appear; LED double-blinks).

### Receiver (Heltec V4)

```bash
pio run -e heltec_v4_companion_sensor_receiver_v3 -t upload
```

If the upload fails with `OSError: [Errno 71] Protocol error` (ESP32-S3
native-USB reset quirk on Linux), manually enter download mode: hold the
**BOOT** button, tap **RESET**, release BOOT — then retry.

The InternalFS partition (LittleFS) is preserved across application
reflash, so identity, contacts, targets, WiFi creds, and Bayou keys all
survive — you do NOT need to re-import the receiver's biz card or re-add
targets after going from v2 → v3.

---

## Setting parameters after flashing

### Connecting via serial

Both nodes expose a text CLI on USB serial at **115200 baud**. Use:

```bash
pio device monitor -b 115200
```

`pio device monitor` is recommended over `screen` / `picocom` for two
reasons:

1. **Auto-reconnect on reset.** The Heltec V4 (ESP32-S3) uses native USB
   CDC — tapping RESET tears down `/dev/ttyACM0` and re-creates it. `screen`
   and `picocom` hold the tty exclusively and exit when the file
   disappears; `pio device monitor` (and `tio`) reconnect through the
   re-enumeration cleanly. The Rook bootloader does the same thing on
   double-tap-reset.
2. **Auto-release for reflash.** When you next run `pio run -t upload`,
   the monitor releases the port automatically. With `screen` open on
   the port, the upload would fail with a busy-port error.

If `pio device monitor` complains about an `UnknownPlatform` (the
`maxgerhardt/platform-raspberrypi` referenced by the `rpi_picow` env),
install it once:

```bash
pio pkg install -g --platform "https://github.com/maxgerhardt/platform-raspberrypi.git"
```

`tio /dev/ttyACM0` is a fine alternative that bypasses the PIO config
entirely and also auto-reconnects.

### First boot

On the very first boot of either node, the firmware prints:

```
Press ENTER to generate key:
```

…and blocks until you press ENTER. The OLED freezes at "Starting…" in
the meantime — that's not a crash, just the key-prompt block. The
generated identity persists across reflash (it lives on the InternalFS
partition, which is separate from the application code).

### Sensor setup (Rook v4)

```
set name FarmSensor                   # mesh advert name
set node_id 1                         # 1–65535; distinguishes multiple sensors on one Bayou feed
import meshcore://<receiver-card>     # paste the receiver's `card` output
target add FarmReceiver               # or target add HomeReceiver / MobileReceiver (max 4)
set interval 300                      # auto-send interval in seconds (min 10, default 300)
send                                  # fire a reading immediately
```

### Receiver setup (Heltec V4)

```
set name FarmReceiver
import meshcore://<sensor-card>       # paste the sensor's `card` output
set wifi_ssid YourNetwork
set wifi_password YourPassword
set bayou_public_key <feed-public-key>
set bayou_private_key <feed-private-key>
status                                # check WiFi: connected / Bayou: ok / Last: …
```

WiFi settings need a **reboot** to take effect (reset button or
unplug/replug). Bayou keys take effect immediately. Get the Bayou keys
from <https://bayou.pvos.org> when you create a feed.

### CLI command reference

| Command | Where | What it does |
|---------|-------|--------------|
| `help` | both | List available commands |
| `ver` | both | Print firmware version string (use this to confirm v3 vs v2) |
| `card` | both | Print this node's biz card (`meshcore://…`) — share with the other node |
| `import meshcore://…` | both | Add another node's biz card to contacts (auto-favourited on receiver) |
| `list` | both | List known contacts. `*` marks a favourite (never auto-evicted) |
| `purge` | both | Clear all stored contacts (`identity` and `targets` survive) |
| `advert` | both | Broadcast a mesh advertisement (also: long-press the "Send Advert" page) |
| `set name <name>` | both | Set this node's advertised mesh name |
| `set node_id <n>` | sensor | Set numeric sensor id (1–65535) included in `[SENSOR]` payload |
| `set interval <secs>` | sensor | Set auto-send interval (min 10, default 300) |
| `target` | sensor | List currently configured send targets |
| `target add <name>` | sensor | Add a contact (by name prefix) to the send-target list (max 4) |
| `target remove <name>` | sensor | Remove a target |
| `target clear` | sensor | Clear all targets |
| `send` | sensor | Send a sensor reading immediately (also: long-press "Send Sensor" page) |
| `set wifi_ssid <ssid>` | receiver | WiFi SSID (reboot to apply) |
| `set wifi_password <pwd>` | receiver | WiFi password (reboot to apply) |
| `set bayou_public_key <k>` | receiver | Bayou feed public key (takes effect immediately) |
| `set bayou_private_key <k>` | receiver | Bayou feed private key (takes effect immediately) |
| `settings` / `show_settings` | receiver | Print current settings (password and private key masked) |
| `status` | receiver | One-line WiFi/Bayou state + last message received |
| `favourite <name>` | receiver | Mark a contact as favourite (immune from auto-eviction). `import` auto-favourites. |
| `unfavourite <name>` | receiver | Clear favourite flag |

### Contact exchange has to be two-way

Both nodes need each other's public key to encrypt/decrypt DMs. On each
node, run `card`, copy the `meshcore://…` line, and `import` it on the
other node. (Over-the-air advert discovery also works if both are in
range with matching radio settings, but manual exchange is more reliable
on initial setup.)

### Try the new OLED feedback

1. On the sensor's OLED, short-press the button to wake the display.
2. Short-press to cycle to PAGE_SEND (`Send Sensor / long press`).
3. Long-press the button.
4. The screen flips to PAGE_STATUS, overlay says `Sent` briefly, then the
   bottom line cycles: `Last: sending...` → `Last: ACK 1s ago` (success;
   counter ticks up live in seconds → minutes → hours → days) or
   `Last: no ACK` (timeout).
5. If no target is set, you'll see `Target not set` instead.

### Verifying end-to-end

Same as v2 — see `firmware/2026-05-24/README.md` for the full Bayou-side
verification walkthrough. Bayou record's `log` field should still look
like `path=5a.91 route=DIRECT` for a DIRECT send.

---

## Reverting to v2

If v3 misbehaves, the v2 binaries and source are untouched:

```bash
pio run -e Rook_companion_sensor_v2 -t upload
pio run -e heltec_v4_companion_sensor_receiver_v2 -t upload
# Or use the snapshots in firmware/2026-05-24/
```
