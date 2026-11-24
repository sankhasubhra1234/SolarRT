"""Fetching and parsing NOAA SWPC space-weather data.

The parse_* functions are pure (JSON in, plain objects out) so they can be unit-tested
against saved fixtures; fetching is done with a shared httpx.AsyncClient.
"""

from __future__ import annotations

import base64
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from .config import settings

GRID_W, GRID_H = 360, 181  # OVATION grid: lon 0..359, lat -90..90, 1 degree steps
EARTH_RADIUS_KM = 6371.0
KP_SLOT = timedelta(hours=3)  # Kp is reported per 3-hour UTC slot


# --------------------------------------------------------------------------- Kp helpers

def parse_time(tag: str) -> datetime:
    """NOAA time tags look like '2026-11-17T01:33:00' or '...Z'; all are UTC."""
    return datetime.fromisoformat(tag.replace("Z", "")).replace(tzinfo=timezone.utc)


def g_scale(kp: float) -> int:
    """NOAA G-scale level (0-5). Kp 5- (4.67) is already G1, so round thirds first."""
    return max(0, min(5, math.floor(kp + 0.34) - 4))


G_LABELS = ["G0 Quiet", "G1 Minor", "G2 Moderate", "G3 Strong", "G4 Severe", "G5 Extreme"]


def kp_label(kp: float) -> str:
    """Express a decimal Kp in the traditional thirds notation: 4.67 -> '5-', 5.0 -> '5o'."""
    n = round(kp)
    diff = kp - n
    if diff < -0.15:
        return f"{n}-"
    if diff > 0.15:
        return f"{n}+"
    return f"{n}o"


def kp_activity(kp: float) -> str:
    if kp >= 5:
        return "Storm"
    if kp >= 4:
        return "Active"
    if kp >= 3:
        return "Unsettled"
    return "Quiet"


@dataclass
class KpPoint:
    time: datetime
    kp: float
    kind: str  # observed | estimated | predicted

    def to_dict(self) -> dict[str, Any]:
        return {"time": self.time.isoformat(), "kp": round(self.kp, 2), "kind": self.kind,
                "g": g_scale(self.kp)}


def _num(value: Any) -> float | None:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def parse_kp_3h(data: Any) -> list[KpPoint]:
    """products/noaa-planetary-k-index.json. Accepts both the current list-of-objects
    format and the legacy list-of-rows format (first row = header)."""
    points: list[KpPoint] = []
    if not isinstance(data, list):
        return points
    for row in data:
        try:
            if isinstance(row, dict):
                tag, kp = row.get("time_tag"), _num(row.get("Kp", row.get("kp")))
            elif isinstance(row, list) and len(row) >= 2:
                tag, kp = row[0], _num(row[1])
            else:
                continue
            if tag and kp is not None:
                points.append(KpPoint(parse_time(str(tag)), kp, "observed"))
        except ValueError:
            continue  # header row or malformed timestamp
    points.sort(key=lambda p: p.time)
    return points


def parse_kp_forecast(data: Any) -> list[KpPoint]:
    """products/noaa-planetary-k-index-forecast.json: observed + estimated + predicted."""
    points: list[KpPoint] = []
    if not isinstance(data, list):
        return points
    for row in data:
        try:
            if isinstance(row, dict):
                tag, kp, kind = row.get("time_tag"), _num(row.get("kp")), row.get("observed")
            elif isinstance(row, list) and len(row) >= 3:
                tag, kp, kind = row[0], _num(row[1]), row[2]
            else:
                continue
            if tag and kp is not None:
                points.append(KpPoint(parse_time(str(tag)), kp, str(kind or "predicted")))
        except ValueError:
            continue
    points.sort(key=lambda p: p.time)
    return points


def parse_kp_1m(data: Any) -> KpPoint | None:
    """json/planetary_k_index_1m.json: latest minute-resolution Kp estimate."""
    if not isinstance(data, list):
        return None
    for row in reversed(data):
        if not isinstance(row, dict):
            continue
        kp = _num(row.get("estimated_kp", row.get("kp_index")))
        tag = row.get("time_tag")
        if kp is not None and tag:
            try:
                return KpPoint(parse_time(str(tag)), kp, "estimated")
            except ValueError:
                continue
    return None


