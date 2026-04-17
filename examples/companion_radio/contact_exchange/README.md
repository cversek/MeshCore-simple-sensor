# Contact Exchange

Exchange contact (business card) information between two MeshCore companion nodes via USB serial, so they can send direct messages to each other.

## Setup

```bash
cd examples/companion_radio/contact_exchange
python3 -m venv venv
source venv/bin/activate
pip install meshcore
```

## Usage

### Exchange (both nodes connected at once)

If both nodes are plugged in simultaneously:

```bash
python contact_exchange.py exchange /dev/ttyUSB0 /dev/ttyACM0
```

This exports each node's identity and imports it into the other automatically.

### One node at a time

If you can only connect one node at a time:

**1. Plug in Node A, export its card:**

```bash
python contact_exchange.py export /dev/ttyUSB0 -o card_a.txt
```

**2. Unplug Node A, plug in Node B. Export its card and import Node A's:**

```bash
python contact_exchange.py export /dev/ttyUSB0 -o card_b.txt
python contact_exchange.py import /dev/ttyUSB0 -i card_a.txt
```

**3. Unplug Node B, plug Node A back in. Import Node B's card:**

```bash
python contact_exchange.py import /dev/ttyUSB0 -i card_b.txt
```

Both nodes now have each other's contact information.

### Additional options

Export a card to stdout (without saving to file):

```bash
python contact_exchange.py export /dev/ttyUSB0
```

Import a card directly from a URI string:

```bash
python contact_exchange.py import /dev/ttyUSB0 -c "meshcore://ab01cd..."
```

Set a custom baud rate (default is 115200):

```bash
python contact_exchange.py --baud 9600 export /dev/ttyUSB0
```

## Radio Settings

Before exchanging contacts, make sure both nodes are using the same radio parameters. The current MeshCore USA defaults are:

| Parameter | Value |
|-----------|-------|
| Frequency | 910.525 MHz |
| Bandwidth | 62.5 kHz |
| Spreading Factor | 7 |
| Coding Rate | 5 |

You can set these via meshcore-cli over USB serial:

```bash
meshcli -s /dev/ttyUSB0 set radio 910.525,62.5,7,5
```

A reboot is required after changing radio params:

```bash
meshcli -s /dev/ttyUSB0 reboot
```

## Sending Direct Messages with meshcli

Once two nodes have exchanged contacts (see above), you can send direct messages between them using `meshcli`.

Install with:

```bash
pipx install meshcore-cli
```

### Contact Management

```bash
# List all contacts
meshcli -s /dev/ttyUSB0 contacts

# Show your own business card (for sharing)
meshcli -s /dev/ttyUSB0 card

# Import a contact from a URI
meshcli -s /dev/ttyUSB0 import_contact "meshcore://ab01cd..."
```

### One-Shot Direct Message

Send a message to a named contact in a single command:

```bash
meshcli -s /dev/ttyUSB0 msg <contact-name> "Hello!"
```

Add `wait_ack` to block until delivery is confirmed:

```bash
meshcli -s /dev/ttyUSB0 msg Techo_fdl "Hello T-Echo" wait_ack
```

### Interactive Chat Mode

Launch without a command to enter interactive mode with tab-completion and real-time messaging:

```bash
meshcli -s /dev/ttyUSB0
```

Then inside the session:

```
> contacts              # list contacts
> to Techo              # select recipient (prefix match works)
Techo_fdl> Hello!       # type message and press Enter to send
```

Use `to /` to return to root, `to ..` for the previous contact, or `to !` to reply to the last sender.

### Other Messaging Commands

| Command | Shortcut | Description |
|---------|----------|-------------|
| `msg <name> <text>` | `m` | Send a direct message |
| `contacts` | `lc` | List all contacts |
| `recv` | `r` | Read next incoming message |
| `wait_msg` | `wm` | Block until a message arrives |
| `wait_ack` | `wa` | Wait for delivery acknowledgment |
| `sync_msgs` | `sm` | Retrieve all unread messages |
| `card` | `e` | Show your business card |
| `public <text>` | `dch` | Send to the public channel |
| `chan <nb> <text>` | `ch` | Send to a specific channel |

### Connection Options

The examples above use `-s /dev/ttyUSB0` for USB serial. Other transports:

```bash
# BLE (scan and select)
meshcli -S

# BLE (specific address)
meshcli -a <ble_address>

# TCP
meshcli -t <hostname> -p <port>
```
