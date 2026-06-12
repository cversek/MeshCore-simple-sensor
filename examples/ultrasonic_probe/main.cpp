// ultrasonic_probe — minimal MaxBotix MB7388 bring-up firmware for Rook v4.
//
// No MeshCore, no LoRa, no filesystem, no display, no key prompt. Just
// USB CDC out + Serial1 in. Boots in <1 s and starts dumping whatever
// arrives on Serial1 at 9600 baud.
//
// Use this when you want a yes/no answer to "is the MaxBotix producing
// frames?" without any of the production firmware's startup sequence
// in the way.
//
// Expected output once per second when the sensor is alive:
//   [Rxxxx\r][Rxxxx\r]...  ← raw bytes, frame brackets added for clarity
//   --- 1s: bytes=42 frames=6 last=R0742\r → 742 mm (0.742 m) ---
//
// Expected output when the sensor is NOT producing frames:
//   --- 1s: bytes=0 frames=0 last=(none) ---
//
// MaxBotix wiring (this firmware mirrors v3-ultrasonic's pinout):
//   MaxBotix pin 5 (TTL TX) → Rook schematic pin 2 (RX1 / P0.08 / D0 / Serial1 RX)
//   MaxBotix pin 6 (V+)     → Rook 3V3 or BAT (BAT preferred to avoid brownout)
//   MaxBotix pin 7 (GND)    → Rook GND
//   MaxBotix pin 4 (strobe) → leave floating for continuous mode

#include <Arduino.h>

#ifndef ULTRASONIC_BAUD
  #define ULTRASONIC_BAUD     9600
#endif
#define USB_BAUD              115200
#define REPORT_INTERVAL_MS    1000

static unsigned long next_report_at = 0;
static unsigned int bytes_since_report = 0;
static unsigned int frames_since_report = 0;
static char last_frame[16] = "(none)";
static int last_mm = -1;

// Frame parser state (persisted across loop() calls).
static bool capturing = false;
static char digits[8];
static int di = 0;

void setup() {
  Serial.begin(USB_BAUD);
  // Hold long enough for USB CDC to enumerate so the banner actually lands
  // in `pio device monitor`. Without this, the first few prints can race the
  // host's tty-open and disappear.
  delay(500);

  Serial.println();
  Serial.println("================================================");
  Serial.println("ultrasonic_probe — MaxBotix MB7388 raw dump");
  Serial.println("================================================");
  Serial.print("Listening on Serial1 @ ");
  Serial.print(ULTRASONIC_BAUD);
  Serial.println(" baud, 8N1.");
  Serial.println("Expect: 'Rdddd\\r' frames at ~6 Hz when sensor is healthy.");
  Serial.println("Press the Rook reset button to restart this probe.");
  Serial.println();

  Serial1.begin(ULTRASONIC_BAUD);

  next_report_at = millis() + REPORT_INTERVAL_MS;
}

void loop() {
  // Drain whatever arrived on Serial1; echo each byte in a readable form,
  // and update the frame parser. Echoing every byte (not just complete
  // frames) means even malformed traffic — wrong baud rate, partial wires,
  // brownout-resetting sensor — shows up on the host.
  while (Serial1.available()) {
    char c = (char)Serial1.read();
    bytes_since_report++;

    if (c >= 32 && c < 127) {
      Serial.write(c);
    } else if (c == '\r') {
      Serial.print("\\r");
    } else if (c == '\n') {
      Serial.println("\\n");
    } else {
      Serial.print("\\x");
      if ((uint8_t)c < 16) Serial.print('0');
      Serial.print((uint8_t)c, HEX);
    }

    if (c == 'R') {
      capturing = true;
      di = 0;
    } else if (capturing) {
      if (c == '\r') {
        digits[di] = 0;
        if (di >= 3) {
          last_mm = atoi(digits);
          frames_since_report++;
          snprintf(last_frame, sizeof(last_frame), "R%s\\r", digits);
        }
        capturing = false;
        di = 0;
      } else if (di < (int)sizeof(digits) - 1 && c >= '0' && c <= '9') {
        digits[di++] = c;
      } else {
        // Non-digit mid-frame: abandon the partial capture.
        capturing = false;
        di = 0;
      }
    }
  }

  if ((long)(millis() - next_report_at) >= 0) {
    Serial.println();
    Serial.print("--- 1s: bytes=");
    Serial.print(bytes_since_report);
    Serial.print(" frames=");
    Serial.print(frames_since_report);
    Serial.print(" last=");
    Serial.print(last_frame);
    if (last_mm >= 0) {
      Serial.print(" → ");
      Serial.print(last_mm);
      Serial.print(" mm (");
      Serial.print((float)last_mm / 1000.0f, 3);
      Serial.print(" m)");
    }
    Serial.println(" ---");

    bytes_since_report = 0;
    frames_since_report = 0;
    next_report_at += REPORT_INTERVAL_MS;
  }
}
