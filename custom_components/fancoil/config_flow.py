"""Config flow: manual host entry + zeroconf discovery.

Both paths resolve each physical unit to its MAC and use that as the config-entry
unique_id, so a device added by IP and later auto-discovered (or vice versa) maps to
exactly ONE Home Assistant device, and a DHCP IP change just updates the stored host.
"""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN
from .coordinator import FancoilApiClient


def _title(mac: str | None, host: str) -> str:
    """Human label: 'FanCoil 70C4' when we know the MAC, else the host."""
    if mac:
        return f"FanCoil {format_mac(mac).replace(':', '')[-4:].upper()}"
    return f"FanCoil ({host})"


class FancoilConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the Fancoil thermostat."""

    VERSION = 1

    def __init__(self) -> None:
        self._host: str | None = None
        self._mac: str | None = None

    async def _probe(self, host: str) -> dict[str, Any]:
        """Confirm the device answers GET /state and return it (carries `mac`)."""
        client = FancoilApiClient(async_get_clientsession(self.hass), host)
        async with asyncio.timeout(10):
            return await client.async_get_state()

    async def _finish(self, host: str, mac: str | None) -> ConfigFlowResult:
        data: dict[str, Any] = {CONF_HOST: host}
        if mac:
            data[CONF_MAC] = format_mac(mac)
        return self.async_create_entry(title=_title(mac, host), data=data)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            try:
                state = await self._probe(host)
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
                errors["base"] = "cannot_connect"
            else:
                mac = state.get("mac")
                # MAC is the stable id; fall back to host for pre-mDNS firmware.
                await self.async_set_unique_id(format_mac(mac) if mac else host)
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                return await self._finish(host, mac)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        host = discovery_info.host
        mac = discovery_info.properties.get("mac")
        # Prefer the TXT MAC; fall back to the instance name (also MAC-derived+unique).
        unique_id = format_mac(mac) if mac else discovery_info.name.split(".", 1)[0]
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        self._host = host
        self._mac = mac
        self.context["title_placeholders"] = {"name": _title(mac, host)}
        return await self.async_step_zeroconf_confirm()

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        # HA matched the DHCP hostname "fancoil-*"; the lease gives us IP + MAC directly.
        self._host = discovery_info.ip
        self._mac = discovery_info.macaddress
        await self.async_set_unique_id(format_mac(self._mac))
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})
        self.context["title_placeholders"] = {"name": _title(self._mac, self._host)}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._host is not None
        if user_input is not None:
            try:
                await self._probe(self._host)
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
                return self.async_abort(reason="cannot_connect")
            return await self._finish(self._host, self._mac)

        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"host": self._host},
        )
