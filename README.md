# FanCoil.co.uk — Home Assistant integration

Local control for the **FanCoil.co.uk** fan-coil thermostat. Talks to the thermostat's
local REST API over your LAN — no cloud, no account, no polling an external service.

[![hacs][hacs-badge]][hacs]

## Features

A single device, auto-discovered on your network:

- **Climate** — power on/off, Heat / Cool / Fan-only, target temperature, fan Auto + 1–7,
  current room temperature, and the live action (heating / cooling / fan / idle).
- **Child-lock** — the panel keypad lock, as a lock entity.
- **Room-temperature sensor** — for history and automations.
- **Firmware update** — reports the installed version and offers one-click updates.

Commands reflect **instantly** in the UI (optimistic), then confirm on the next poll.

## Install (HACS)

1. In HACS → **Integrations** → menu → **Custom repositories**, add
   `https://github.com/Warm-Energy/fancoil_home_assistant` with category **Integration**.
2. Install **FanCoil.co.uk**.
3. **Fully restart Home Assistant** (Settings → System → ⟳ → *Restart Home Assistant*) —
   this step is required, not optional. A "reload" or quick-reload is **not** enough:
   Home Assistant only registers a custom integration's mDNS/DHCP discovery at a full
   startup, so without this restart your thermostat won't be auto-discovered (and the
   integration logo may stay blank).
4. Each thermostat is then **auto-discovered** (mDNS + DHCP) and appears as a card under
   **Settings → Devices & Services** — click that card to add it, no IP needed. (Using
   **+ Add Integration → FanCoil.co.uk** instead will ask for the IP; that's the manual
   path, not a discovery failure.)

Manual install: copy `custom_components/fancoil/` into your HA `config/custom_components/`,
then **fully restart Home Assistant** (same reason as step 3).

See [`custom_components/fancoil/README.md`](custom_components/fancoil/README.md) for the
full details on discovery, multiple units, and firmware updates.

## Requirements

Home Assistant 2024.1 or newer. The integration logo/icon renders natively on
Home Assistant 2026.3+ (local brand images); older versions show a default tile.

## License

[MIT](LICENSE) © FanCoil.co.uk (Warm-Energy)

[hacs]: https://github.com/hacs/integration
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