def build_kp_summary(now_1m: KpPoint | None, history: list[KpPoint],
                     forecast: list[KpPoint], now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    # NOAA marks the rest of *today's* 3-hour slots as "estimated" even when they lie in the
    # future, so re-label by time: started slots are estimates, future slots are forecasts.
    forecast = [p if p.kind == "observed" else
                KpPoint(p.time, p.kp, "estimated" if p.time <= now else "predicted")
                for p in forecast]
    current = now_1m or (history[-1] if history else None)
    last_obs = history[-1] if history else None
    past_24h = [p.kp for p in history if (now - p.time).total_seconds() <= 24 * 3600]
    upcoming = [p for p in forecast if p.kind != "observed" and p.time + KP_SLOT > now]
    next_24h = [p for p in upcoming if (p.time - now).total_seconds() <= 24 * 3600]
    peak = max(next_24h, key=lambda p: p.kp) if next_24h else None

    def describe(p: KpPoint | None) -> dict[str, Any] | None:
        if p is None:
            return None
        g = g_scale(p.kp)
        return {**p.to_dict(), "label": kp_label(p.kp), "g_label": G_LABELS[g],
                "activity": kp_activity(p.kp)}

    # Chart series: observed history from the forecast product (it includes the last week),
    # falling back to the 3-hour product, then predictions.
    series = [p.to_dict() for p in forecast] or [p.to_dict() for p in history]
    return {
        "current": describe(current),
        "last_3h": describe(last_obs),
        "max_24h": round(max(past_24h), 2) if past_24h else None,
        "forecast_peak_24h": describe(peak),
        "series": series,
    }


# --------------------------------------------------------------------------- OVATION aurora

@dataclass
class AuroraGrid:
    observation_time: datetime | None
    forecast_time: datetime | None
    values: bytearray = field(repr=False)  # index = (lat + 90) * 360 + lon, value 0..100

    def at_cell(self, lat_i: int, lon_i: int) -> int:
        lat_i = max(0, min(GRID_H - 1, lat_i))
        return self.values[lat_i * GRID_W + (lon_i % GRID_W)]

    def value(self, lat: float, lon: float) -> float:
        """Bilinearly interpolated aurora probability (%) at a point."""
        lon = lon % 360
        y = max(0.0, min(GRID_H - 1.0, lat + 90))
        x0, y0 = int(math.floor(lon)), int(math.floor(y))
        fx, fy = lon - x0, y - y0
        y1 = min(y0 + 1, GRID_H - 1)
        v00, v10 = self.at_cell(y0, x0), self.at_cell(y0, x0 + 1)
        v01, v11 = self.at_cell(y1, x0), self.at_cell(y1, x0 + 1)
        top = v00 * (1 - fx) + v10 * fx
        bottom = v01 * (1 - fx) + v11 * fx
        return top * (1 - fy) + bottom * fy

    def max_within(self, lat: float, lon: float, radius_km: float) -> tuple[int, float, float]:
        """Highest probability of any grid cell within radius_km. Returns (value, lat, lon)."""
        best = (0, lat, lon)
        dlat = math.ceil(radius_km / 111.0)
        for la in range(math.floor(lat) - dlat, math.ceil(lat) + dlat + 1):
            if la < -90 or la > 90:
                continue
            cos_la = max(math.cos(math.radians(la)), 0.01)
            dlon = min(180, math.ceil(radius_km / (111.0 * cos_la)))
            for lo in range(math.floor(lon) - dlon, math.ceil(lon) + dlon + 1):
                v = self.at_cell(la + 90, lo)
                if v > best[0] and haversine_km(lat, lon, la, lo) <= radius_km:
                    best = (v, float(la), float(((lo + 180) % 360) - 180))
        return best

    def encoded(self) -> str:
        return base64.b64encode(bytes(self.values)).decode("ascii")

    def hemisphere_max(self) -> dict[str, int]:
        half = (GRID_H // 2) * GRID_W
        return {"south": max(self.values[:half]), "north": max(self.values[half + GRID_W:])}


def parse_ovation(data: Any) -> AuroraGrid:
    if not isinstance(data, dict) or not isinstance(data.get("coordinates"), list):
        raise ValueError("Unexpected OVATION format")
    values = bytearray(GRID_W * GRID_H)
    for item in data["coordinates"]:
        try:
            lon, lat, val = int(item[0]), int(item[1]), item[2]
        except (TypeError, ValueError, IndexError):
            continue
        if -90 <= lat <= 90:
            values[(lat + 90) * GRID_W + (lon % GRID_W)] = max(0, min(100, int(round(val))))

    def t(key: str) -> datetime | None:
        try:
            return parse_time(str(data[key]))
        except (KeyError, ValueError):
            return None

    return AuroraGrid(t("Observation Time"), t("Forecast Time"), values)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


# --------------------------------------------------------------------------- Sun position

def sun_elevation(lat: float, lon: float, when: datetime | None = None) -> float:
    """Approximate solar elevation angle in degrees (NOAA low-precision algorithm, ~0.5°)."""
    when = when or datetime.now(timezone.utc)
    day = when.timetuple().tm_yday
    hour = when.hour + when.minute / 60 + when.second / 3600
    g = 2 * math.pi / 365 * (day - 1 + (hour - 12) / 24)
    decl = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g)
            - 0.006758 * math.cos(2 * g) + 0.000907 * math.sin(2 * g)
            - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    eqtime = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g)
                       - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    tst = hour * 60 + eqtime + 4 * lon  # true solar time, minutes
    ha = math.radians(tst / 4 - 180)
    phi = math.radians(lat)
    cos_zen = math.sin(phi) * math.sin(decl) + math.cos(phi) * math.cos(decl) * math.cos(ha)
    return 90 - math.degrees(math.acos(max(-1.0, min(1.0, cos_zen))))


def sky_darkness(elevation: float) -> str:
    if elevation > 0:
        return "Daylight"
    if elevation > -6:
        return "Civil twilight"
    if elevation > -12:
        return "Nautical twilight"
    if elevation > -18:
        return "Astronomical twilight"
    return "Dark"


# --------------------------------------------------------------------------- Fetching

class NoaaClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def _json(self, url: str) -> Any:
        r = await self.client.get(url, timeout=settings.http_timeout)
        r.raise_for_status()
        return r.json()

    async def kp_3h(self) -> list[KpPoint]:
        return parse_kp_3h(await self._json(settings.kp_3h_url))

    async def kp_forecast(self) -> list[KpPoint]:
        return parse_kp_forecast(await self._json(settings.kp_forecast_url))

    async def kp_1m(self) -> KpPoint | None:
        return parse_kp_1m(await self._json(settings.kp_1m_url))

    async def ovation(self) -> AuroraGrid:
        return parse_ovation(await self._json(settings.ovation_url))
