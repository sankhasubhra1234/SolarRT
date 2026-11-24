"""Central configuration. Values can be overridden with SOLARRT_* environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

from . import APP_NAME, __version__

NOAA_BASE = "https://services.swpc.noaa.gov"


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    # NOAA SWPC data feeds
    kp_3h_url: str = f"{NOAA_BASE}/products/noaa-planetary-k-index.json"
    kp_forecast_url: str = f"{NOAA_BASE}/products/noaa-planetary-k-index-forecast.json"
    kp_1m_url: str = f"{NOAA_BASE}/json/planetary_k_index_1m.json"
    ovation_url: str = f"{NOAA_BASE}/json/ovation_aurora_latest.json"

    # ISS orbital elements (TLE); positions are computed locally with SGP4
    iss_tle_urls: tuple[str, ...] = (
        "https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=TLE",
        "https://api.wheretheiss.at/v1/satellites/25544/tles?format=text",
    )
    ttl_iss_tle: int = 6 * 3600

    # Weather at a location (Open-Meteo, free, no key) and the global cloud map (EUMETSAT)
    open_meteo_url: str = "https://api.open-meteo.com/v1/forecast"
    cloud_wms_url: str = "https://view.eumetsat.int/geoserver/ows"
    cloud_layer: str = "mumi:worldcloudmap_ir108"
    cloud_caps_url: str = ("https://view.eumetsat.int/geoserver/mumi/worldcloudmap_ir108/ows"
                           "?service=WMS&version=1.3.0&request=GetCapabilities")
    ttl_weather: int = 600
    ttl_clouds: int = 900

    # Feedback storage. Desktop builds set SOLARRT_DATA_DIR to %LOCALAPPDATA%\SolarRT.
    data_dir: str = os.environ.get("SOLARRT_DATA_DIR", "data")
    # Optional: also forward feedback to another SolarRT server (e.g. the hosted website).
    feedback_forward_url: str = os.environ.get("SOLARRT_FEEDBACK_FORWARD_URL", "")
    # Token required to read feedback via GET /api/feedback (disabled when empty).
    admin_token: str = os.environ.get("SOLARRT_ADMIN_TOKEN", "")

    # ---- security
    # Host names this server answers to (comma-separated), e.g. "solarrt.example.com".
    # "*" accepts any (development). The desktop app sets "127.0.0.1,localhost".
    allowed_hosts: tuple[str, ...] = tuple(
        h.strip() for h in os.environ.get("SOLARRT_ALLOWED_HOSTS", "*").split(",") if h.strip())
    # Interactive API docs at /docs (turn off in production with SOLARRT_ENABLE_DOCS=0)
    enable_docs: bool = os.environ.get("SOLARRT_ENABLE_DOCS", "1") not in ("0", "false", "no")
    # Requests per minute per client: whole API / place search (OpenStreetMap is shared & strict)
    rate_limit_api: int = _env_int("SOLARRT_RATE_LIMIT_API", 240)
    rate_limit_search: int = _env_int("SOLARRT_RATE_LIMIT_SEARCH", 20)
    # Largest feedback file before new entries are refused (protects the disk)
    feedback_max_bytes: int = _env_int("SOLARRT_FEEDBACK_MAX_BYTES", 20 * 1024 * 1024)

    # Geocoding (place search) — OpenStreetMap Nominatim
    nominatim_url: str = "https://nominatim.openstreetmap.org"

    # Cache lifetimes in seconds (NOAA updates: 1m Kp every minute, OVATION ~5 min)
    ttl_kp_1m: int = _env_int("SOLARRT_TTL_KP_1M", 60)
    ttl_kp_3h: int = _env_int("SOLARRT_TTL_KP_3H", 600)
    ttl_ovation: int = _env_int("SOLARRT_TTL_OVATION", 300)
    ttl_geocode: int = 24 * 3600

    http_timeout: float = 20.0
    user_agent: str = f"{APP_NAME}/{__version__} (aurora monitor)"

    host: str = os.environ.get("SOLARRT_HOST", "127.0.0.1")
    port: int = _env_int("SOLARRT_PORT", 8000)


settings = Settings()
