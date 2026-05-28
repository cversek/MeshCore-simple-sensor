# Rook v4 pin map

Three-way reference for the Rook v4 (Nice Nano / promicro_nrf52840-based)
across the names you'll see in different places:

- **Schematic pin** — what's printed on the Nice Nano symbol in the Rook
  schematic (and on the module's PCB silkscreen).
- **Arduino** — the digital-pin number you pass to `pinMode(N, …)`,
  `digitalRead(N)`, etc. in firmware.
- **nRF52** — the native port.pin name from Nordic's reference manual.

## The D0/D1 gotcha

The repo's local `variants/rook/variant.cpp` defines its own pin map and
**swaps D0 and D1 vs. the canonical Nice Nano layout**:

|  | D0 | D1 |
|---|---|---|
| Canonical Nice Nano | P0.06 (TX) | P0.08 (RX) |
| **This repo's Rook v4** | **P0.08** | **P0.06** |

Confirmed by:

- `variants/rook/variant.cpp:5-10` —
  `g_ADigitalPinMap = { 8, 6, 17, 20, 22, 24, 32, 11, 36, 38, 9, 10, 43, 45, 47, 2, 29, 31, 33, 34, 37, 13, 15 }`
- `variants/rook/variant.h:37-38` —
  `PIN_SERIAL1_TX = (1)` (= Arduino D1 = P0.06),
  `PIN_SERIAL1_RX = (0)` (= Arduino D0 = P0.08)

The silkscreen labels `TX0` and `RX1` are inherited from Pro Micro
convention. They refer to firmware roles — **not** to Arduino digital pin
numbers. So `TX0` silkscreen is on Arduino D1 in this variant; `RX1` is
on D0.

## Left side — user breakouts (schematic pins 1–12)

| Schematic | Arduino | nRF52 | Silkscreen | In-firmware use |
|---|---|---|---|---|
| 1 | D1 | P0.06 | TX0 | `Serial1` TX |
| 2 | D0 | P0.08 | RX1 | `Serial1` RX |
| 3 | — | — | GND | |
| 4 | — | — | GND | |
| 5 | D2 | P0.17 | RF_SW | |
| 6 | D3 | P0.20 | GPS_RX | unused (firmware routes GPS to `Serial1`) |
| 7 | D4 | P0.22 | GPS_TX | unused |
| 8 | D5 | P0.24 | GPS_EN | |
| 9 | D6 | P1.00 | BUTTON_A | `PIN_USER_BTN=6` (user button on Rook v4) |
| 10 | D7 | P0.11 | SCL | `PIN_BOARD_SCL=7` (OLED I²C clock) |
| 11 | D8 | P1.04 | SDA | `PIN_BOARD_SDA=8` (OLED I²C data) |
| 12 | D9 | P1.06 | (P1_06) | `ONEWIRE_PIN=9` (DS18B20 on v2/v3 sensor) |

Earlier Rook revisions had BUTTON_A on P0.06 (Arduino D1). The repo's
defaults were updated 2026-05-24 to match Rook v4 hardware. Don't
reintroduce `PIN_USER_BTN=1` / `PIN_BUTTON1=1` without confirming you're
back on a pre-v4 board.

## Right side — internal / power (schematic pins 13–26)

Mostly LoRa radio and power; the only breakouts here in practice are
`3V3`, `BAT`, and `GND`.

| Schematic | Arduino | nRF52 | Silkscreen | Notes |
|---|---|---|---|---|
| 13 | D10 | P0.09 | LORA_RST | also NFC1 |
| 14 | — | — | DIO1 | LoRa IRQ |
| 15 | — | — | SCK | LoRa SPI clock |
| 16 | — | — | LORA_CS | LoRa chip select |
| 17 | — | — | MOSI | LoRa SPI |
| 18 | — | — | MISO | LoRa SPI |
| 19 | — | — | BUSY | LoRa busy |
| 20 | D16 | P0.29 | MESH_BATT_MEASURE | AIN5 — battery divider tap |
| 21 | — | — | 3V3 | 3.3 V out |
| 22 | — | — | MESH_RST | |
| 23 | — | — | GND | |
| 24, 25 | — | — | BAT | battery + / VBUS when USB-powered |
| 26 | — | — | GND | |

## Full Arduino ↔ nRF52 map

Decoded from `g_ADigitalPinMap`. nRF native numbers use 0–31 for P0.X
and 32–63 for P1.X (so 32 = P1.00, 36 = P1.04, 38 = P1.06, etc.).

| Arduino | nRF52 |  | Arduino | nRF52 |
|---|---|---|---|---|
| D0 | P0.08 | | D12 | P1.11 |
| D1 | P0.06 | | D13 | P1.13 |
| D2 | P0.17 | | D14 | P1.15 |
| D3 | P0.20 | | D15 | P0.02 |
| D4 | P0.22 | | D16 | P0.29 (AIN5) |
| D5 | P0.24 | | D17 | P0.31 (AIN7) |
| D6 | P1.00 | | D18 | P1.01 |
| D7 | P0.11 | | D19 | P1.02 |
| D8 | P1.04 | | D20 | P1.05 |
| D9 | P1.06 | | D21 | P0.13 |
| D10 | P0.09 | | D22 | P0.15 |
| D11 | P0.10 | | | |

## Quick reference for serial peripherals

When wiring something like the MaxBotix MB7388 ultrasonic
(`examples/v2-ultrasonic/`) or a GPS module:

| Peripheral side | Rook side |
|---|---|
| TX (out) | schematic pin **2** — silkscreen `RX1` — P0.08 — Arduino D0 — `Serial1` RX |
| RX (in, if any) | schematic pin **1** — silkscreen `TX0` — P0.06 — Arduino D1 — `Serial1` TX |
| V+ | schematic pin **21** (`3V3`) or pins 24/25 (`BAT` ≈ VBUS) |
| GND | any of pins 3, 4, 23, 26 |

The `[Rook]` base env in `variants/rook/platformio.ini` defines
`PIN_GPS_RX=PIN_SERIAL1_RX` — so the GPS helper, if any of it compiles
in, would also try to use `Serial1`. Pick **one** `Serial1` owner per
build (v2-ultrasonic claims it for the MaxBotix; don't combine with a
GPS build).
