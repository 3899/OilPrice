"""API helpers for the oilprice integration."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Optional, Tuple, TypedDict

from aiohttp import ClientError
from bs4 import BeautifulSoup
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import region_name

_BASE_URL = "http://www.huangjinjiage.cn/oil/{region}.html"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
}
_PRICE_VALUE_PATTERN = re.compile(r"(?P<value>\d+\.\d+)(?:\s*元/升)?")


class OilPriceData(TypedDict):
    """Structured payload returned by the upstream parser."""

    state: float | str
    gas92: float | None
    gas95: float | None
    gas98: float | None
    die0: float | None
    time: str | None
    tips: str | None
    trend: str | None
    next_adjust_date: str | None
    next_adjust_at: datetime | None
    update_time: str
    region: str
    region_name: str


class OilPriceApiError(Exception):
    """Base API error."""


class OilPriceCannotConnectError(OilPriceApiError):
    """Raised when remote endpoint cannot be reached."""


class OilPriceInvalidRegionError(OilPriceApiError):
    """Raised when region is invalid or unsupported."""


async def async_fetch_oilprice(hass, region: str) -> OilPriceData:
    """Fetch and parse oil price information for a region."""
    session = async_get_clientsession(hass)

    try:
        async with session.get(_BASE_URL.format(region=region), headers=_HEADERS) as response:
            if response.status >= 400:
                raise OilPriceCannotConnectError
            raw_bytes = await response.read()
            text = _decode_page(raw_bytes)
    except ClientError as err:
        raise OilPriceCannotConnectError from err

    soup = BeautifulSoup(text, "html.parser")
    normalized_text = _normalize_text(soup.get_text("\n", strip=True))

    table_prices = _extract_prices_from_tables(soup)
    parsed_prices = _extract_prices_by_section(normalized_text)
    gas92 = _to_float_price(_pick_price(table_prices.get("gas92"), parsed_prices.get("gas92")))
    gas95 = _to_float_price(_pick_price(table_prices.get("gas95"), parsed_prices.get("gas95")))
    gas98 = _to_float_price(_pick_price(table_prices.get("gas98"), parsed_prices.get("gas98")))
    die0 = _to_float_price(_pick_price(table_prices.get("die0"), parsed_prices.get("die0")))

    time_text, tips_text = _extract_notice_fields(soup, normalized_text)
    trend_text = _extract_trend_text(tips_text)
    next_adjust_at = _extract_next_adjust_at(time_text)
    next_adjust_date = _format_adjust_datetime(next_adjust_at)

    if not _has_any_core_price(gas92, gas95, gas98, die0):
        raise OilPriceInvalidRegionError

    update_time = dt_util.now().strftime("%Y-%m-%d %H:%M:%S")
    state = gas92 or time_text or "unknown"

    return {
        "state": state,
        "gas92": gas92,
        "gas95": gas95,
        "gas98": gas98,
        "die0": die0,
        "time": time_text,
        "tips": tips_text,
        "trend": trend_text,
        "next_adjust_date": next_adjust_date,
        "next_adjust_at": next_adjust_at,
        "update_time": update_time,
        "region": region,
        "region_name": region_name(region),
    }


def _extract_notice_fields(
    soup: BeautifulSoup, page_text: str
) -> Tuple[Optional[str], Optional[str]]:
    """Extract notice time and tips from huangjinjiage page text."""
    page_lines = [_normalize_text(line) for line in soup.stripped_strings]
    page_lines = [line for line in page_lines if line]

    time_text = _extract_time_text(page_text)
    tip_text = _extract_tips_text(page_lines)

    return time_text, tip_text


def _normalize_text(text: str) -> str:
    """Normalize whitespace for predictable regex parsing."""
    return re.sub(r"\s+", " ", text).strip()


def _decode_page(raw_bytes: bytes) -> str:
    """Decode source page with fallback charsets used by Chinese websites."""
    for encoding in ("utf-8", "gb18030", "gbk"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue

    return raw_bytes.decode("utf-8", errors="ignore")


def _extract_prices_by_section(page_text: str) -> dict[str, Optional[str]]:
    """Extract fuel prices from ordered gasoline/diesel sections."""
    values = {"gas92": None, "gas95": None, "gas98": None, "die0": None}

    gasoline_match = re.search(
        r"今日汽油价格[（(]元/升[）)](.*?)今日柴油价格[（(]元/升[）)]",
        page_text,
    )
    if gasoline_match is not None:
        gasoline_prices = _extract_price_tokens(gasoline_match.group(1))
        # Order on page: 89, 92, 95, 98.
        if len(gasoline_prices) >= 4:
            values["gas92"] = _none_if_dash(gasoline_prices[1])
            values["gas95"] = _none_if_dash(gasoline_prices[2])
            values["gas98"] = _none_if_dash(gasoline_prices[3])

    diesel_match = re.search(
        r"今日柴油价格[（(]元/升[）)](.*?)(?:油价调整最新消息|今日油价最新消息|$)",
        page_text,
    )
    if diesel_match is not None:
        diesel_prices = _extract_price_tokens(diesel_match.group(1))
        # Order on page: 0, -10, -20, -35.
        if diesel_prices:
            values["die0"] = _none_if_dash(diesel_prices[0])

    return values


def _extract_prices_from_tables(soup: BeautifulSoup) -> dict[str, Optional[str]]:
    """Extract prices from table.bx layout by reading the first data row after headers."""
    values = {"gas92": None, "gas95": None, "gas98": None, "die0": None}

    for table in soup.select("table.bx"):
        table_prices = _extract_prices_from_table_first_data_row(table)
        if any(table_prices.values()):
            for key, value in table_prices.items():
                if values[key] is None and value is not None:
                    values[key] = value
            continue

        header_cells = table.select("tbody tr:nth-of-type(1) th, tbody tr:nth-of-type(1) td")
        value_cells = table.select("tbody tr:nth-of-type(2) td, tbody tr:nth-of-type(2) th")
        if not header_cells or not value_cells:
            continue

        for index, header_cell in enumerate(header_cells):
            if index >= len(value_cells):
                continue

            header_text = _normalize_text(header_cell.get_text(" ", strip=True))
            value_text = _normalize_text(value_cells[index].get_text(" ", strip=True))
            value = _normalize_price_value(value_text)

            if "92" in header_text and "汽油" in header_text:
                values["gas92"] = value
            elif "95" in header_text and "汽油" in header_text:
                values["gas95"] = value
            elif "98" in header_text and "汽油" in header_text:
                values["gas98"] = value
            elif header_text.startswith("0") and "柴油" in header_text:
                values["die0"] = value

    return values


def _extract_prices_from_table_first_data_row(table) -> dict[str, Optional[str]]:
    """Extract prices from the first data row after a matching header row."""
    values = {"gas92": None, "gas95": None, "gas98": None, "die0": None}

    rows = table.select("tbody tr")
    if len(rows) < 2:
        return values

    for header_row_index, row in enumerate(rows[:-1]):
        cells = row.select("td, th")
        if not cells:
            continue

        header_texts = [_normalize_text(cell.get_text(" ", strip=True)) for cell in cells]
        has_target_header = any(
            ("92" in text and "汽油" in text)
            or ("95" in text and "汽油" in text)
            or ("98" in text and "汽油" in text)
            or (text.startswith("0") and "柴油" in text)
            for text in header_texts
        )
        if not has_target_header:
            continue

        header_cells = rows[header_row_index].select("td, th")

        # Find the first non-empty data-like row below the matched header row.
        first_data_cells = []
        for candidate_row in rows[header_row_index + 1 :]:
            candidate_cells = candidate_row.select("td, th")
            if not candidate_cells:
                continue

            candidate_texts = [
                _normalize_text(cell.get_text(" ", strip=True)) for cell in candidate_cells
            ]
            if any(_normalize_price_value(text) is not None for text in candidate_texts):
                first_data_cells = candidate_cells
                break

        if not first_data_cells:
            continue

        for index, header_cell in enumerate(header_cells):
            if index >= len(first_data_cells):
                continue

            header_text = _normalize_text(header_cell.get_text(" ", strip=True))
            value_text = _normalize_text(first_data_cells[index].get_text(" ", strip=True))
            value = _normalize_price_value(value_text)

            if "92" in header_text and "汽油" in header_text:
                values["gas92"] = value
            elif "95" in header_text and "汽油" in header_text:
                values["gas95"] = value
            elif "98" in header_text and "汽油" in header_text:
                values["gas98"] = value
            elif header_text.startswith("0") and "柴油" in header_text:
                values["die0"] = value

        if any(values.values()):
            break

    return values


def _extract_price_tokens(text: str) -> list[str]:
    """Return ordered price-like tokens (decimal or standalone dash)."""
    return re.findall(r"\d+\.\d+|(?<!\d)-(?=\s|$)", text)


def _none_if_dash(value: str) -> Optional[str]:
    """Convert placeholder dash to None."""
    return None if value == "-" else value


def _normalize_price_value(value: str) -> Optional[str]:
    """Normalize table price cell value."""
    if not value or value == "-":
        return None

    match = _PRICE_VALUE_PATTERN.fullmatch(value)
    if match is None:
        return None
    return match.group("value")


def _pick_price(primary: Optional[str], fallback: Optional[str]) -> Optional[str]:
    """Pick primary parsed value, otherwise fallback value."""
    return primary if primary is not None else fallback


def _to_float_price(value: Optional[str]) -> float | None:
    """Convert a normalized price string to float."""
    if value is None:
        return None
    return float(value)


def _has_any_core_price(*values: float | None) -> bool:
    """Return True when the page contains at least one usable fuel price."""
    return any(value is not None for value in values)


def _extract_time_text(page_text: str) -> Optional[str]:
    """Extract next adjustment time sentence."""
    match = re.search(r"(油价下次调价时间[为:：]?[^；。\n]+)", page_text)
    if match is not None:
        return match.group(1).strip()

    match = re.search(r"(下次国内成品油价调整窗口时间为[^；。\n]+)", page_text)
    if match is not None:
        return match.group(1).strip()

    return None


def _extract_tips_text(page_lines: list[str]) -> Optional[str]:
    """Extract latest trend tip text from news lines."""
    for line in page_lines:
        if "今日油价最新消息" in line:
            return line

    for line in page_lines:
        if "油价调整最新消息" in line:
            return line

    return None


def _extract_trend_text(tips_text: Optional[str]) -> Optional[str]:
    """Extract adjustment trend from the forecast segment in tips text."""
    if not tips_text:
        return None

    normalized = _normalize_text(tips_text)

    # Highest priority: extract from the pricing-cycle forecast segment.
    cycle_match = re.search(
        r"新一轮\d+个工作日统计周期[^。；]{0,120}(?:预计|预期|预测)[^。；]{0,20}油价[^。；，]{0,30}(上涨|上调|上升|下调|下跌|下降|搁浅|不作调整|不做调整|维持)",
        normalized,
    )
    if cycle_match is not None:
        trend = _normalize_trend_token(cycle_match.group(1))
        if trend is not None:
            return trend

    # Prefer the explicit forecast wording (e.g. "预计油价上涨...") to avoid
    # being misled by unrelated "国际油价上涨/下跌" context.
    forecast_patterns = (
        r"(?:预计|预期|预测)[^。；，]{0,20}油价[^。；，]{0,30}(上涨|上调|上升|下调|下跌|下降|搁浅|不作调整|不做调整|维持)",
    )
    for pattern in forecast_patterns:
        match = re.search(pattern, normalized)
        if match is not None:
            trend = _normalize_trend_token(match.group(1))
            if trend is not None:
                return trend

    # Conservative fallback: only parse when adjustment keywords lead the trend term.
    fallback_patterns = (
        r"调价[^。；，]{0,30}(上涨|上调|上升|下调|下跌|下降|搁浅|不作调整|不做调整|维持)",
        r"窗口时间[^。；，]{0,30}(上涨|上调|上升|下调|下跌|下降|搁浅|不作调整|不做调整|维持)",
    )
    for pattern in fallback_patterns:
        match = re.search(pattern, normalized)
        if match is not None:
            trend = _normalize_trend_token(match.group(1))
            if trend is not None:
                return trend

    return None


def _normalize_trend_token(token: str) -> Optional[str]:
    """Normalize trend wording to canonical values."""
    if token in ("下调", "下跌", "下降"):
        return "下调"
    if token in ("搁浅", "不作调整", "不做调整", "维持"):
        return "搁浅"
    if token in ("上调", "上涨", "上升"):
        return "上涨"
    return None


def _extract_next_adjust_at(time_text: Optional[str]) -> Optional[datetime]:
    """Extract an aware datetime for the next adjustment window."""
    if not time_text:
        return None

    match = re.search(
        r"(\d{4}年\d{1,2}月\d{1,2}日)\s*(?:([0-2]?\d)[:：](\d{2})|([0-2]?\d)[点时])?",
        time_text,
    )
    if match is None:
        return None

    date_part = match.group(1)
    hour_minute_hour = match.group(2)
    hour_minute_minute = match.group(3)
    hour_dot = match.group(4)

    if hour_minute_hour is not None:
        hour_text = hour_minute_hour
        minute_text = hour_minute_minute or "00"
    else:
        hour_text = hour_dot or "0"
        minute_text = "00"

    date_match = re.fullmatch(r"(\d{4})年(\d{1,2})月(\d{1,2})日", date_part)
    if date_match is None:
        return None

    tz = dt_util.get_time_zone("Asia/Shanghai") or dt_util.DEFAULT_TIME_ZONE
    year = int(date_match.group(1))
    month = int(date_match.group(2))
    day = int(date_match.group(3))
    hour = int(hour_text)
    minute = int(minute_text)

    try:
        date_obj = datetime(year, month, day, tzinfo=tz)
    except ValueError:
        return None

    if hour == 24 and minute == 0:
        return date_obj + timedelta(days=1)

    if hour >= 24 or minute >= 60:
        return None

    return date_obj.replace(hour=hour, minute=minute)


def _format_adjust_datetime(adjust_at: Optional[datetime]) -> Optional[str]:
    """Format the next adjustment window for display."""
    if adjust_at is None:
        return None

    local = adjust_at.astimezone(
        dt_util.get_time_zone("Asia/Shanghai") or dt_util.DEFAULT_TIME_ZONE
    )
    date_part = f"{local.year}年{local.month}月{local.day}日"
    if local.minute == 0:
        return f"{date_part}{local.hour}点"
    return f"{date_part}{local.hour}:{local.minute:02d}"


