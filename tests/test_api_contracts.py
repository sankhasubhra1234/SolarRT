"""Lightweight snapshot tests for API response contract stability.

These tests verify that every endpoint returns the expected key set and
that types are consistent. They serve as a safety net against invisible
shape changes that would break the distributed Android app (P1-8).
"""


from fastapi.testclient import TestClient

from solarrt import api as api_module
from tests.conftest import fake_noaa


def test_health_contract():
    """/api/health returns status, app, version, edition."""
    with TestClient(api_module.create_app(transport=fake_noaa())) as c:
        d = c.get("/api/health").json()
        assert {"status", "app", "version", "edition"} <= d.keys()
        assert d["status"] == "ok"


def test_kp_contract():
    """/api/kp returns expected fields with correct types."""
    with TestClient(api_module.create_app(transport=fake_noaa())) as c:
        d = c.get("/api/kp").json()
        # Top-level keys
        assert {"stale", "age_seconds", "current", "series", "max_24h",
                "forecast_peak_24h", "last_3h", "source"} <= d.keys()
        # current sub-dict
        cur = d["current"]
        assert {"g_label", "kp", "label", "g", "activity"} <= cur.keys()
        # age_seconds is a non-negative number
        assert isinstance(d["age_seconds"], (int, float))
        assert d["age_seconds"] >= 0


def test_aurora_contract():
    """/api/aurora returns expected fields."""
    with TestClient(api_module.create_app(transport=fake_noaa())) as c:
        d = c.get("/api/aurora").json()
        assert {"observation_time", "forecast_time", "width", "height",
                "encoding", "data", "hemisphere_max", "stale", "age_seconds"} <= d.keys()
        assert isinstance(d["age_seconds"], (int, float))
        assert d["width"] == 360 and d["height"] == 181


def test_regions_contract():
    """/api/regions returns expected fields."""
    with TestClient(api_module.create_app(transport=fake_noaa())) as c:
        d = c.get("/api/regions").json()
        assert {"forecast_time", "regions", "stale", "age_seconds"} <= d.keys()
        assert isinstance(d["age_seconds"], (int, float))
        assert len(d["regions"]) > 0


def test_location_contract():
    """/api/location returns expected fields."""
    with TestClient(api_module.create_app(transport=fake_noaa())) as c:
        d = c.get("/api/location", params={"lat": 64.84, "lon": -147.72}).json()
        assert {"lat", "lon", "probability", "level", "chance", "verdict",
                "sky", "nearby", "sun_elevation", "stale", "age_seconds"} <= d.keys()
        assert isinstance(d["age_seconds"], (int, float))
        assert d["probability"] >= 0


def test_iss_contract():
    """/api/iss returns expected fields."""
    with TestClient(api_module.create_app(transport=fake_noaa())) as c:
        d = c.get("/api/iss").json()
        assert {"lat", "lon", "altitude_km", "track", "sunlit", "stale", "age_seconds"} <= d.keys()
        assert isinstance(d["age_seconds"], (int, float))


def test_weather_contract():
    """/api/weather returns expected fields."""
    with TestClient(api_module.create_app(transport=fake_noaa())) as c:
        d = c.get("/api/weather", params={"lat": 57.15, "lon": -2.1}).json()
        assert {"lat", "lon", "current", "hourly", "dark_now", "clear_now",
                "next_dark_clear", "timezone", "timezone_abbreviation",
                "utc_offset_seconds", "stale", "age_seconds"} <= d.keys()
        assert isinstance(d["age_seconds"], (int, float))
        # stale data should have non-negative age
        assert d["age_seconds"] >= 0


def test_clouds_contract():
    """/api/clouds returns expected fields."""
    with TestClient(api_module.create_app(transport=fake_noaa())) as c:
        d = c.get("/api/clouds").json()
        assert {"wms_url", "layer", "time", "stale", "age_seconds"} <= d.keys()
        assert isinstance(d["age_seconds"], (int, float))