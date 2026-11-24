import base64

from fastapi.testclient import TestClient

from solarrt.api import create_app
from solarrt.config import settings
from solarrt.regions import REGIONS
from tests.conftest import fake_noaa


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
