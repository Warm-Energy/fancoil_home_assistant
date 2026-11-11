"""Shared base entity (device info + state access) for the Fancoil platforms."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FancoilCoordinator


class FancoilEntity(CoordinatorEntity[FancoilCoordinator]):
    """Common device_info and a convenient `data` accessor."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FancoilCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry

        # Identify the device by MAC when known (stable across IP changes and across
        # the manual/discovery paths); fall back to the entry id for pre-mDNS firmware.
        mac: str | None = entry.data.get(CONF_MAC)
        # Stable base for entity unique_ids (survives a remove/re-add of the entry).
        self._base_id = mac or entry.entry_id
        name = f"FanCoil {mac.replace(':', '')[-4:].upper()}" if mac else "FanCoil"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac or entry.entry_id)},
            connections={(CONNECTION_NETWORK_MAC, mac)} if mac else set(),
            name=name,
            manufacturer="FanCoil.co.uk",
            model="Fan-coil thermostat",
            sw_version=(coordinator.data or {}).get("fw"),
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

    @property
    def data(self) -> dict[str, Any]:
        """Latest decoded /state snapshot (empty dict before the first poll)."""
        return self.coordinator.data or {}

    @property
    def available(self) -> bool:
        # Reachable AND the MCU has produced a valid status frame.
        return super().available and bool(self.data.get("valid"))
