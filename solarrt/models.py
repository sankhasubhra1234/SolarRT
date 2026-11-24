"""Pydantic response models for SolarRT API endpoints.

These models ensure consistent response shapes and enable OpenAPI schema generation.
They are the single source of truth for API response models; endpoint handlers should
construct and return pydantic model instances rather than raw dicts.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

# --- Health ---

class HealthResponse(BaseModel):
    status: str = "ok"
    app: str = "SolarRT"
    version: str
    edition: str = "web"


# --- Kp ---

class KpCurrent(BaseModel):
    kp: float = Field(..., ge=0, le=9)
    label: str
    g_label: str
    g: int
    activity: str


class KpSeriesItem(BaseModel):
    time: datetime
    kp: float
    kind: str  # observed | estimated | predicted
    g: int | None = None
    label: str | None = None


class KpSummaryResponse(BaseModel):
    current: KpCurrent
    stale: bool
    age_seconds: float = 0.0
    max_24h: float | None = None
    forecast_peak_24h: KpCurrent | None = None
    last_3h: KpCurrent | None = None
    series: list[KpSeriesItem]


# --- Aurora ---

class AuroraResponse(BaseModel):
    observation_time: datetime | None = None
    forecast_time: datetime | None = None
    width: int = 360
    height: int = 181
    encoding: str = "base64 uint8, row = latitude -90..90, column = longitude 0..359"
    data: str  # base64 encoded
    hemisphere_max: dict[str, int]
    stale: bool
    age_seconds: float = 0.0


# --- Regions ---

class RegionItem(BaseModel):
    id: str
    name: str
    hemisphere: str  # north | south
    max: int
    coverage: float  # 0..100 %
    level: str  # Very high | High | Moderate | Low | None
    bounds: list[list[int]]  # [[south, west], [north, east]]


class RegionsResponse(BaseModel):
    forecast_time: datetime | None = None
    regions: list[RegionItem]
    stale: bool
    age_seconds: float = 0.0


# --- Location ---

class NearbyItem(BaseModel):
    max: int | None = None
    lat: float | None = None
    lon: float | None = None
    distance_km: float | None = None
    radius_km: int = 800


class LocationResponse(BaseModel):
    lat: float
    lon: float
    probability: float  # 0..100
    level: str
    chance: str
    verdict: str
    sky: str | None = None
    nearby: NearbyItem
    sun_elevation: float
    kp: KpCurrent | None = None
    forecast_time: datetime | None = None
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    stale: bool
    age_seconds: float = 0.0


# --- ISS ---

class IssObserver(BaseModel):
    distance_km: float
    in_view: bool


class IssSnapshotResponse(BaseModel):
    time: str
    lat: float
    lon: float
    altitude_km: float
    speed_kmh: int
    footprint_km: float
    sunlit: bool
    track: list[list[float]]  # [lat, lon, seconds_from_now]
    tle_epoch: str
    observer: IssObserver | None = None


# --- Weather ---

class WeatherCurrent(BaseModel):
    cloud: int | None = None
    cloud_low: int | None = None
    cloud_mid: int | None = None
    cloud_high: int | None = None
    visibility: float | None = None  # meters
    precipitation: float | None = None
    temperature: float | None = None
    condition: str = "—"
    sky: str | None = None


class WeatherHourly(BaseModel):
    time: str  # ISO format UTC
    cloud: int | None = None
    visibility: float | None = None  # meters
    precip_prob: float | None = None  # 0..100
    dark: bool  # nautical twilight or darker


class WeatherResponse(BaseModel):
    lat: float
    lon: float
    current: WeatherCurrent
    darkness: str
    dark_now: bool
    clear_now: bool
    next_dark_clear: str | None = None
    hourly: list[WeatherHourly]
    timezone: str  # IANA name, e.g. "America/Anchorage"
    timezone_abbreviation: str  # e.g. "AKST"
    utc_offset_seconds: int
    source: str = "Open-Meteo"


# --- Clouds ---

class CloudsResponse(BaseModel):
    wms_url: str
    layer: str
    time: str | None = None
    stale: bool = False
    age_seconds: float = 0.0
    attribution: str = "Clouds © EUMETSAT (geostationary IR 10.8 µm composite)"


# --- ISS Passes ---

class IssPass(BaseModel):
    start: str  # ISO datetime
    peak: str  # ISO datetime
    end: str  # ISO datetime
    max_elevation: float  # degrees
    azimuth: float  # degrees
    duration: float  # minutes
    brightness_hint: str  # e.g. "bright", "dim", "very dim"
    tle_epoch: str


# --- Geocode/Reverse ---

class GeocodeResult(BaseModel):
    name: str
    lat: float
    lon: float


class ReverseResult(BaseModel):
    name: str | None = None


# --- Feedback ---

class FeedbackResponse(BaseModel):
    id: str
    time: str
    rating: int
    rating_label: str
    comment: str
    contact: str
    edition: str
    version: str


# --- API Versioning ---

API_VERSION = "v1"


def api_version_path():
    """Return the versioned API prefix."""
    return f"/api/{API_VERSION}"