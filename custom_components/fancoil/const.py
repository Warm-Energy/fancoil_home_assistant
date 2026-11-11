"""Constants and device<->HA mappings for the Fancoil integration."""

from __future__ import annotations

from homeassistant.components.climate import HVACMode

DOMAIN = "fancoil"

# Public firmware manifest the update entity polls for the latest release. Serve a small
# JSON here:  {"version": "1.1.0", "url": "https://.../fancoil-1.1.0.bin", "notes": "https://..."}
# Until this exists the update entity simply shows no update available (fails soft).
FIRMWARE_MANIFEST_URL = "https://github.com/Warm-Energy/fancoil_thermostat/releases/latest/download/latest.json"

# How often we poll GET /state (seconds). The ESP answers in a few ms on the LAN.
# Commands are reflected instantly (optimistic), so this mainly bounds how fast a
# change made on the physical panel shows up in HA.
SCAN_INTERVAL_SECONDS = 10

# Setpoint range exposed to HA. The firmware sends whole °C; the MCU may clamp
# to its own cool_bot/heat_top limits, so this is a safe superset.
MIN_TEMP = 5
MAX_TEMP = 35
TARGET_TEMP_STEP = 1.0

# --- Device "mode" datapoint (GET /state) <-> HA HVACMode -----------------------
# Device-confirmed live: 0 = HEAT (heating flag @ setpoint 35), 1 = COOL,
# 2 = FAN-only (heating/cooling both off @ fan 7). OFF is the power flag, not a
# mode. A panel mode we don't expose (e.g. dehumidify) falls back to fan-only.
MODE_TO_HVAC: dict[int, HVACMode] = {
    0: HVACMode.HEAT,
    1: HVACMode.COOL,
    2: HVACMode.FAN_ONLY,
}
HVAC_TO_MODE: dict[HVACMode, int] = {v: k for k, v in MODE_TO_HVAC.items()}

# Modes offered in the UI (no Auto). OFF is driven by the power flag.
HVAC_MODES = [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.FAN_ONLY]

# --- Device "fan" datapoint (GET /state) <-> HA fan mode ------------------------
# 0 = Auto, 1..7 = speed level (this unit has 7). /state and /set share this same
# value, so it round-trips. (Confirmed: fan=0 reads as Auto on the panel.)
FAN_AUTO = "auto"
FAN_TO_HA: dict[int, str] = {0: FAN_AUTO, **{i: str(i) for i in range(1, 8)}}
HA_TO_FAN: dict[str, int] = {v: k for k, v in FAN_TO_HA.items()}
FAN_MODES = list(HA_TO_FAN)   # ["auto", "1", "2", "3", "4", "5", "6", "7"]
