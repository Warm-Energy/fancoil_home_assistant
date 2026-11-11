"""Climate entity for the Fancoil thermostat."""

from __future__ import annotations

import time
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .const import (
    DOMAIN,
    FAN_MODES,
    FAN_TO_HA,
    HA_TO_FAN,
    HVAC_MODES,
    HVAC_TO_MODE,
    MAX_TEMP,
    MIN_TEMP,
    MODE_TO_HVAC,
    TARGET_TEMP_STEP,
)
from .coordinator import FancoilCoordinator
from .entity import FancoilEntity

# After a command, the MCU needs ~1 status cycle to report the new value back, so a
# single immediate poll reads stale. We show the commanded value optimistically and
# re-poll after this delay; the optimistic value is cleared once a poll confirms it.
_CONFIRM_DELAY = 2.0
_OPTIMISTIC_TTL = 20.0   # safety cap: never hold an unconfirmed value longer than this


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: FancoilCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([FancoilClimate(coordinator, entry)])


class FancoilClimate(FancoilEntity, ClimateEntity):
    """Maps the fan-coil's power/mode/fan/setpoint onto an HA climate entity."""

    _attr_name = None  # take the device name
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = HVAC_MODES
    _attr_fan_modes = FAN_MODES
    _attr_min_temp = MIN_TEMP
    _attr_max_temp = MAX_TEMP
    _attr_target_temperature_step = TARGET_TEMP_STEP
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator: FancoilCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._base_id}_climate"
        # Commanded-but-not-yet-confirmed /state values, overlaid on the real data.
        self._optimistic: dict[str, Any] = {}
        self._optimistic_until = 0.0

    def _val(self, key: str) -> Any:
        """Latest value for a /state key, preferring an optimistic override."""
        if key in self._optimistic:
            return self._optimistic[key]
        return self.data.get(key)

    @callback
    def _handle_coordinator_update(self) -> None:
        # Drop optimistic keys the device has now confirmed (or that have expired),
        # so a fresh poll takes over seamlessly without the UI flipping back first.
        if self._optimistic:
            expired = time.monotonic() >= self._optimistic_until
            data = self.coordinator.data or {}
            for key in list(self._optimistic):
                if expired or data.get(key) == self._optimistic[key]:
                    del self._optimistic[key]
        super()._handle_coordinator_update()

    # ---- read state (optimistic-aware) ----
    @property
    def current_temperature(self) -> float | None:
        return self.data.get("room_temp_c")   # a measurement, never commanded

    @property
    def target_temperature(self) -> float | None:
        # Fan-only/Off have no meaningful setpoint (device reports 0) — hide it.
        if self.hvac_mode in (HVACMode.FAN_ONLY, HVACMode.OFF):
            return None
        return self._val("setpoint_c")

    @property
    def hvac_mode(self) -> HVACMode:
        if not self._val("power"):
            return HVACMode.OFF
        return MODE_TO_HVAC.get(self._val("mode"), HVACMode.FAN_ONLY)

    @property
    def hvac_action(self) -> HVACAction:
        if not self._val("power"):
            return HVACAction.OFF
        # Heating/cooling are live readbacks (not commandable), so use real data.
        if self.data.get("cooling"):
            return HVACAction.COOLING
        if self.data.get("heating"):
            return HVACAction.HEATING
        if self.hvac_mode == HVACMode.FAN_ONLY:
            return HVACAction.FAN
        return HVACAction.IDLE

    @property
    def fan_mode(self) -> str | None:
        return FAN_TO_HA.get(self._val("fan"))

    # ---- write state ----
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self._send({"power": False})
        else:
            await self._send({"power": True, "mode": HVAC_TO_MODE[hvac_mode]})

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            await self._send({"setpoint_c": int(round(temp))})

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        await self._send({"fan": HA_TO_FAN[fan_mode]})

    async def async_turn_on(self) -> None:
        await self._send({"power": True})

    async def async_turn_off(self) -> None:
        await self._send({"power": False})

    async def _send(self, payload: dict[str, Any]) -> None:
        await self.coordinator.client.async_set(payload)
        # Reflect the command in the UI immediately (payload keys mirror /state keys)...
        self._optimistic.update(payload)
        self._optimistic_until = time.monotonic() + _OPTIMISTIC_TTL
        self.async_write_ha_state()
        # ...then confirm from the device once the MCU has had a cycle to apply it.
        async_call_later(self.hass, _CONFIRM_DELAY, self._confirm)

    async def _confirm(self, _now: Any = None) -> None:
        await self.coordinator.async_request_refresh()
