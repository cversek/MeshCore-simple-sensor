#!/bin/bash
# Flash companion radio firmware to a Heltec V3 (ESP32-S3) via USB.
#
# Usage:
#   ./flash_heltec_v3.sh              # uses /dev/ttyUSB0
#   ./flash_heltec_v3.sh /dev/ttyACM0 # specify port
#
# Hold the BOOT button on the Heltec while plugging in USB if the
# device isn't detected. Press RST after flashing to reboot.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FIRMWARE="$SCRIPT_DIR/Heltec_v3_companion_radio_usb-v1.14.1-467959c-merged.bin"
PORT="${1:-/dev/ttyUSB0}"

if [ ! -f "$FIRMWARE" ]; then
    echo "Error: Firmware file not found: $FIRMWARE"
    exit 1
fi

if ! command -v esptool.py &> /dev/null; then
    echo "esptool.py not found. Install it with: pip install esptool"
    exit 1
fi

echo "Flashing Heltec V3 on $PORT..."
echo "Firmware: $(basename "$FIRMWARE")"
echo ""

esptool.py --chip esp32-s3 --port "$PORT" --baud 921600 write_flash 0x0 "$FIRMWARE"
