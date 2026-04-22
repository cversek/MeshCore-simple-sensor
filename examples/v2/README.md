# v2 — companion sensor / receiver with hop visibility + stale-path recovery

Pair of MeshCore examples that replaces `examples/companion_sensor/` +
`examples/companion_sensor_receiver/` with incremental changes aimed at:

1. **Seeing hop topology** in log output and Bayou data.
2. **Recovering** from stale-direct-path failures (the "message arrives at
   receiver, sender times out waiting for ACK" symptom).

All protocol semantics are unchanged — these are drop-in firmware variants
that use the same MeshCore primitives and wire format, plus a few extra bytes
in the sensor payload.

---

## What's different vs v1

### Sender (`companion_sensor/main.cpp`)

1. **Payload includes sender's view of the path (length + hash bytes).**
   Message text is now `[SENSOR] node_id=N temp=T batt=B fwd_hops=F fwd_path=aa.bb.cc`.
   `F` is the sender's `out_path_len` at send time (255 = "path unknown, will flood").
   `fwd_path` is the cached path as `.`-separated hash bytes (first byte of each
   repeater's hash), or the literal string `none` when the path is unknown.
   Cross-reference with `~/alfred/repeaters.md` (when that exists) to identify
   which specific repeaters a packet passed through.
2. **Verbose path logging before each send.** Shows the cached path bytes
   (not just length). Output like:
   `-> Receiver: (direct, len=2, hashes=5a.91) sent (DIRECT)`
3. **Verbose `onContactPathUpdated`.** Logs the path hash bytes when a new
   path to a contact is learned.
4. **Stale-path recovery via timeout.** On `onSendTimeout`, invalidates the
   cached `out_path` of the last-addressed target (`out_path_len =
   OUT_PATH_UNKNOWN`). The *next* scheduled send will flood, which forces a
   fresh path discovery on both sides. No automatic resend of the same
   message — we let the natural interval handle retransmission, which keeps
   the logic simple and avoids double-sends.

### Receiver (`companion_sensor_receiver/main.cpp`)

1. **Parses the new `fwd_hops` + `fwd_path` fields** from sensor payloads.
2. **Posts them to Bayou:** `aux_2 = fwd_hops` (numeric, alongside existing
   `aux_1` for arrival-measured hops), and `fwd_path = "aa.bb.cc"` (string,
   new field). Downstream visualization plots all three: arrival-measured hop
   count, sender-claimed hop count, and which specific repeaters the sender
   thought it was routing through.
3. **Duplicate-message detection + flood-ACK fallback.** Keeps a small LRU
   (8 entries × 60s window) of recently-handled `(sender_pub_prefix,
   sender_timestamp)` tuples. If a DIRECT message arrives whose key is
   already in the cache, it's inferred that the previous ACK never reached
   the sender (otherwise the sender wouldn't be retrying). Receiver
   invalidates its own reverse `out_path` to the sender *before the base
   class sends the ACK*, so the ACK goes via FLOOD this time, rebuilding the
   reverse path. Self-repairing without sender-side cooperation.
4. **Status line includes `fwd_hops`** in the serial `status` command
   output.

---

## Field semantics (Bayou)

| Field | Source | Meaning |
|-------|--------|---------|
| `aux_1` | Receiver at arrival | Hops measured on this packet (flood: accumulated path-hash count; direct: falls back to stored reverse `out_path_len`) |
| `aux_2` | Sender (v2) | Sender's cached `out_path_len` at the moment of send; 255 = unknown (will flood) |
| `log` | Receiver (v2) | Structured string packed as `path=5a.91.3c route=DIRECT` (or `route=FLOOD`). Bayou's `log VARCHAR(255)` column is the native slot for this kind of free-form metadata. Downstream parsers can split on spaces + `=` to recover `path` and `route` fields. |

**Interpretation cheat-sheet:**

- `aux_1 == aux_2` and both small: stable, short path, both sides agree.
- `aux_1 != aux_2`: the sender and receiver disagree about the topology.
  Usually harmless (flood mode or recent path change), but systematic drift
  hints at stale cache on one side.
- `aux_2 == 255`: sender had no cached path, went flood.
- `route == DIRECT` with many retries: stale forward path (receiver is
  getting the messages fine, but the ACKs aren't landing — sender-side
  invalidation kicks in on timeout).
- `route == FLOOD` immediately after previous DIRECT success: sender
  invalidated its cache after a timeout (recovery).

---

## Build

Same as v1 — the build system picks up examples under `examples/` by convention.

```
cd ~/gitwork/MeshCore-simple-sensor
# sender:
pio run -e t1000-e -d examples/v2/companion_sensor
# receiver:
pio run -e t1000-e -d examples/v2/companion_sensor_receiver
```

Swap `t1000-e` for whichever PlatformIO env you're targeting.

---

## Deploy / test plan

1. Flash **sender v2** onto the greenhouse node. Flash **receiver v2** onto
   the home node. Leave the existing Bayou keys / WiFi config in place —
   they're preserved in flash.
2. Watch the sender's serial output on boot + during the first few sends.
   Confirm the verbose path lines appear and match the number of repeaters
   expected.
3. Watch the receiver's serial: confirm `fwd_hops=N` is being parsed and
   shown in the `[SENSOR DATA]` line and in `status`.
4. Check Bayou — the new `aux_2` field should appear on incoming records.
5. Stress-test: deliberately reboot one of the repeater nodes in the path.
   Expect:
   - Sender's first post-reboot send probably times out.
   - Sender logs "Invalidating cached path" and the next send floods.
   - Receiver sees `fwd_hops=255` on the flood, plus a fresh path update.
   - Subsequent sends go DIRECT again along the new path.

If the duplicate-detection path triggers on the receiver, you'll see a `DUP:`
line in its serial — that means sender was retrying and the receiver
auto-flooded its ACK.

---

## Rollback

v1 untouched at `examples/companion_sensor/` and
`examples/companion_sensor_receiver/`. If v2 misbehaves in the field, re-flash
from v1 and everything is as it was.
