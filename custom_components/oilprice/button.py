"""Button platform for OilPrice."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_CITY,
    DOMAIN,
    location_key,
    location_slug,
    region_name,
)
from .coordinator import OilPriceDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OilPrice refresh button from config entry."""
    coordinator: OilPriceDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    async_add_entities([OilPriceRefreshButton(entry, coordinator)])


class OilPriceRefreshButton(CoordinatorEntity[OilPriceDataUpdateCoordinator], ButtonEntity):
    """Button to trigger immediate refresh."""

    _attr_icon = "mdi:refresh"
    _attr_has_entity_name = False

    def __init__(self, entry: ConfigEntry, coordinator: OilPriceDataUpdateCoordinator) -> None:
        """Initialize refresh button."""
        super().__init__(coordinator)
        self._province = entry.data["region"]
        self._city = entry.data.get(CONF_CITY, "")
        self._region_name = region_name(self._city or self._province)
        self._location_key = location_key(self._province, self._city)
        self._location_slug = location_slug(self._province, self._city)
        self._attr_unique_id = f"{self._location_key}_refresh"
        self._attr_suggested_object_id = f"oilprice_{self._location_slug}_refresh"
        self.entity_id = f"button.oilprice_{self._location_slug}_refresh"
        self._attr_name = f"油价-{self._region_name}-立即更新"

    async def async_press(self) -> None:
        """Handle button press."""
        await self.coordinator.async_request_refresh()

    @property
    def device_info(self) -> DeviceInfo:
        """Return device metadata for grouping entities on one device page."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._location_key)},
            name=f"油价-{self._region_name}",
            manufacturer="3899",
            model="OilPrice",
        )

