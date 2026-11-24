"""Local weather for aurora viewing (Open-Meteo) and the global cloud-map timestamp."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

import defusedxml
import defusedxml.ElementTree as ET

defusedxml.defuse_stdlib()

from .noaa import sky_darkness, sun_elevation

CURRENT_FIELDS = ("cloud_cover,cloud_cover_low,cloud_cover_mid,cloud_cover_high,visibility,"
                  "precipitation,weather_code,temperature_2m,is_day")
HOURLY_FIELDS = "cloud_cover,visibility,precipitation_probability"

# WMO weather codes (subset, grouped) used by Open-Meteo
WMO = {0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast", 45: "Fog", 48: "Rime fog",
       51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle", 56: "Freezing drizzle", 57: "Freezing drizzle",
       61: "Light rain", 63: "Rain", 65: "Heavy rain", 66: "Freezing rain", 67: "Freezing rain",
       71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains", 80: "Rain showers",
       81: "Rain showers", 82: "Violent rain showers", 85: "Snow showers", 86: "Snow showers",
       95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with hail"}

CLEAR_MAX_CLOUD = 30      # % cloud cover regarded as "clear enough" by default
GOOD_VISIBILITY_M = 10_000


def sky_quality(cloud: float | None, visibility_m: float | None) -> str:
    if cloud is None:
        return "Unknown"
    if visibility_m is not None and visibility_m < 2000:
        return "Fog / poor visibility"
    if cloud < 20:
        return "Clear"
    if cloud < 50:
        return "Partly cloudy"
    if cloud < 85:
        return "Mostly cloudy"
    return "Overcast"


def summarize_weather(data: dict[str, Any], lat: float, lon: float,
                      now: datetime | None = None) -> dict[str, Any]:
    """Turn an Open-Meteo response (requested with timezone=auto) into what the aurora UI needs."""
    now = now or datetime.now(timezone.utc)
    cur = data.get("current") or {}
    cloud, vis = cur.get("cloud_cover"), cur.get("visibility")

    # Open-Meteo is asked for the location's own time zone (for its label) and, since P0-4,
    # for ``timeformat=unixtime``: hourly times are then unambiguous UTC epoch seconds. Older
    # cached payloads (and the saved fixtures) may still hold local wall-clock ISO strings, so
    # accept both. Converting every ISO hour with one current offset was the DST bug.
    offset = timedelta(seconds=int(data.get("utc_offset_seconds") or 0))
    hourly = data.get("hourly") or {}
    hours = []
    for i, t in enumerate(hourly.get("time") or []):
        when = _hour_time(t, offset)
        if when is None or when + timedelta(hours=1) <= now:
            continue
        elev = sun_elevation(lat, lon, when)
        hours.append({
            "time": when.isoformat(),
            "cloud": _at(hourly, "cloud_cover", i),
            "visibility": _at(hourly, "visibility", i),
            "precip_prob": _at(hourly, "precipitation_probability", i),
            "dark": elev <= -12,  # nautical twilight or darker: faint aurora visible
        })
        if len(hours) >= 24:
            break

    # First hour in the coming day that is dark AND clear enough.
    best = next((h for h in hours if h["dark"] and h["cloud"] is not None
                 and h["cloud"] <= CLEAR_MAX_CLOUD
                 and (h["visibility"] is None or h["visibility"] >= GOOD_VISIBILITY_M)), None)
    elev_now = sun_elevation(lat, lon, now)
    return {
        "lat": lat, "lon": lon,
        "current": {
            "cloud": cloud,
            "cloud_low": cur.get("cloud_cover_low"),
            "cloud_mid": cur.get("cloud_cover_mid"),
            "cloud_high": cur.get("cloud_cover_high"),
            "visibility": vis,
            "precipitation": cur.get("precipitation"),
            "temperature": cur.get("temperature_2m"),
            "condition": WMO.get(cur.get("weather_code", -1), "—"),
            "sky": sky_quality(cloud, vis),
        },
        "darkness": sky_darkness(elev_now),
        "dark_now": elev_now <= -12,
        "clear_now": cloud is not None and cloud <= CLEAR_MAX_CLOUD
                     and (vis is None or vis >= GOOD_VISIBILITY_M),
        "next_dark_clear": best["time"] if best else None,
        "hourly": hours,
        # Time zone of the location (IANA name, e.g. "America/Anchorage") for local-time display
        "timezone": data.get("timezone") or "UTC",
        "timezone_abbreviation": data.get("timezone_abbreviation") or "UTC",
        "utc_offset_seconds": int(offset.total_seconds()),
        "source": "Open-Meteo",
    }


def _at(block: dict[str, Any], key: str, i: int):
    values = block.get(key) or []
    return values[i] if i < len(values) else None


def _hour_time(value: Any, offset: timedelta) -> datetime | None:
    """Turn an Open-Meteo hourly time into an aware UTC datetime.

    Epoch seconds (``timeformat=unixtime``) are used directly. ISO wall-clock strings from
    older payloads are interpreted with the supplied offset as a fallback.
    """
    if value is None or isinstance(value, bool):
        return None
    # Numeric epoch seconds, either as a JSON number or a numeric string.
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), timezone.utc)
        except (ValueError, OverflowError, OSError):
            return None
    text = str(value).strip()
    try:
        return datetime.fromtimestamp(float(text), timezone.utc)
    except (ValueError, OverflowError, OSError):
        pass
    try:
        return (datetime.fromisoformat(text) - offset).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def parse_cloud_time(caps_xml: str) -> str | None:
    """Latest image time from the EUMETSAT WMS capabilities document.

    Parsed with ElementTree so attribute order and quoting do not matter; a small regex
    fallback keeps working if the document is not well-formed XML.
    """
    try:
        root = ET.fromstring(caps_xml)
    except ET.ParseError:
        root = None
    if root is not None:
        for el in root.iter():
            if el.tag.rsplit("}", 1)[-1] == "Dimension" and el.get("name") == "time":
                default = el.get("default")
                if default:
                    return default
        return None
    # Fallback: find the Dimension tag, then its default attribute in either order.
    tag = re.search(r'<Dimension\b[^>]*\bname=["\']time["\'][^>]*>', caps_xml)
    if tag:
        m = re.search(r'\bdefault=["\']([^"\']+)["\']', tag.group(0))
        if m:
            return m.group(1)
    return None
