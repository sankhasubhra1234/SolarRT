import base64
import time

import httpx
from fastapi.testclient import TestClient

from solarrt import api as api_module
from solarrt.api import create_app
from solarrt.config import Settings, settings
from solarrt.regions import REGIONS
from tests.conftest import ROUTES, fake_noaa, load


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_index_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "SolarRT" in r.text
    js = client.get("/static/app.js")
    assert js.status_code == 200 and js.headers["cache-control"] == "no-cache"
    assert r.headers["cache-control"] == "no-cache"


def test_kp(client):
    d = client.get("/api/kp").json()
    assert d["current"]["g_label"].startswith("G")
    assert d["series"] and d["stale"] is False


def test_aurora_grid(client):
    d = client.get("/api/aurora").json()
    assert len(base64.b64decode(d["data"])) == d["width"] * d["height"] == 360 * 181


def test_regions(client):
    regions = client.get("/api/regions").json()["regions"]
    assert len(regions) == len(REGIONS)
    assert regions == sorted(regions, key=lambda r: (-r["max"], -r["coverage"]))


def test_location(client):
    d = client.get("/api/location", params={"lat": 64.84, "lon": -147.72}).json()
    assert 0 <= d["probability"] <= 100
    assert d["chance"] in {"none", "low", "moderate", "high"}
    assert d["sky"] and d["verdict"]


def test_location_validates_input(client):
    assert client.get("/api/location", params={"lat": 120, "lon": 0}).status_code == 422


def test_geocode_and_reverse(client):
    assert client.get("/api/geocode", params={"q": "Tromso"}).json()["results"][0]["lat"] == 69.65
    assert client.get("/api/reverse", params={"lat": 69.6, "lon": 18.9}).json()["name"] == "Tromsø, Norway"


def test_noaa_down_returns_503():
    with TestClient(create_app(transport=fake_noaa(fail={settings.ovation_url}))) as c:
        r = c.get("/api/aurora")
        assert r.status_code == 503 and "unavailable" in r.json()["detail"]


def test_kp_marks_stale_data_and_reports_age(monkeypatch, tmp_path):
    state = {"fail": False}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url).split("?")[0]
        if state["fail"]:
            return httpx.Response(502)
        return httpx.Response(200, json=load(ROUTES[url]))

    # Zero TTLs make the second request attempt a refresh, which then fails.
    monkeypatch.setattr(api_module, "settings",
                        Settings(ttl_kp_1m=0, ttl_kp_3h=0, ttl_ovation=0))
    with TestClient(api_module.create_app(transport=httpx.MockTransport(handler),
                                          data_dir=str(tmp_path))) as c:
        first = c.get("/api/kp").json()
        assert first["stale"] is False and first["age_seconds"] == 0

        state["fail"] = True
        time.sleep(0.05)
        second = c.get("/api/kp").json()
        assert second["stale"] is True
        assert second["age_seconds"] > 0
        assert second["current"]["kp"] == first["current"]["kp"]


def test_weather_503_hides_coordinates_and_blames_the_right_service():
    with TestClient(create_app(transport=fake_noaa(fail={settings.open_meteo_url}))) as c:
        r = c.get("/api/weather", params={"lat": 57.1234, "lon": -2.5678})
        assert r.status_code == 503
        body = r.text
        assert "57.12" not in body and "-2.5" not in body
        assert "NOAA" not in body
        assert "Weather" in r.json()["detail"]

