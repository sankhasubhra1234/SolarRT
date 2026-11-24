from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from solarrt import api as api_module
from solarrt.config import Settings
from solarrt.weather import parse_cloud_time, sky_quality, summarize_weather
from tests.conftest import FIXTURES, load


def test_sky_quality():
    assert sky_quality(5, 30000) == "Clear"
    assert sky_quality(95, 30000) == "Overcast"
    assert sky_quality(10, 500) == "Fog / poor visibility"
    assert sky_quality(None, None) == "Unknown"


def test_summarize_weather_finds_dark_clear_hour():
    data = {
        "current": {"cloud_cover": 90, "visibility": 20000, "weather_code": 3},
        "hourly": {
            "time": ["2026-01-10T12:00", "2026-01-10T22:00", "2026-01-10T23:00"],
            "cloud_cover": [10, 80, 15],
            "visibility": [30000, 30000, 30000],
            "precipitation_probability": [0, 10, 0],
        },
    }
    now = datetime(2026, 1, 10, 11, 30, tzinfo=timezone.utc)
    s = summarize_weather(data, 57.15, -2.1, now=now)  # Aberdeen: noon is light, 23:00 is dark
    assert s["current"]["sky"] == "Overcast" and s["clear_now"] is False
    assert s["next_dark_clear"].startswith("2026-01-10T23:00")
    assert [h["dark"] for h in s["hourly"]] == [False, True, True]


def test_summarize_weather_converts_local_times_and_reports_timezone():
    # Anchorage is UTC-9: local 14:00 is 23:00 UTC.
    data = {"timezone": "America/Anchorage", "timezone_abbreviation": "AKST", "utc_offset_seconds": -32400,
            "current": {"cloud_cover": 10, "visibility": 30000},
            "hourly": {"time": ["2026-01-10T14:00"], "cloud_cover": [10], "visibility": [30000],
                       "precipitation_probability": [0]}}
    s = summarize_weather(data, 61.2, -149.9, now=datetime(2026, 1, 10, 22, 30, tzinfo=timezone.utc))
    assert s["hourly"][0]["time"].startswith("2026-01-10T23:00")
    assert (s["timezone"], s["timezone_abbreviation"], s["utc_offset_seconds"]) == ("America/Anchorage", "AKST", -32400)


def test_summarize_weather_uses_utc_epochs_across_a_dst_change():
    # Europe/London springs forward at 01:00 UTC on 2026-03-29. With `timeformat=unixtime`
    # Open-Meteo returns UTC epoch seconds, so no per-hour offset maths (which would use the
    # current +01:00 for every row) is needed.
    base = datetime(2026, 3, 29, 0, 0, tzinfo=timezone.utc)
    times = [int((base + timedelta(hours=h)).timestamp()) for h in range(4)]
    data = {
        "timezone": "Europe/London", "timezone_abbreviation": "BST", "utc_offset_seconds": 3600,
        "current": {"cloud_cover": 10, "visibility": 30000},
        "hourly": {"time": times, "cloud_cover": [10] * 4, "visibility": [30000] * 4,
                   "precipitation_probability": [0] * 4},
    }
    s = summarize_weather(data, 51.5, -0.12, now=base)
    assert [h["time"][11:16] for h in s["hourly"]] == ["00:00", "01:00", "02:00", "03:00"]
    assert s["hourly"][0]["time"].startswith("2026-03-29T00:00")


def test_parse_cloud_time():
    assert parse_cloud_time((FIXTURES / "clouds_caps.xml").read_text(encoding="utf-8")).endswith("Z")
    assert parse_cloud_time("<nope/>") is None


@pytest.mark.parametrize("xml", [
    '<Dimension name="time" default="2026-11-17T09:00:00Z" units="ISO8601"/>',
    '<Dimension default="2026-11-17T09:00:00Z" units="ISO8601" name="time"/>',
    "<Dimension name='time' default='2026-11-17T09:00:00Z'/>",
    '<WMS><Dimension name="time" default="T"/></WMS>',
    # Malformed surrounding XML: ElementTree fails, the regex fallback still finds the tag.
    '<WMS><Dimension name="time" default="T"></WMS>',
])
def test_parse_cloud_time_attribute_order_and_fallback(xml):
    assert parse_cloud_time(xml) in {"2026-11-17T09:00:00Z", "T"}


def test_parse_cloud_time_missing_or_broken_dimension():
    assert parse_cloud_time('<WMS><Dimension name="elevation" default="10"/></WMS>') is None
    assert parse_cloud_time("<WMS><Dimension") is None


def test_weather_api(client):
    d = client.get("/api/weather", params={"lat": 57.15, "lon": -2.1}).json()
    assert {"current", "hourly", "dark_now", "clear_now", "next_dark_clear"} <= d.keys()
    assert d["current"]["cloud"] == load("weather.json")["current"]["cloud_cover"]


def test_clouds_api(client):
    d = client.get("/api/clouds").json()
    assert d["layer"] and d["time"]


def test_feedback_roundtrip(client):
    r = client.post("/api/feedback", json={"rating": 5, "comment": "  Lovely aurora map! ", "edition": "web"})
    assert r.status_code == 201
    assert client.get("/api/feedback").status_code == 403
    assert client.get("/api/feedback", params={"token": "secret"}).status_code == 403  # never via URL
    assert client.get("/api/feedback", headers={"Authorization": "Bearer wrong"}).status_code == 403
    s = client.get("/api/feedback", headers={"Authorization": "Bearer secret"}).json()
    assert s["count"] == 1 and s["average"] == 5
    assert s["entries"][0]["comment"] == "Lovely aurora map!" and s["entries"][0]["rating_label"] == "Love it"


def test_feedback_validation_and_rate_limit(client):
    assert client.post("/api/feedback", json={"rating": 9}).status_code == 422
    assert client.post("/api/feedback", json={"rating": 3, "comment": "x" * 3000}).status_code == 422
    codes = [client.post("/api/feedback", json={"rating": 4}).status_code for _ in range(6)]
    assert codes[:5] == [201] * 5 and codes[5] == 429


def test_feedback_forwarding_is_single_hop(monkeypatch, tmp_path):
    forward_url = "https://forward.example/api/feedback"
    forwarded: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == forward_url
        forwarded.append(request)
        return httpx.Response(201, json={"ok": True})

    monkeypatch.setattr(api_module, "settings", Settings(feedback_forward_url=forward_url))
    with TestClient(api_module.create_app(transport=httpx.MockTransport(handler),
                                          data_dir=str(tmp_path))) as c:
        r = c.post("/api/feedback", json={"rating": 5})
        assert r.status_code == 201 and r.json()["forwarded"] is True
        assert len(forwarded) == 1
        assert forwarded[0].headers["x-solarrt-forwarded"] == "1"

        # A request that arrives already forwarded is stored but never sent on again.
        r = c.post("/api/feedback", json={"rating": 4},
                   headers={"X-SolarRT-Forwarded": "1"})
        assert r.status_code == 201 and r.json()["forwarded"] is False
        assert len(forwarded) == 1

