"""Config flow for oilprice integration."""

from __future__ import annotations

import logging
from typing import Any, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_REGION
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .api import OilPriceCannotConnectError, OilPriceInvalidRegionError, async_fetch_oilprice
from .const import (
    CITY_MAP,
    CONF_CITY,
    CONF_FINAL_QUERY_CODE,
    CONF_UPDATE_SCHEDULE_MODE,
    DEFAULT_REGION,
    DEFAULT_SCHEDULE_MODE,
    DOMAIN,
    REGION_SELECTOR_OPTIONS,
    SCHEDULE_MODE_SELECTOR_OPTIONS,
    location_key,
    region_name,
)

_LOGGER = logging.getLogger(__name__)


class OilPriceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for oilprice."""

    VERSION = 4

    def __init__(self) -> None:
        """Store transient flow selections across steps."""
        self._province = DEFAULT_REGION
        self._schedule_mode = DEFAULT_SCHEDULE_MODE

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Return options flow handler."""
        return OilPriceOptionsFlow(config_entry)

    async def async_step_user(self, user_input: Optional[dict[str, Any]] = None) -> FlowResult:
        """Handle province selection and schedule mode."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._province = user_input[CONF_REGION]
            self._schedule_mode = user_input[CONF_UPDATE_SCHEDULE_MODE]

            if self._province in CITY_MAP:
                return await self.async_step_city()

            return await self._async_validate_and_create(self._province, "")

        return self.async_show_form(
            step_id="user",
            data_schema=_build_user_schema(self._province, self._schedule_mode),
            errors=errors,
            last_step=False,
        )

    async def async_step_city(self, user_input: Optional[dict[str, Any]] = None) -> FlowResult:
        """Handle optional city selection for supported provinces."""
        errors: dict[str, str] = {}

        if user_input is not None:
            city = user_input.get(CONF_CITY, "")
            final_query_code = city or self._province
            return await self._async_validate_and_create(final_query_code, city)

        return self.async_show_form(
            step_id="city",
            data_schema=_build_city_schema(self._province),
            errors=errors,
            last_step=True,
        )

    async def _async_validate_and_create(self, final_query_code: str, city: str) -> FlowResult:
        """Validate location against the upstream site and create the entry."""
        errors: dict[str, str] = {}
        unique_id = location_key(self._province, city)

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        try:
            await async_fetch_oilprice(self.hass, final_query_code)
        except OilPriceCannotConnectError:
            errors["base"] = "cannot_connect"
        except OilPriceInvalidRegionError:
            errors["base"] = "invalid_region"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected error while validating region")
            errors["base"] = "unknown"
        else:
            title_code = city or self._province
            return self.async_create_entry(
                title=f"油价-{region_name(title_code)}",
                data={
                    CONF_REGION: self._province,
                    CONF_CITY: city,
                    CONF_FINAL_QUERY_CODE: final_query_code,
                },
                options={CONF_UPDATE_SCHEDULE_MODE: self._schedule_mode},
            )

        if self._province in CITY_MAP:
            return self.async_show_form(
                step_id="city",
                data_schema=_build_city_schema(self._province, city),
                errors=errors,
                last_step=True,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_user_schema(self._province, self._schedule_mode),
            errors=errors,
            last_step=False,
        )


class OilPriceOptionsFlow(config_entries.OptionsFlow):
    """Handle options for oilprice."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: Optional[dict[str, Any]] = None) -> FlowResult:
        """Update schedule mode."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={CONF_UPDATE_SCHEDULE_MODE: user_input[CONF_UPDATE_SCHEDULE_MODE]},
            )

        default_mode = self.config_entry.options.get(
            CONF_UPDATE_SCHEDULE_MODE,
            DEFAULT_SCHEDULE_MODE,
        )
        return self.async_show_form(
            step_id="init",
            data_schema=_build_options_schema(default_mode),
            last_step=True,
        )


def _build_user_schema(default_region: str, default_schedule_mode: str) -> vol.Schema:
    """Build schema for the first setup step."""
    return vol.Schema(
        {
            vol.Required(CONF_REGION, default=default_region): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=REGION_SELECTOR_OPTIONS,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_UPDATE_SCHEDULE_MODE,
                default=default_schedule_mode,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=SCHEDULE_MODE_SELECTOR_OPTIONS,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    )


def _build_city_schema(province: str, default_city: str = "") -> vol.Schema:
    """Build schema for province-specific city selection."""
    options = [{"value": "", "label": "全省/省级默认价"}]
    for code, name in CITY_MAP[province].items():
        options.append({"value": code, "label": name})

    return vol.Schema(
        {
            vol.Required(CONF_CITY, default=default_city): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        }
    )


def _build_options_schema(default_schedule_mode: str) -> vol.Schema:
    """Build schema for options."""
    return vol.Schema(
        {
            vol.Required(
                CONF_UPDATE_SCHEDULE_MODE,
                default=default_schedule_mode,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=SCHEDULE_MODE_SELECTOR_OPTIONS,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        }
    )
