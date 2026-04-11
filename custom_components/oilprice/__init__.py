"""The oilprice integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import (
    CONF_CITY,
    CONF_FINAL_QUERY_CODE,
    CONF_UPDATE_SCHEDULE_MODE,
    DEFAULT_SCHEDULE_MODE,
    DOMAIN,
    PLATFORMS,
    location_key,
)
from .coordinator import OilPriceDataUpdateCoordinator


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up integration."""
    hass.data.setdefault(DOMAIN, {})
    return True


def _desired_entity_id(platform: str, location_slug: str, suffix: str) -> str:
    """Build the canonical entity_id for this integration."""
    return f"{platform}.oilprice_{location_slug}_{suffix}"


async def _async_normalize_entity_ids(
    hass: HomeAssistant,
    entry: ConfigEntry,
    province: str,
    city: str,
) -> None:
    """Rename entities for this config entry to the canonical oilprice_* style."""
    entity_registry = er.async_get(hass)
    location = location_key(province, city)
    location_slug = location

    for entity_entry in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        if entity_entry.domain == "sensor":
            prefix = f"{location}_"
            if not entity_entry.unique_id.startswith(prefix):
                continue
            suffix = entity_entry.unique_id.removeprefix(prefix)
            desired_entity_id = _desired_entity_id("sensor", location_slug, suffix)
        elif entity_entry.domain == "button":
            if entity_entry.unique_id != f"{location}_refresh":
                continue
            desired_entity_id = _desired_entity_id("button", location_slug, "refresh")
        else:
            continue

        if entity_entry.entity_id == desired_entity_id:
            continue

        try:
            entity_registry.async_update_entity(
                entity_entry.entity_id,
                new_entity_id=desired_entity_id,
            )
        except ValueError:
            continue


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up integration from UI config entry."""
    province = entry.data["region"]
    city = entry.data.get(CONF_CITY, "")
    final_query_code = entry.data.get(CONF_FINAL_QUERY_CODE, province)
    schedule_mode = entry.options.get(CONF_UPDATE_SCHEDULE_MODE, DEFAULT_SCHEDULE_MODE)

    hass.data.setdefault(DOMAIN, {})

    coordinator = OilPriceDataUpdateCoordinator(
        hass,
        entry.entry_id,
        province,
        city,
        final_query_code,
        schedule_mode,
    )
    try:
        await coordinator.async_config_entry_first_refresh()
    except UpdateFailed as err:
        raise ConfigEntryNotReady("Failed to initialize oilprice data") from err

    await _async_normalize_entity_ids(hass, entry, province, city)

    unsubscribe_update_listener = entry.add_update_listener(_async_update_listener)
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "unsubscribe_update_listener": unsubscribe_update_listener,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        runtime = hass.data[DOMAIN].pop(entry.entry_id, None)
        if runtime:
            if runtime.get("unsubscribe_update_listener"):
                runtime["unsubscribe_update_listener"]()
            if runtime.get("coordinator"):
                runtime["coordinator"].async_unload()
    return unload_ok
