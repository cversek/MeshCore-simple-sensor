# v3-1-wire — v3-style sensor + DS18B20 → temperature_c → Bayou

Fork of `examples/v3-ultrasonic/` that swaps the MaxBotix ultrasonic
probe for a **DS18B20 OneWire temperature probe** and posts
`temperature_c` to Bayou.

Functionally equivalent to `examples/v3/` on the sensor side (same field
name and Bayou JSON shape), but with the **v3-ultrasonic UX
improvements** carried over:

- Verbose boot prints in `setup()` so each step is visible on the serial
  monitor (handy for first-boot diagnosis: shows where it blocks on
  `Press ENTER to generate key:` after a UF2 flash that wipes
  InternalFS).
- The **Send page does a live sensor read on page-entry** — short-press
  to land on the Send page and you immediately see a fresh
  `Temp: 22.5C / Batt: 3.85V` preview before deciding whether to
  long-press send.
- Carries v3's OLED last-ACK feedback (status page bottom line shows
  `Last: sending…` → `Last: ACK Xs ago` → `Last: no ACK`).

| | v3 | v3-1-wire |
|---|---|---|
| Sensor probe | DS18B20 (OneWire) | DS18B20 (OneWire) |
| Payload field | `temp=22.50C` | `temp=22.50C` |
| Bayou JSON key | `temperature_c` | `temperature_c` |
| OLED status line | `Temp: 22.5C` | `Temp: 22.5C` |
| OLED ACK feedback | yes | yes |
| Boot prints | minimal | verbose (every step) |
| Send-page live read | no | yes (refreshes on page-arrival) |

---

## Wiring (Rook v4)

DS18B20 OneWire probe on **Arduino D9 = P1.06 = Rook v4 schematic
pin 12**. Pull-up resistor required between data line and 3V3.

| DS18B20 | Rook (schematic) | nRF52 | Arduino |
|---|---|---|---|
| data (yellow) | pin **12** | P1.06 | D9 (`ONEWIRE_PIN`) |
| V+ (red) | pin **21** — `3V3` | — | — |
| GND (black) | any GND (3, 4, 23, 26) | — | — |
| pull-up | 4.7 kΩ between data and 3V3 | — | — |

See `notes/rook_v4_pinmap.md` for the full Rook v4 pin map.

The default `ONEWIRE_PIN=9` is set in the PlatformIO env and matches the
existing v2/v3 sensor envs. If your DS18B20 is wired elsewhere, override
the macro in your env's `build_flags`.

---

## Build

```bash
pio run -e Rook_companion_sensor_v3_1_wire              # sensor (Rook v4)
pio run -e Heltec_v3_companion_sensor_receiver_v3_1_wire # receiver (Heltec V3)
# or:
pio run -e heltec_v4_companion_sensor_receiver_v3_1_wire # receiver (Heltec V4)
```

Flash:

```bash
pio run -e Rook_companion_sensor_v3_1_wire -t upload
pio run -e Heltec_v3_companion_sensor_receiver_v3_1_wire -t upload
```

### PlatformIO env definitions

- Rook sensor env: `[env:Rook_companion_sensor_v3_1_wire]` in
  `variants/rook/platformio.ini`
- Heltec V3 receiver env:
  `[env:Heltec_v3_companion_sensor_receiver_v3_1_wire]` in
  `variants/heltec_v3/platformio.ini`
- Heltec V4 receiver env:
  `[env:heltec_v4_companion_sensor_receiver_v3_1_wire]` in
  `variants/heltec_v4/platformio.ini`

---

## Setup (after flashing)

Both nodes share the same radio settings and CLI as v2/v3/v3-ultrasonic.

### Bayou setup

This fork posts `temperature_c` to Bayou — same field name as v3, so an
**existing v3 Bayou feed can be reused**. If you don't already have one,
create a feed with `temperature_c` as a measured field and set the
receiver's `bayou_public_key` / `bayou_private_key` to that feed.

The full Bayou JSON body looks like:

```json
{
  "private_key": "...",
  "node_id": 1,
  "temperature_c": 22.50,
  "battery_volts": 3.870,
  "aux_1": 0,
  "aux_2": 0,
  "log": "path=none route=DIRECT",
  "source": "Sensor"
}
```

`battery_volts` is still posted alongside so you can monitor unattended
node battery health.

### CLI sanity check after flashing the sensor

On the Rook serial console:

```
ver               # should print "companion_sensor v3-1-wire ..."
send              # forces a reading + send; serial trace should show
                  # "[SENSOR] node_id=N temp=X.XXC batt=Y.YYV ..."
```

If the boot log says `No DS18B20 on OneWire bus`, check:

1. Pull-up resistor (4.7 kΩ data ↔ 3V3) is present and connected.
2. Wiring matches Arduino D9 / P1.06 (schematic pin 12).
3. Probe V+ and GND aren't swapped.

The on-page live preview (short-press to Send page) is the easiest way
to verify the sensor: it forces a fresh read and prints `Temp: …` on the
OLED without sending anything over the radio.

---

## Reverting

`examples/v3/` and `examples/v3-ultrasonic/` are untouched — flash one
of those envs to revert:

```bash
pio run -e Rook_companion_sensor_v3 -t upload
pio run -e Rook_companion_sensor_v3_ultrasonic -t upload
```
