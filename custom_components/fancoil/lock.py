"""Child-lock (keypad lock) entity for the Fancoil thermostat."""

from __future__ import annotations

import time
from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN
from .coordinator import FancoilCoordinator
from .entity import FancoilEntity

_CONFIRM_DELAY = 2.0
_OPTIMISTIC_TTL = 20.0


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: FancoilCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([FancoilLock(coordinator, entry)])


class FancoilLock(FancoilEntity, LockEntity):
    """The panel's physical key lock (prevents local button changes)."""

    _attr_name = "Child lock"
    _attr_translation_key = "child_lock"

    def __init__(self, coordinator: FancoilCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._base_id}_lock"
        self._optimistic: bool | None = None
        self._optimistic_until = 0.0

    @callback
    def _handle_coordinator_update(self) -> None:
        if self._optimistic is not None:
            expired = time.monotonic() >= self._optimistic_until
            if expired or (self.coordinator.data or {}).get("key_lock") == self._optimistic:
                self._optimistic = None
        super()._handle_coordinator_update()

    @property
    def is_locked(self) -> bool | None:
        if self._optimistic is not None:
            return self._optimistic
        return self.data.get("key_lock")

    async def async_lock(self, **kwargs: Any) -> None:
        await self._send(True)

    async def async_unlock(self, **kwargs: Any) -> None:
        await self._send(False)

    async def _send(self, locked: bool) -> None:
        await self.coordinator.client.async_set({"lock": locked})
        self._optimistic = locked
        self._optimistic_until = time.monotonic() + _OPTIMISTIC_TTL
        self.async_write_ha_state()
        async_call_later(self.hass, _CONFIRM_DELAY, self._confirm)

    async def _confirm(self, _now: Any = None) -> None:
        await self.coordinator.async_request_refresh()
