# Future work

Things we've discussed but deliberately deferred — capturing here so they
don't get lost.

## MaxBotix strobe-pin (low-power) mode

The MB7388's pin 4 is a strobe / ranging-enable input. Currently we leave
it floating, which puts the sensor in continuous mode at ~6 Hz and a
~3.4 mA average current draw. We could instead:

1. Wire MaxBotix pin 4 to a Rook GPIO.
2. Drive it LOW between readings → sensor sits in standby (~0.5–1 mA).
3. ~100 ms before we want a reading, drive HIGH (≥ 20 µs pulse, or hold
   HIGH while we drain Serial1).
4. Read the next `Rdddd\r` frame, drive pin 4 LOW again.

Expected savings: ~3 mA → ~1 mA average for the MaxBotix. Whole-node
budget would drop from ~14 mA to ~12 mA — modest but free, and gives
more headroom in cloudy weeks if running on solar.

For deeper savings (~0.06 mA average), power-gate V+ via a P-channel
MOSFET driven by a Rook GPIO. Allow ~50–100 ms after power-on for the
first frame. Trade-off: extra parts (MOSFET, gate pull-up) and longer
warmup per reading.

Either is a small firmware change in `examples/v3-ultrasonic/companion_sensor/main.cpp`
(`updateSensorReadings()` and `setup()`).

Not blocking — solar will work fine at the current ~14 mA budget. Revisit
if cloudy-weather autonomy becomes a real-world problem.

## Reference for solar sizing

See conversation: a 2 W (5 V) panel + TP4056 charger + 1–2 Ah LiPo runs
~14 mA continuously with multi-day cloudy-weather buffer in temperate
latitudes. Same setup that works for a MeshCore repeater works here —
sensor radio duty cycle is comparable or lower.
