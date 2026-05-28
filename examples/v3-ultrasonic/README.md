# v3-ultrasonic — v3 sensor + MaxBotix MB7388 → distance_meters → Bayou

Fork of `examples/v3/` that swaps the DS18B20 temperature probe for a
**MaxBotix MB7388 (HRXL-MaxSonar-WRMT)** ultrasonic rangefinder.
Designed for dockside water-level monitoring: aim the sensor down at the
water surface and log `distance_meters` to Bayou.

Functionally identical to v3 on the LoRa side (hop logging,
timeout-invalidates-path, ACK + path discovery) **and** carries v3's
OLED last-ACK feedback (status page shows `Last: sending…` → `Last: ACK
Xs ago` → `Last: no ACK` after a button-triggered send, plus the page
flip to status + `Sent` alert and `Target not set` alert). The only
changes vs v3 are the sensor read path on the Rook and the JSON field
name on the receiver:

| | v3 | v3-ultrasonic |
|---|---|---|
| Sensor probe | DS18B20 (OneWire) | MB7388 (Serial1, 9600 baud) |
| Payload field | `temp=22.50C` | `dist=1.234m` |
| Bayou JSON key | `temperature_c` | `distance_meters` |
| OLED status line | `Temp: 22.5C` | `Dist: 1.23m` |
| OLED ACK feedback | yes | yes (carried over from v3) |

---

## Hardware: MaxBotix MB7388

The MB7388 is the IP67 weather-resistant member of the HRXL-MaxSonar-WRMT
family. Quick spec:

| | |
|---|---|
| Range | 300 mm – 5000 mm |
| Resolution | 1 mm |
| Beam | narrow (~3°) |
| Output rate | ~6 Hz (~168 ms/frame) in free-run mode |
| TTL serial format | `Rdddd\r` at 9600 baud, 8N1 (`dddd` = mm) |
| Supply | 2.7–5.5 V, ~3.4 mA average |
| Mount | down-facing, 30+ cm above max water level |

The 7388 free-runs when its **pin 4** (RX/strobe) is left floating or pulled
high. Frame format example: `R0742\r` = 742 mm = 0.742 m.

### Pinout (looking at the connector end)

```
1  Temperature sensor  (leave NC for typical use)
2  PWM output          (NC for our build)
3  Analog output       (NC for our build)
4  RX / strobe         (NC = continuous mode)
5  TTL serial OUT      → Rook Serial1 RX pin
6  V+  (2.7–5.5 V)     → Rook 3V3 (or VBUS — see note)
7  GND                 → Rook GND
```

**Power note.** 3.3 V works fine but the manufacturer-suggested supply for
best long-range performance is 4.5–5.0 V. If the Rook is USB-powered you
can tap VBUS (5 V) instead of 3V3 — just check your particular Rook
revision exposes it on a header pin.

### Wiring to Rook v4

The MB7388's TTL serial output is 3.3 V logic, so it connects directly to
the Rook's UART RX pin (no level shifter needed). Only one wire is
needed for data — the Rook never sends to the MB7388 in this build.

| MaxBotix | Rook (schematic) | nRF52 | Arduino |
|---|---|---|---|
| pin 5 (TTL TX) | pin **2** — silkscreen `RX1` | P0.08 | D0 (`Serial1` RX) |
| pin 6 (V+) | pin **21** — `3V3` | — | — |
| pin 7 (GND) | any GND (3, 4, 23, 26) | — | — |
| pin 4 (RX/strobe) | leave NC | — | — |

See `notes/rook_v4_pinmap.md` for the full Rook v4 pin map (including
the D0/D1 swap vs canonical Nice Nano — the silkscreen labels `TX0`/`RX1`
do **not** correspond to Arduino digital pins 0/1).

For longer-range performance the manufacturer recommends 4.5–5.0 V on
pin 6 — tap the `BAT` pad (schematic pin 24/25 ≈ VBUS when USB-powered)
instead of `3V3`.

---

## Build

```bash
pio run -e Rook_companion_sensor_v3_ultrasonic           # sensor (Rook v4)
pio run -e heltec_v4_companion_sensor_receiver_v3_ultrasonic  # receiver (Heltec V4)
```

Flash:

```bash
pio run -e Rook_companion_sensor_v3_ultrasonic -t upload
pio run -e heltec_v4_companion_sensor_receiver_v3_ultrasonic -t upload
```

