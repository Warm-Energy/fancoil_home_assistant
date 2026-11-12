# FanCoil.co.uk — Home Assistant integration

Local control for the **FanCoil.co.uk** fan-coil thermostat. Talks to the thermostat's
local REST API (`GET /state`, `POST /set`) — no cloud, no account.

## What you get

A single device with:

- **Climate entity** — power (on/off via HVAC mode), mode (heat / cool / fan-only),
  target temperature, fan (Auto + 1–7), current room temperature, and the live
  action (heating / cooling / fan / idle).
- **Child-lock** lock entity — the panel keypad lock.
- **Room-temperature sensor** — the measured room temp, for history/automations.
- **Fan-speed sensor** — the running speed (1–7); `0` when off, blank in *auto* (the panel
  never reports the speed it picks internally; the fan *mode* is on the climate entity).
- **Firmware update entity** — installed vs latest, one-click install (see below).

Polls `/state` every 10 s; commands reflect **instantly** (optimistic) and are then
confirmed by a quick re-poll.

## Install

1. Copy `custom_components/fancoil/` into your Home Assistant `config/custom_components/`
   directory (so you end up with `config/custom_components/fancoil/`).
   (Or add this repo to HACS as a custom repository.)
2. Restart Home Assistant.
3. Each thermostat on the same subnet is **auto-discovered** (see below) and shows
   up under **Settings → Devices & Services → Discovered** — click *Configure* to add it.
   To add one manually (or across subnets), use **Add Integration → "Fancoil
   Thermostat"** and enter its IP (e.g. `192.0.2.50`).

## Discovery & multiple thermostats

Discovery uses **two** transports so it survives different network setups; HA auto-adds
each unit via whichever gets through, no manual step:

- **DHCP** (primary, most robust) — the device sets its DHCP hostname to `fancoil-<mac>`;
  HA matches `fancoil-*` and auto-loads the integration. DHCP is broadcast/router-based,
  so it works even on WiFi that prunes multicast (IGMP snooping), and reaches across real
  subnets when HA has a router/controller integration (UniFi, Mikrotik, …) that exposes
  the lease table.
- **mDNS/zeroconf** (`_fancoil._tcp`, port 80) — advertised the moment the device gets an
  IP. Instant where multicast is allowed (flat L2, or a VLAN with an mDNS reflector).

Both paths key each unit on its MAC, so a device found by DHCP, mDNS, *and* manual entry
still resolves to one HA device.

It works cleanly with any number of units because identity is keyed on the **MAC**, not
the IP:

- Each unit advertises a unique, MAC-derived name (`fancoil-70c5.local`) and its full
  MAC in a TXT record; HA uses that MAC as the config-entry id.
- A unit added **manually by IP** and later **auto-discovered** resolve to the *same*
  MAC, so you never get a duplicate device.
- **DHCP IP changes self-heal:** when the device re-announces with a new address, HA
  updates the stored host automatically (no re-add).
- Each device is named by its MAC suffix (`FanCoil 70C4`) so several are distinguishable.

**Subnet caveat:** mDNS is link-local multicast, so HA and the thermostats must share a
subnet/VLAN. If your IoT devices are on a separate VLAN, either run an mDNS reflector
(e.g. Avahi / UniFi mDNS / pfSense) or just add each unit manually by IP — manual add is
still MAC-keyed, so all the dedup/rename benefits above apply.

Verify a device is advertising (from a Mac on the same subnet):

```bash
dns-sd -B _fancoil._tcp        # lists each thermostat instance
```

## ⚠ Verify the mode / fan mapping (30 seconds)

The firmware reports `mode` and `fan` as small integers. Only **`mode 1 = cool`** is
device-confirmed; the rest are best-guesses. To check:

1. On the physical panel, set a mode (e.g. Heat). 
2. Open `http://<device-ip>/state` in a browser and note the `mode` number.
3. Repeat for each mode and fan speed.
4. If anything is off, fix the **one** dict in [`const.py`](const.py):
   `MODE_TO_HVAC` / `FAN_TO_HA`. Everything else derives from it.

## Firmware updates

Three ways, Shelly-style:

1. **HA update entity** — the device reports its version (`/state.fw`); the `update`
   entity polls a public manifest and offers one-click **Install**. HA downloads the
   image and pushes it to the device's `/ota`; the device flashes and reboots, and its
   **rollback** reverts automatically if the new image boot-loops.
   Host a small manifest at the URL in `const.py` (`FIRMWARE_MANIFEST_URL`):
   ```json
   { "version": "1.1.0",
     "url":     "https://fancoil.co.uk/fw/fancoil-1.1.0.bin",
     "notes":   "https://fancoil.co.uk/fw/1.1.0" }
   ```
   Until that exists the entity just shows "up to date" (fails soft).
2. **Device web UI** — open `http://<device-ip>/`, pick a `.bin`, **Upload & flash**.
3. **curl** — `curl --data-binary @firmware.bin http://<device-ip>/ota`.

The OTA endpoint is intentionally **open** (no auth/signing) — the device is yours to
reflash. Rollback makes that safe: a bad image reverts on the next boot.

## Notes / limitations

- **Open API, by design** — the local API (including `POST /ota`) has no auth. The
  device is meant to be user-reflashable; keep it on a trusted LAN, not the internet.
- Setpoint is whole °C; the UI step is 1°. The MCU may clamp to its own
  `cool_bot` / `heat_top` limits.
- The climate/lock/sensor entities go *unavailable* if the device is unreachable or
  the MCU hasn't yet produced a valid status frame (`"valid": false`); the firmware
  update entity stays available (its data is ESP-side).

The companion open firmware for the thermostat lives at
[Warm-Energy/fancoil_thermostat](https://github.com/Warm-Energy/fancoil_thermostat).
