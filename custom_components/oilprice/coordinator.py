"""Data coordinator for the oilprice integration."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    OilPriceData,
    OilPriceApiError,
    OilPriceCannotConnectError,
    OilPriceInvalidRegionError,
    async_fetch_oilprice,
)
from .const import DOMAIN, SCHEDULE_MODE_DAILY, location_key

_LOGGER = logging.getLogger(__name__)
_TWO_PLACES = Decimal("0.01")


class OilPriceDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage oilprice updates with point-in-time scheduling."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        province: str,
        city: str,
        final_query_code: str,
        schedule_mode: str,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{location_key(province, city)}",
            update_interval=None,
        )
        self._entry_id = entry_id
        self._province = province
        self._city = city
        self._final_query_code = final_query_code
        self._schedule_mode = schedule_mode
        self._history_store_key = f"{DOMAIN}_history_{location_key(province, city)}"
        self._store = Store(hass, 1, self._history_store_key)
        self._history_data: dict[str, str] = {}
        self._unsub_tracker = None
        self._scheduled_target_time: datetime | None = None
        self._last_prices_changed = False

    @property
    def province(self) -> str:
        """Return configured province."""
        return self._province

    @property
    def city(self) -> str:
        """Return configured city code if any."""
        return self._city

    @property
    def final_query_code(self) -> str:
        """Return the upstream query code used for fetching."""
        return self._final_query_code

    async def async_config_entry_first_refresh(self) -> None:
        """Load persisted history before the first network refresh."""
        self._history_data = await self._store.async_load() or {}
        self.data = self._history_data.copy()
        await super().async_config_entry_first_refresh()

    async def _async_update_data(self) -> OilPriceData:
        """Fetch latest oilprice data."""
        try:
            current_data = await async_fetch_oilprice(self.hass, self._final_query_code)
        except OilPriceCannotConnectError as err:
            raise UpdateFailed("Unable to connect to oilprice service") from err
        except OilPriceInvalidRegionError as err:
            raise UpdateFailed("Region is invalid or unsupported") from err
        except OilPriceApiError as err:
            raise UpdateFailed(str(err)) from err

        await self._apply_change_amounts(current_data)
        self._schedule_next_update(current_data)
        return current_data

    async def _apply_change_amounts(self, current_data: dict[str, Any]) -> None:
        """Update change_amount values and persist history as needed."""
        needs_save = not self._history_data
        save_data = dict(self._history_data)
        prices_changed = False

        for key in ("gas92", "gas95", "gas98", "die0"):
            price_text = current_data.get(key)
            if price_text is None:
                continue

            new_price = _normalize_decimal(price_text)
            if new_price is None:
                continue

            history_price = _normalize_decimal(self._history_data.get(key))
            if history_price is None:
                change_amount = Decimal("0.00")
                needs_save = True
            elif history_price == new_price:
                change_amount = _normalize_decimal(self._history_data.get(f"{key}_change"))
                if change_amount is None:
                    change_amount = Decimal("0.00")
                    needs_save = True
            else:
                change_amount = (new_price - history_price).quantize(
                    _TWO_PLACES,
                    rounding=ROUND_HALF_UP,
                )
                prices_changed = True
                needs_save = True

            current_data[f"{key}_change"] = float(change_amount)
            save_data[key] = f"{new_price:.2f}"
            save_data[f"{key}_change"] = f"{change_amount:.2f}"

        self._last_prices_changed = prices_changed
        self._history_data = save_data
        if needs_save:
            await self._store.async_save(self._history_data)

    def _next_daily_refresh_time(self) -> datetime:
        """Return the default daily refresh time in China local time."""
        china_tz = dt_util.get_time_zone("Asia/Shanghai") or dt_util.DEFAULT_TIME_ZONE
        local_now = dt_util.now().astimezone(china_tz)
        return (local_now + timedelta(days=1)).replace(
            hour=0,
            minute=5,
            second=0,
            microsecond=0,
        )

    def _schedule_refresh_at(self, new_target_time: datetime) -> None:
        """Schedule a single refresh callback at the given absolute time."""
        if self._scheduled_target_time == new_target_time:
            return

        if self._unsub_tracker is not None:
            self._unsub_tracker()
            self._unsub_tracker = None

        self._scheduled_target_time = new_target_time
        self._unsub_tracker = async_track_point_in_time(
            self.hass,
            self._handle_alarm_trigger,
            new_target_time,
        )

    def _schedule_fallback_refresh(self) -> None:
        """Schedule the conservative fallback refresh after a failed update."""
        self._schedule_refresh_at(self._next_daily_refresh_time())

    def _schedule_next_update(self, current_data: dict[str, Any]) -> None:
        """Schedule the next absolute refresh time."""
        next_daily = self._next_daily_refresh_time()
        china_tz = dt_util.get_time_zone("Asia/Shanghai") or dt_util.DEFAULT_TIME_ZONE
        local_now = dt_util.now().astimezone(china_tz)

        adjust_at = current_data.get("next_adjust_at")
        if adjust_at is not None:
            adjust_at = adjust_at.astimezone(china_tz) + timedelta(minutes=5)

        retry_stale_window = (
            adjust_at is not None
            and adjust_at <= local_now
            and adjust_at.date() == local_now.date()
            and not self._last_prices_changed
        )

        if retry_stale_window:
            # Some upstream pages update prices later than the official 24:00
            # window. Keep polling briefly so change_amount is calculated from
            # the old stored price once the page catches up.
            new_target_time = min(local_now + timedelta(hours=1), next_daily)
        elif self._schedule_mode == SCHEDULE_MODE_DAILY:
            new_target_time = next_daily
        else:
            if adjust_at is None or adjust_at <= local_now:
                new_target_time = next_daily
            else:
                new_target_time = adjust_at

        self._schedule_refresh_at(new_target_time)

    async def _handle_alarm_trigger(self, _trigger_time) -> None:
        """Handle an absolute-time refresh trigger."""
        self._unsub_tracker = None
        self._scheduled_target_time = None

        try:
            await self.async_request_refresh()
        except Exception:
            _LOGGER.exception("Scheduled oilprice refresh failed")
            self._schedule_fallback_refresh()

    def async_unload(self) -> None:
        """Cancel the scheduled refresh callback."""
        if self._unsub_tracker is not None:
            self._unsub_tracker()
            self._unsub_tracker = None
        self._scheduled_target_time = None


def _normalize_decimal(value: Any) -> Decimal | None:
    """Normalize string or numeric price values to two decimal places."""
    if value in (None, ""):
        return None

    try:
        return Decimal(str(value)).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None
