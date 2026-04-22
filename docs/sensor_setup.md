# Companion Sensor Setup Guide

This guide covers the full setup for the **companion_sensor** and **companion_sensor_receiver** firmware pair. The sensor reads a DS18B20 temperature probe and sends readings over the mesh network. The receiver picks up those messages and posts them to [bayou.pvos.org](https://bayou.pvos.org) over WiFi.

## Overview

```
[ DS18B20 ] --> [ Sensor Node ] ~~~LoRa~~~ [ Receiver Node ] --> WiFi --> bayou.pvos.org
```

- **companion_sensor**: Reads temperature, sends `[SENSOR]` messages to a specific contact at a configurable interval
- **companion_sensor_receiver**: Listens for `[SENSOR]` messages and posts the data to Bayou

Both nodes use a simple text-based serial CLI for configuration. All settings are saved to flash and persist across reboots.

## Supported Boards

| Board | Sensor Environment | Receiver Environment |
|-------|-------------------|---------------------|
| Heltec WiFi LoRa 32 V3 | `Heltec_v3_companion_sensor` | `Heltec_v3_companion_sensor_receiver` |
| Rook (nRF52840 + SX1262) | `Rook_companion_sensor` | — (no WiFi) |

The Rook can run the sensor firmware but not the receiver (which requires WiFi for Bayou posting).

## 1. Build and Flash

### Sensor Node (Heltec V3)

```bash
pio run -e Heltec_v3_companion_sensor -t upload
```

### Sensor Node (Rook)

```bash
# Build
pio run -e Rook_companion_sensor

# Flash via UF2: double-tap reset, then copy
cp .pio/build/Rook_companion_sensor/firmware.uf2 /media/$USER/*/

# Or flash via PlatformIO
pio run -e Rook_companion_sensor -t upload
```

### Receiver Node (Heltec V3)

```bash
pio run -e Heltec_v3_companion_sensor_receiver -t upload
```

### Serial Monitor

Use `pio device monitor` (recommended — auto-disconnects during uploads):

```bash
pio device monitor -b 115200
```

Or `screen`:

```bash
screen /dev/ttyUSB0 115200
```

**Note:** If using `screen`, you must quit it (`Ctrl-A` then `k`) before flashing. `pio device monitor` handles this automatically.

## 2. First Boot

On first boot, each node will prompt:

```
Press ENTER to generate key:
```

Press ENTER to generate a cryptographic identity. This only happens once.

## 3. Set Node Names

Give each node a descriptive name so they're easy to identify:

**On the sensor:**
```
set name FarmSensor
```

**On the receiver:**
```
set name FarmReceiver
```

## 4. Exchange Contact Cards

Both nodes need each other's contact cards for encrypted messaging to work. The exchange must go **both ways**.

### Get Each Node's Card

**On the sensor** serial monitor:
```
card
```

This prints something like:
```
meshcore://1100a98ccc696b61232add5dc0...
```

**On the receiver** serial monitor:
```
card
```

This prints the receiver's card in the same format.

### Import Cards

**On the sensor**, paste the receiver's card:
```
import meshcore://PASTE_RECEIVER_CARD_HERE
```

You should see:
```
   hex len=206
   Contact imported OK!
```

**On the receiver**, paste the sensor's card:
```
import meshcore://PASTE_SENSOR_CARD_HERE
```

### Verify Contacts

On either node, check that the contact was imported:
```
list
```

You should see the other node listed by name.

### Alternative: Over-the-Air Discovery

If both nodes are within radio range and using the same radio settings, they will automatically discover each other via mesh advertisements. You'll see:

```
ADVERT from -> FarmSensor [NEW]
```

You can force an advertisement with:
```
advert
```

**Important:** Advertisement-based discovery shares contacts automatically, but it requires both nodes to hear each other's advertisement. For reliable setup, manual card exchange is recommended.

## 5. Set the Sensor's Target(s)

Tell the sensor which contact(s) should receive readings. The sensor supports up to **4 targets** — useful for range testing with a stationary and a mobile receiver.

**Single target:**
```
target FarmReceiver
```

**Multiple targets:**
```
target add HomeReceiver
target add MobileReceiver
```

Name matching is prefix-based. Verify with:

```
target
```

To remove or reset:
```
target remove HomeReceiver
target clear
```

Targets are saved to flash. When `send` runs (manual or interval), the sensor sends the reading to all targets in sequence.

## 6. Configure the Receiver's WiFi

On the **receiver** serial monitor:

```
set wifi_ssid YourNetworkName
set wifi_password YourWiFiPassword
```

**Reboot the receiver** after setting WiFi credentials (press the reset button or unplug/replug). On boot it will connect automatically:

```
   WiFi connecting to: YourNetworkName
   WiFi connected, IP: 192.168.1.42
```

## 7. Configure Bayou Credentials

On the **receiver** serial monitor, set your Bayou feed keys:

```
set bayou_public_key your-bayou-public-key
set bayou_private_key your-bayou-private-key
```

Get these keys from [bayou.pvos.org](https://bayou.pvos.org) when you create a feed.

These take effect immediately (no reboot needed). Verify everything with:

```
status
```

Which shows:
```
   WiFi: connected
   Bayou: idle
   Last: no data received yet
```

## 8. Configure Send Interval

The sensor sends readings every 5 minutes by default. Change it on the **sensor**:

```
set interval 60
```

This sets the interval to 60 seconds. Minimum is 10 seconds.

## 9. Test

### Manual Send

On the **sensor**, force an immediate reading:
```
send
```

Or long-press the button on the "Send Sensor" display page.

### Expected Output

**Sensor serial:**
```
   [SENSOR] [SENSOR] node_id=1 temp=22.50C batt=3.85V
   -> FarmReceiver: sent (FLOOD)
   (1/1 sent)
   Got ACK! (round trip: 1234 millis)
```

**Receiver serial:**
```
(FLOOD) MSG from FarmSensor:
   [SENSOR] node_id=1 temp=22.50C batt=3.85V
   [SENSOR DATA] from=FarmSensor node_id=1 temp=22.50C batt=3.85V hops=2 route=FLOOD
   Posting to Bayou: https://bayou.pvos.org/data/your-public-key
   Bayou post OK (200): ...
```

## Radio Settings

Both nodes must use the same radio parameters. The defaults are:

| Parameter | Value |
|-----------|-------|
| Frequency | 910.525 MHz |
| Bandwidth | 62.5 kHz |
| Spreading Factor | 7 |
| Coding Rate | 5 |

These are set at compile time via build flags. To change them, edit the `build_flags` in the platformio.ini environment.

## Hardware

### Sensor Node (Heltec V3)

- Heltec WiFi LoRa 32 V3
- DS18B20 temperature sensor (optional — uses dummy value 99.9C if not detected)
- 4.7k ohm pullup resistor between DS18B20 DATA and 3.3V

```
DS18B20        Heltec V3
-------        ---------
VCC (red)  --> 3.3V
GND (black) -> GND
DATA (yellow) -> GPIO 7
```

### Sensor Node (Rook)

- Rook board (nRF52840 + SX1262)
- DS18B20 temperature sensor (optional)
- 4.7k ohm pullup resistor between DS18B20 DATA and 3.3V

```
DS18B20        Rook
-------        ----
VCC (red)  --> 3.3V
GND (black) -> GND
DATA (yellow) -> P1.06 (Arduino pin 9)
```

### Receiver Node (Heltec V3)

- Heltec WiFi LoRa 32 V3
- WiFi access point within range
- No additional hardware needed

## Display Pages

### Sensor Node (3 pages, short press to cycle)

| Page | Shows | Long Press |
|------|-------|------------|
| Status | Temp, battery, target, interval | -- |
| Send Sensor | "long press" prompt | Sends a reading now |
| Send Advert | "long press" prompt | Broadcasts advertisement |

### Receiver Node (2 pages, short press to cycle)

| Page | Shows | Long Press |
|------|-------|------------|
| Status | WiFi, Bayou status, last data | -- |
| Send Advert | "long press" prompt | Broadcasts advertisement |

Both displays auto-off after 30 seconds. Any button press wakes the display.

## Message Format

```
[SENSOR] node_id=1 temp=22.50C batt=3.85V
```

The receiver parses `node_id=`, `temp=` and `batt=` values from this format and posts them as JSON to Bayou, along with the packet hop count (useful for mesh health monitoring):

```json
{
  "private_key": "<bayou_private_key>",
  "node_id": 1,
  "temperature_c": 22.50,
  "battery_volts": 3.85,
  "aux_1": 2,
  "source": "FarmSensor"
}
```

- `aux_1` — hop count (path hash count on the received packet)

## Serial Command Reference

### Sensor Commands

| Command | Description |
|---------|-------------|
| `card` | Show your biz card |
| `import meshcore://...` | Import a contact |
| `list` | List contacts (shows `Contacts: N/MAX`) |
| `purge` | Clear all stored contacts |
| `target` | Show current targets |
| `target add <name>` | Add a send target (max 4) |
| `target remove <name>` | Remove a send target |
| `target clear` | Clear all targets |
| `target <name>` | Set to a single target (replaces all) |
| `to <name>` | Alias for `target <name>` |
| `send` | Send a reading now |
| `set name <name>` | Set node name |
| `set node_id <id>` | Set node ID (1-65535, default 1) |
| `set interval <secs>` | Set send interval (min 10) |
| `advert` | Send mesh advertisement |
| `ver` | Show firmware version |
| `help` | Show help |

### Receiver Commands

| Command | Description |
|---------|-------------|
| `card` | Show your biz card |
| `import meshcore://...` | Import a contact |
| `list` | List contacts (shows `Contacts: N/MAX`) |
| `purge` | Clear all stored contacts |
| `status` | Show contacts count, WiFi, Bayou, last data |
| `set name <name>` | Set node name |
| `set wifi_ssid <ssid>` | Set WiFi SSID (reboot to apply) |
| `set wifi_password <pwd>` | Set WiFi password (reboot to apply) |
| `set bayou_public_key <key>` | Set Bayou public key |
| `set bayou_private_key <key>` | Set Bayou private key |
| `advert` | Send mesh advertisement |
| `ver` | Show firmware version |
| `help` | Show help |

## Troubleshooting

**"No targets set, skipping send"** — Run `target add <name>` on the sensor to set at least one destination contact.

**"skip: contact not found for prefix..."** — A target was set but the contact card isn't in the address book. Import the receiver's card on the sensor, or run `target remove <name>` / `target clear` to drop it.

**"No DS18B20 found, using dummy value"** — Normal if no sensor is wired up. The firmware works with a dummy temperature of 99.9C for testing.

**"no bayou keys"** — Set `bayou_public_key` and `bayou_private_key` on the receiver.

**"no wifi" / "WiFi: no SSID"** — Set `wifi_ssid` and `wifi_password` on the receiver and reboot.

**Contact import shows "error: invalid format"** — Make sure you're pasting the full `meshcore://...` string including the prefix. Check that the hex string wasn't truncated during copy/paste.

**Import says "ADVERT from -> Name" but `list` doesn't show the contact** — The contacts list is full. The firmware now auto-evicts the oldest non-favourite contact when full, but if all slots are held by favourites (or if you're on an older build), nothing new can be added. Check contact count with `list` or `status`, then `purge` to clear and re-import.

**Commands show "ERROR: unknown command"** — If the first character is missing, this is a serial monitor quirk. Press ENTER once after connecting before typing commands.
