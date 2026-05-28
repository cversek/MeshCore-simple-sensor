# Companion Sensor Receiver

A MeshCore firmware that receives `[SENSOR]` messages from companion_sensor nodes and posts the data to [bayou.pvos.org](https://bayou.pvos.org) over WiFi.

## How It Works

1. The receiver listens for incoming mesh messages with the `[SENSOR]` prefix
2. When a sensor message arrives, it parses the node_id, temperature and battery values
3. If WiFi and Bayou keys are configured, it POSTs the data as JSON to the Bayou API
4. All received data is displayed on the OLED and printed to serial

## Building and Flashing

```bash
# Build
pio run -e Heltec_v3_companion_sensor_receiver

# Flash
pio run -e Heltec_v3_companion_sensor_receiver -t upload

# Serial monitor
pio device monitor -b 115200
```

## Setup Workflow

### Step 1: Flash and Boot

Flash the firmware. On first boot, press ENTER in the serial monitor to generate a cryptographic identity.

Optionally set the node name:

```
set name MyReceiver
```

### Step 2: Configure WiFi

```
set wifi_ssid YourNetworkName
set wifi_password YourPassword
```

Reboot the device after setting WiFi credentials (unplug and replug, or press the reset button).

### Step 3: Configure Bayou

Get your Bayou feed keys from [bayou.pvos.org](https://bayou.pvos.org) and set them:

```
set bayou_public_key your-public-key-here
set bayou_private_key your-private-key-here
```

These take effect immediately (no reboot needed). Verify with:

```
status
```

### Step 4: Exchange Contacts with Sensor Node

The receiver and sensor must exchange contact cards. See the [companion_sensor README](../companion_sensor/README.md) for detailed instructions.

**Quick version:**

On the **receiver** serial:
```
card
```
Copy the `meshcore://...` output and import it on the sensor node.

On the **sensor** serial:
```
card
```
Copy its `meshcore://...` output and import it on the receiver:
```
import meshcore://PASTE_HEX_HERE
```

### Step 5: Verify

Once the sensor sends a reading, you should see on the receiver serial:

```
(FLOOD) MSG from Sensor:
   [SENSOR] node_id=1 temp=22.50C batt=3.85V
   [SENSOR DATA] from=Sensor node_id=1 temp=22.50C batt=3.85V hops=2 route=FLOOD
   Posting to Bayou: https://bayou.pvos.org/data/your-public-key
   Bayou post OK (200): ...
```

## Display and Button

The OLED display has 2 pages, cycled with a **short press**:

| Page | Shows | Long Press Action |
|------|-------|-------------------|
| **Status** | WiFi, Bayou status, last received data | -- |
| **Send Advert** | "long press" prompt | Broadcasts a mesh advertisement |

## Bayou API

The receiver POSTs JSON to:

```
POST https://bayou.pvos.org/data/<bayou_public_key>
Content-Type: application/json

{
  "private_key": "<bayou_private_key>",
  "node_id": 1,
  "temperature_c": 22.50,
  "battery_volts": 3.85,
  "aux_1": 2,
  "source": "SensorNodeName"
}
```

- `aux_1` — number of hops the packet took to reach the receiver (path hash count). Useful for mesh health monitoring.

## Serial Commands

| Command | Description |
|---------|-------------|
| `card` | Show your biz card for sharing |
| `import <biz card>` | Import a contact's biz card |
| `list {n}` | List contacts (optionally last n); shows `Contacts: N/MAX` header |
| `purge` | Clear all stored contacts |
| `advert` | Send a mesh advertisement |
| `status` | Show WiFi, Bayou, and last data status |
| `set name <name>` | Set node name |
| `set wifi_ssid <ssid>` | Set WiFi SSID (reboot to apply) |
| `set wifi_password <pwd>` | Set WiFi password (reboot to apply) |
| `set bayou_public_key <key>` | Set Bayou public key |
| `set bayou_private_key <key>` | Set Bayou private key |
| `ver` | Show firmware version |
| `help` | Show command help |

## Build Flags

| Flag | Default | Description |
|------|---------|-------------|
| `ADVERT_NAME` | "Receiver" | Node name advertised on the mesh |
| `MAX_CONTACTS` | 128 | Maximum number of stored contacts (auto-evicts oldest non-favourite when full) |
| `LORA_FREQ` | 910.525 | LoRa frequency in MHz |
| `LORA_BW` | 62.5 | LoRa bandwidth in kHz |
| `LORA_SF` | 7 | LoRa spreading factor |
| `LORA_CR` | 5 | LoRa coding rate |
| `BAYOU_BASE_URL` | "https://bayou.pvos.org/data/" | Bayou API base URL |

## All Settings Are Persisted

All `set` commands save to flash and persist across reboots. WiFi credentials require a reboot to take effect; Bayou keys are used immediately.
