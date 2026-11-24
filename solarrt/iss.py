"""International Space Station position from its published orbit (TLE) using SGP4.

Only the TLE is downloaded (every few hours); positions are computed locally, so the
tracker updates as often as the UI likes without hammering any third-party API.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sgp4.api import Satrec, jday

from .noaa import haversine_km, sun_elevation

ISS_NORAD_ID = 25544
WGS84_A = 6378.137  # km
WGS84_F = 1 / 298.257223563
EARTH_MEAN_RADIUS = 6371.0

# One full orbit of ground track, quoted by the UI and README (P0-2). Keep all three in sync.
TRACK_PAST_MIN = 46
TRACK_FUTURE_MIN = 46
TRACK_STEP_S = 60


@dataclass
class Tle:
    name: str
    line1: str
    line2: str

    @property
    def epoch(self) -> datetime:
        sat = Satrec.twoline2rv(self.line1, self.line2)
        return datetime(2000, 1, 1, tzinfo=timezone.utc) + timedelta(days=sat.jdsatepoch + sat.jdsatepochF - 2451545.0 + 0.5)


def parse_tle(text: str) -> Tle:
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    for i in range(len(lines) - 1):
        if lines[i].startswith("1 ") and lines[i + 1].startswith("2 "):
            name = lines[i - 1] if i > 0 else "ISS"
            Satrec.twoline2rv(lines[i], lines[i + 1])  # validates
            return Tle(name, lines[i], lines[i + 1])
    raise ValueError("No TLE found")


def gmst(jd_ut1: float) -> float:
    """Greenwich mean sidereal time in radians (IAU 1982)."""
    t = (jd_ut1 - 2451545.0) / 36525.0
    sec = 67310.54841 + (876600 * 3600 + 8640184.812866) * t + 0.093104 * t * t - 6.2e-6 * t ** 3
    return math.radians((sec % 86400) / 240.0)


def teme_to_geodetic(r: tuple[float, float, float], jd: float) -> tuple[float, float, float]:
    """TEME position (km) -> geodetic latitude, longitude (deg) and altitude (km)."""
    th = gmst(jd)
    x = math.cos(th) * r[0] + math.sin(th) * r[1]
    y = -math.sin(th) * r[0] + math.cos(th) * r[1]
    z = r[2]
    lon = math.atan2(y, x)
    p = math.hypot(x, y)
    e2 = WGS84_F * (2 - WGS84_F)
    lat = math.atan2(z, p * (1 - e2))
    for _ in range(5):
        n = WGS84_A / math.sqrt(1 - e2 * math.sin(lat) ** 2)
        alt = p / math.cos(lat) - n
        lat = math.atan2(z, p * (1 - e2 * n / (n + alt)))
    n = WGS84_A / math.sqrt(1 - e2 * math.sin(lat) ** 2)
    alt = p / math.cos(lat) - n
    return math.degrees(lat), math.degrees(lon), alt


class IssTracker:
    def __init__(self, tle: Tle) -> None:
        self.tle = tle
        self.sat = Satrec.twoline2rv(tle.line1, tle.line2)

    def position(self, when: datetime) -> dict[str, float]:
        jd, fr = jday(when.year, when.month, when.day, when.hour, when.minute,
                      when.second + when.microsecond / 1e6)
        err, r, v = self.sat.sgp4(jd, fr)
        if err:
            raise ValueError(f"SGP4 propagation error {err}")
        lat, lon, alt = teme_to_geodetic(r, jd + fr)
        speed = math.sqrt(sum(c * c for c in v)) * 3600  # km/h (inertial)
        return {"lat": lat, "lon": lon, "alt_km": alt, "speed_kmh": speed}

    def snapshot(self, now: datetime | None = None, observer: tuple[float, float] | None = None,
                 past_min: int = TRACK_PAST_MIN, future_min: int = TRACK_FUTURE_MIN,
                 step_s: int = TRACK_STEP_S) -> dict[str, Any]:
        now = now or datetime.now(timezone.utc)
        pos = self.position(now)
        # Radius of the area on the ground from which the ISS is above the horizon.
        footprint = EARTH_MEAN_RADIUS * math.acos(EARTH_MEAN_RADIUS / (EARTH_MEAN_RADIUS + pos["alt_km"]))
        track = []
        for s in range(-past_min * 60, future_min * 60 + 1, step_s):
            p = self.position(now + timedelta(seconds=s))
            track.append([round(p["lat"], 3), round(p["lon"], 3), s])
        out: dict[str, Any] = {
            "time": now.isoformat(),
            "lat": round(pos["lat"], 4), "lon": round(pos["lon"], 4),
            "altitude_km": round(pos["alt_km"], 1),
            "speed_kmh": round(pos["speed_kmh"]),
            "footprint_km": round(footprint),
            "sunlit": iss_sunlit(pos["lat"], pos["lon"], pos["alt_km"], now),
            "track": track,  # [lat, lon, seconds from now]
            "tle_epoch": self.tle.epoch.isoformat(),
        }
        if observer:
            d = haversine_km(observer[0], observer[1], pos["lat"], pos["lon"])
            out["observer"] = {"distance_km": round(d), "in_view": d <= footprint}
        return out


def iss_sunlit(lat: float, lon: float, alt_km: float, when: datetime) -> bool:
    """True when the Sun is above the station's own (dipped) horizon."""
    dip = math.degrees(math.acos(EARTH_MEAN_RADIUS / (EARTH_MEAN_RADIUS + alt_km)))
    return sun_elevation(lat, lon, when) > -dip
