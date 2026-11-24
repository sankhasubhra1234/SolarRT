from datetime import datetime, timezone

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


def test_parse_cloud_time():
    assert parse_cloud_time((FIXTURES / "clouds_caps.xml").read_text(encoding="utf-8")).endswith("Z")
    assert parse_cloud_time("<nope/>") is None


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
