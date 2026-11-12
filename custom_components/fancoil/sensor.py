"""Sensors for the Fancoil thermostat: room temperature and fan speed."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import FancoilCoordinator
from .entity import FancoilEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: FancoilCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [FancoilRoomTemp(coordinator, entry), FancoilFanSpeed(coordinator, entry)]
    )


class FancoilRoomTemp(FancoilEntity, SensorEntity):
    """The thermostat's measured room temperature (0.1 °C resolution)."""

    _attr_translation_key = "room_temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator: FancoilCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._base_id}_room_temp"

    @property
    def native_value(self) -> float | None:
        return self.data.get("room_temp_c")


class FancoilFanSpeed(FancoilEntity, SensorEntity):
    """The fan's current fixed speed, 1–7.

    The panel only reports the fan *setting* — a fixed speed 1–7, or "auto". In auto the
    MCU chooses and drives a speed itself but never reports which one over the UART link,
    so there is no real running speed to show: the sensor is `unknown` (blank) while in
    auto. The fan *mode* (auto / 1–7) is available on the climate entity.
    """

    _attr_translation_key = "fan_speed"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:fan"
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator: FancoilCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._base_id}_fan_speed"

    @property
    def native_value(self) -> int | None:
        fan = self.data.get("fan")
        # 0 == "auto": the MCU doesn't report the speed it runs in auto, so show nothing
        # rather than a misleading 0 (which would read as "fan off").
        if not fan:  # None or 0
            return None
        return int(fan)
