// v4: SX1262 SPI sleep + nRF52840 System OFF, for JS220 sleep profiling (Rook).
//
// v1 (System OFF) 2.82 mA; v2/v3 (+ POWER_EN low + USB off + cold cycle) stuck flat at
// 1.05 mA, voltage-INDEPENDENT -> a load behind a regulator that never got the sleep
// command. Hypothesis: POWER_EN low only killed the TCXO/RF-switch (the 1.77 mA we saw
// drop); the SX1262 digital core is still in standby (~1 mA). Only a SPI SLEEP opcode
// (RadioLib radio.sleep()) puts the core to ~1 uA. v4 powers the radio, inits it, sleeps
// it over SPI, then sleeps the MCU.

#include <Arduino.h>
#include <SPI.h>
#include <RadioLib.h>

#define P_LORA_NSS   13
#define P_LORA_DIO_1 11
#define P_LORA_RESET 10
#define P_LORA_BUSY  16
#define P_LORA_MISO  15
#define P_LORA_SCLK  12
#define P_LORA_MOSI  14
#define SX126X_POWER_EN 21       // P0.13 active-HIGH radio module enable
#define SX126X_RXEN      2       // P0.17 RF switch RX

SPIClass spiLora(NRF_SPIM3, P_LORA_MISO, P_LORA_SCLK, P_LORA_MOSI);
SX1262 radio = new Module(P_LORA_NSS, P_LORA_DIO_1, P_LORA_RESET, P_LORA_BUSY, spiLora);

void setup() {
  delay(3000);                                  // awake window (boot blip)

  pinMode(SX126X_POWER_EN, OUTPUT); digitalWrite(SX126X_POWER_EN, HIGH);  // power radio to talk to it
  pinMode(SX126X_RXEN, OUTPUT);     digitalWrite(SX126X_RXEN, LOW);
  delay(10);

  spiLora.begin();
  // freq, bw, sf, cr, sync, power, preamble, tcxoVoltage=1.8 (Rook DIO3 TCXO), useLDO=false
  radio.begin(910.525, 62.5, 7, 5, RADIOLIB_SX126X_SYNC_WORD_PRIVATE, 22, 8, 1.8, false);
  radio.setDio2AsRfSwitch(true);
  radio.sleep();                                // SX1262 -> deep sleep (~1 uA)

  NRF_USBD->ENABLE = 0;                         // release USB
  NRF_POWER->SYSTEMOFF = 1;                     // nRF System OFF
  while (1) { __WFE(); }
}

void loop() {}
