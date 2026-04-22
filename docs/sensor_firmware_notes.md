# Companion Sensor Firmware Notes

Companion notes to `sensor_setup.md`. Covers features, data flows, and non-obvious behaviours of the `companion_sensor` and `companion_sensor_receiver` firmware as of April 2026.

## Data Flow Overview

```
[ DS18B20 ] --> sensor: [SENSOR] node_id=N temp=T.TTC batt=B.BBV
              --LoRa--> (up to 4 targets, sent in sequence)
              --LoRa--> receiver: parse -> JSON POST to Bayou
                                      { node_id, temperature_c,
                                        battery_volts, aux_1, source }
```

- `aux_1` = number of LoRa radio hops (see "Radio Hops" below)
- `source` = the sender contact name as seen on the receiver

## Node ID (sensor)

- Each sensor has a `node_id` (uint16, default 1), set via `set node_id <N>` on the sensor serial.
- Included in every `[SENSOR]` message so the receiver can post it as `node_id` in the Bayou JSON.
- Purpose: distinguish multiple sensors feeding the same Bayou feed.

## Multi-Target Sending (sensor)

- Sensor supports up to **4 targets** (`MAX_SEND_TARGETS=4`).
- On each `send` (manual or interval), it iterates all targets and sends sequentially.
- Targets are stored as 6-byte public-key prefixes in `/targets` on flash.
- Migration: the first boot after upgrading from the single-target format reads the old `/target` file and imports it as target #1.
- Commands: `target`, `target <name>`, `target add <name>`, `target remove <name>`, `target clear`.

## Contacts List — Size, Overflow, Eviction

### Capacity
- Sensor: `MAX_CONTACTS=32` (default — lean since sensors don't need many contacts)
- Receiver: `MAX_CONTACTS=128`

### Auto-evict on overflow
Both firmwares override `shouldOverwriteWhenFull()` to return `true`. When the list is full and a new advert arrives, `BaseChatMesh::allocateContactSlot()` evicts the **oldest non-favourite** contact (by `lastmod`) to make room. The `onContactOverwrite` hook logs the evicted key prefix to serial.

### How `lastmod` is updated
- Incoming advert from a contact → `lastmod = now`
- Incoming direct message from a contact → `lastmod = now` (BaseChatMesh.cpp:218)
- So a contact that is **actively communicating** is very unlikely to be evicted.
- A contact that has gone **silent** (out of range, dead battery) will have its `lastmod` stale and can eventually be evicted if enough new adverts arrive.

### The `is_new` quirk
`BaseChatMesh::onAdvertRecv` has a subtlety: `is_new` is initialized to `false` and only set to `true` in the three **early-return** branches (auto-add disabled, hop-limit exceeded, slot allocation failed). In the **successful-add** branch, `is_new` stays `false` when `onDiscoveredContact` is called (line 178). Any receiver logic that depends on "`is_new && successful add`" will not fire — match on `pub_key` instead.

This is why the auto-favourite-on-import logic compares pub_key bytes rather than relying on `is_new`.

### Purging
- `purge` command clears all contacts and saves an empty `/contacts`.
- Use it when the list is saturated with junk or you want a clean slate.
- **Warning:** after purge, you cannot receive direct messages from the sensor until it's re-added (either by import or by overhearing its advert). The sender's pub_key is required to compute the shared secret for decryption.

## Favourites (receiver)

A contact's `flags` field has bit `0x01` = favourite. Favourites are never evicted.

- `favourite <name>` — set the flag (name matched by prefix via `searchContactsByPrefix`)
- `unfavourite <name>` — clear the flag
- `list` — shows `*` next to favourite contacts
- **Auto-favourite on import**: `import meshcore://...` now captures the pub_key from the advert bytes before queuing the loopback. When the contact is added (via `onDiscoveredContact`), if the pub_key matches the pending import, the favourite flag is set automatically. Rationale: if you went to the trouble of importing a card manually, you probably want to keep that contact. Protects against the "contacts list fills up and evicts my sensor" footgun.
- Race consideration: between `importContact()` and the loopback being processed, an OTA advert could theoretically arrive with the same pub_key and be favourited first — but that would still result in the intended outcome (the imported contact exists and is favourited).

## Radio Hops (`aux_1`)

The receiver reports the hop count as `aux_1` in the Bayou JSON. This is tricky because MeshCore's two route types handle the path field differently:

- **FLOOD route**: each forwarding repeater **appends** its 1-byte hash to the path. At the destination, `pkt->getPathHashCount() == number of hops`. Straightforward.
- **DIRECT route**: each forwarding repeater **strips** its hash from the start of the path before forwarding (Mesh.cpp:`removeSelfFromPath`). At the destination, the path is empty — `getPathHashCount()` returns 0 even for multi-hop messages.

### Fix: fall back to `out_path_len`
For DIRECT arrivals, the receiver uses its **stored outbound path length** to the sensor (`from.out_path_len`) as the hop count — this is the path the receiver would take to send back to the sensor. Because `PATH_HASH_SIZE=1`, the byte count equals the hop count.

Caveat: **symmetric route assumption**. If the forward and reverse paths differ in length (uncommon but possible under topology changes), the reported hops will be the reverse path's hops.

## Settings Visibility (receiver)

`show_settings` (alias `settings`) prints:
- node name
- WiFi SSID (value); password shown as `****` if set
- Bayou public key (value); private key shown as `****` if set
- contacts count (N/MAX)
- list of favourited contact names

## Identity / Pub Key Stability

The exported `meshcore://` card contains:

| Offset | Bytes | Field          | Stability                                   |
|--------|-------|----------------|---------------------------------------------|
| 0      | 1     | header         | stable per packet type                      |
| 1+     | path  | path bytes     | usually 0 for self-generated cards          |
| next   | 32    | **pub_key**    | **stable for life of the identity file**    |
| +32    | 4     | timestamp      | refreshed each time `card` runs             |
| +36    | 64    | signature      | refreshed (signs fresh timestamp + data)    |
| +100   | N     | app_data (name, type, optional lat/lon) | changes if `set name` is used |

**Key takeaway**: the hex string you copy from `card` will look different every time, but the 32-byte pub_key is identical. Only direct messaging requires the pub_key to match. A new identity is only generated if the identity file on flash is missing (triggers the "Press ENTER to generate key" prompt at boot).

## Troubleshooting Summary

| Symptom                                       | Likely cause                                          |
|-----------------------------------------------|-------------------------------------------------------|
| "Contact imported OK!" but contact not in `list` | List was full and the contact got evicted, or allocation failed. Use `favourite` on contacts you want to keep. `purge` if needed. |
| Messages from known sender stop arriving     | Sender got evicted from contacts (list was full, sender went silent while new adverts piled up). Re-import, then `favourite`. |
| `aux_1` always 0                              | Messages arriving as DIRECT before the symmetric-path fix. Rebuild with current firmware. |
| `node_id=0` in Bayou                          | Sensor firmware is older (no `node_id` field) or sensor was never configured with `set node_id`. |
| `temp` shows ~99.9 / ~100                    | No DS18B20 detected, firmware using dummy value. Check wiring / pullup. |