Approx. flash usage: Rook sensor ~376 KB / 815 KB (46%), Heltec receiver
~1.21 MB / 6.55 MB (18%).

### PlatformIO env definitions

- Rook sensor env: `[env:Rook_companion_sensor_v3_ultrasonic]` in
  `variants/rook/platformio.ini`
- Heltec receiver env: `[env:heltec_v4_companion_sensor_receiver_v3_ultrasonic]`
  in `variants/heltec_v4/platformio.ini`

The Rook env drops the DS18B20 libs (`OneWire`, `DallasTemperature`) and
the `ONEWIRE_PIN` define. Otherwise it mirrors the standard v2/v3 sensor
envs.

---

## Setup (after flashing)

Both nodes share the same radio settings and CLI as v2/v3. See
`firmware/2026-05-26/README.md` (the v3 build notes) for the full CLI
walkthrough — the command set is identical here, only the displayed
field changes.

### Bayou setup

This fork posts `distance_meters` (not `temperature_c`), so create a
**new Bayou feed** with `distance_meters` as one of its measured fields.
Set the receiver's `bayou_public_key` / `bayou_private_key` to that new
feed.

The full Bayou JSON body looks like:

```json
{
  "private_key": "...",
  "node_id": 1,
  "distance_meters": 1.234,
  "battery_volts": 3.870,
  "aux_1": 0,
  "aux_2": 0,
  "log": "path=none route=DIRECT",
  "source": "DockSensor"
}
```

`battery_volts` is still posted so you can monitor whether the unattended
dock node needs charging.

### CLI sanity check after flashing the sensor

On the Rook serial console:

```
ver               # should print "companion_sensor v3-ultrasonic ..."
send              # forces a reading + send; serial trace should show
                  # "[SENSOR] node_id=N dist=X.XXXm batt=Y.YYV ..."
```

If the boot log says `No MaxBotix frames on Serial1 (check wiring / 9600 baud)`,
the sensor's pin 5 isn't talking to the Rook's `Serial1` RX. Double-check
wiring and that pin 4 is left floating (not grounded).

---

## Water-level interpretation

The sensor measures distance to the water surface, not water level. To
convert:

```
water_level = (sensor_height_above_datum) - distance_meters
```

Pick a datum (e.g. MLLW, a fixed dock structure, or the sensor mount
height itself) and record it once per install. Bayou's downstream
plotting can subtract distance from that constant.

### Tide reference — Cranston, RI

For dockside testing in Cranston RI, NOAA's nearest tide station is
**Providence (8454000)**:

<https://tidesandcurrents.noaa.gov/noaatidepredictions.html?id=8454000&legacy=1>

Useful for cross-checking that the sensor's recorded tide curve tracks
NOAA predictions during a 24-hour soak test. Note that Providence
predictions are MLLW-referenced; subtract your sensor's mount height
above MLLW to compare against the predicted curve.

---

## Calibration

A few practical notes when first deploying:

1. **Sanity-test in air first.** Point the sensor at a known target
   (e.g. tape measure stretched on the ground, sensor mounted 1 m above)
   and confirm the OLED reads `Dist: 1.00m ±0.01m`. If it reads way off,
   check ground/V+/pin5 wiring.
2. **Settling.** First reading after wake takes 2–3 frames (~500 ms);
   the firmware already waits up to 400 ms on each `send` cycle for a
   fresh frame.
3. **Reflections / clutter.** The MB7388 picks the strongest return. On
   a dock, the dominant return should be the water surface as long as
   no piling / rope / boat hull is closer than the water. Mount the
   sensor over open water with at least 1 m clearance from any other
   structure.
4. **Min range.** The MB7388's dead zone is 0–300 mm. Mount the sensor
   high enough that even at the maximum tide / wave, distance stays
   above ~0.4 m.
5. **Rain / spray.** The 7388 is IP67-rated and tolerates a wet
   transducer, but heavy spray on the face during measurement causes
   occasional spurious short readings. Consider median-filtering N
   readings if this becomes a problem (currently the firmware uses the
   freshest single frame).

---

## Reverting

Both `examples/v2/` and `examples/v3/` are untouched — just flash one of
the original envs:

```bash
pio run -e Rook_companion_sensor_v2 -t upload
pio run -e Rook_companion_sensor_v3 -t upload
```
