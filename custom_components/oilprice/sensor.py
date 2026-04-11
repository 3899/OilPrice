"""Sensor platform for OilPrice."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_CITY,
    DOMAIN,
    ICON,
    PRICE_SENSOR_KEYS,
    PRICE_UNIT,
    SENSOR_STATE_KEYS,
    location_key,
    location_slug,
    region_name,
)
from .coordinator import OilPriceDataUpdateCoordinator

_ENTITY_META: dict[str, tuple[str, str]] = {
    "gas92": ("92#汽油", "mdi:gas-station"),
    "gas95": ("95#汽油", "mdi:gas-station"),
    "gas98": ("98#汽油", "mdi:gas-station"),
    "die0": ("0#柴油", "mdi:gas-station"),
    "time": ("下次调价", "mdi:clock-outline"),
    "tips": ("调价提示", "mdi:bullhorn-outline"),
    "trend": ("趋势", "mdi:trending-up"),
    "next_adjust_date": ("调价日期", "mdi:calendar-clock"),
    "update_time": ("更新时间", "mdi:update"),
    "friendly_name": ("地区名称", "mdi:map-marker"),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OilPrice sensors from config entry."""
    coordinator: OilPriceDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    async_add_entities(
        [OilPriceFieldSensor(entry, coordinator, field_key) for field_key in SENSOR_STATE_KEYS]
    )


class OilPriceFieldSensor(CoordinatorEntity[OilPriceDataUpdateCoordinator], SensorEntity):
    """One sensor entity per OilPrice field."""

    _attr_has_entity_name = False

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: OilPriceDataUpdateCoordinator,
        field_key: str,
    ) -> None:
        """Initialize field sensor."""
        super().__init__(coordinator)

        self._field_key = field_key
        self._province = entry.data["region"]
        self._city = entry.data.get(CONF_CITY, "")
        self._region_name = region_name(self._city or self._province)
        self._location_key = location_key(self._province, self._city)
        self._location_slug = location_slug(self._province, self._city)
        self._is_price_sensor = field_key in PRICE_SENSOR_KEYS

        field_name, icon = _ENTITY_META[field_key]
        self._attr_icon = icon if field_key != "gas92" else ICON

        self._attr_unique_id = f"{self._location_key}_{field_key}"
        self._attr_suggested_object_id = f"oilprice_{self._location_slug}_{field_key}"
        self.entity_id = f"sensor.oilprice_{self._location_slug}_{field_key}"
        self._attr_name = f"油价-{self._region_name}-{field_name}"
        if self._is_price_sensor:
            self._attr_native_unit_of_measurement = PRICE_UNIT
            self._attr_suggested_display_precision = 2

    @property
    def native_value(self) -> str | float | None:
        """Return the current field value."""
        if self._field_key == "friendly_name":
            return f"油价-{self._region_name}"

        data: dict[str, Any] = self.coordinator.data or {}
        value = data.get(self._field_key)
        if value is None:
            return None
        if self._is_price_sensor:
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
        return str(value)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose change_amount on fuel price sensors only."""
        attrs = dict(super().extra_state_attributes or {})

        if self._is_price_sensor:
            data: dict[str, Any] = self.coordinator.data or {}
            change_key = f"{self._field_key}_change"
            if change_key in data:
                try:
                    attrs["change_amount"] = float(data[change_key])
                except (TypeError, ValueError):
                    attrs["change_amount"] = data[change_key]

        return attrs

    @property
    def device_info(self) -> DeviceInfo:
        """Return device metadata for grouping entities on one device page."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._location_key)},
            name=f"油价-{self._region_name}",
            manufacturer="3899",
            model="OilPrice",
        )
