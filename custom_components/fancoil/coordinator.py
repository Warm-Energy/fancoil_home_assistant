"""HTTP client + polling coordinator for the Fancoil thermostat."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL_SECONDS

_LOGGER = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=10)


class FancoilApiClient:
    """Thin wrapper over the firmware's local REST API (no auth)."""

    def __init__(self, session: aiohttp.ClientSession, host: str) -> None:
        self._session = session
        self._base = f"http://{host}"

    async def async_get_state(self) -> dict[str, Any]:
        """GET /state -> decoded JSON. Raises on transport/HTTP error."""
        async with self._session.get(f"{self._base}/state", timeout=_TIMEOUT) as resp:
            resp.raise_for_status()
            return await resp.json(content_type=None)

    async def async_set(self, payload: dict[str, Any]) -> None:
        """POST /set with a partial state (only changed fields)."""
        async with self._session.post(
            f"{self._base}/set", json=payload, timeout=_TIMEOUT
        ) as resp:
            resp.raise_for_status()


class FancoilCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls GET /state and shares the decoded snapshot with all entities."""

    def __init__(self, hass: HomeAssistant, client: FancoilApiClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL_SECONDS),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.client.async_get_state()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise UpdateFailed(f"Error talking to fancoil: {err}") from err
