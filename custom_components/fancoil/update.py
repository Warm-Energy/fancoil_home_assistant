"""Firmware update entity for the FanCoil.co.uk thermostat.

Shelly-style: the device reports its installed version (/state.fw); this entity polls a
public manifest for the latest release and, on Install, downloads the image in HA and
pushes it to the device's open /ota endpoint (the device flashes + reboots; rollback on
the device reverts a bad image automatically).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

import aiohttp

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN, FIRMWARE_MANIFEST_URL
from .coordinator import FancoilCoordinator
from .entity import FancoilEntity

_LOGGER = logging.getLogger(__name__)
_MANIFEST_INTERVAL = timedelta(hours=6)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: FancoilCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([FancoilUpdate(coordinator, entry)])


class FancoilUpdate(FancoilEntity, UpdateEntity):
    """Reports installed vs latest firmware and flashes via /ota."""

    _attr_name = "Firmware"
    _attr_translation_key = "firmware"
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )

    def __init__(self, coordinator: FancoilCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._base_id}_firmware"
        self._latest: str | None = None
        self._bin_url: str | None = None

    @property
    def available(self) -> bool:
        # Firmware info is ESP-side, so stay available even if the MCU status isn't valid.
        return self.coordinator.last_update_success

    @property
    def installed_version(self) -> str | None:
        return self.data.get("fw")

    @property
    def latest_version(self) -> str | None:
        # Fall back to the installed version so the card reads "up to date" rather
        # than "Unknown" until a manifest is hosted at FIRMWARE_MANIFEST_URL.
        return self._latest or self.installed_version

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await self._refresh_manifest()
        self.async_on_remove(
            async_track_time_interval(
                self.hass, self._refresh_manifest, _MANIFEST_INTERVAL
            )
        )

    async def _refresh_manifest(self, _now: Any = None) -> None:
        session = async_get_clientsession(self.hass)
        try:
            async with asyncio.timeout(15):
                async with session.get(FIRMWARE_MANIFEST_URL) as resp:
                    resp.raise_for_status()
                    data = await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            _LOGGER.debug("firmware manifest unavailable: %s", err)
            return
        self._latest = data.get("version")
        self._bin_url = data.get("url")
        self._attr_release_url = data.get("notes")
        self.async_write_ha_state()

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        if not self._bin_url:
            raise HomeAssistantError("No firmware download URL available")
        session = async_get_clientsession(self.hass)
        host = self._entry.data[CONF_HOST]
        self._attr_in_progress = True
        self.async_write_ha_state()
        try:
            async with asyncio.timeout(60):
                async with session.get(self._bin_url) as resp:
                    resp.raise_for_status()
                    image = await resp.read()
            # Push the raw image to the device's open /ota (it flashes + reboots).
            async with asyncio.timeout(120):
                async with session.post(f"http://{host}/ota", data=image) as resp:
                    resp.raise_for_status()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise HomeAssistantError(f"Firmware update failed: {err}") from err
        finally:
            self._attr_in_progress = False
            self.async_write_ha_state()
        # The device reboots into the new image; versions refresh on the next poll.
        await self.coordinator.async_request_refresh()
