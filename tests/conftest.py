import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from solarrt.api import create_app
from solarrt.config import settings

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


ROUTES = {
    settings.kp_3h_url: "kp_3h.json",
    settings.kp_forecast_url: "kp_forecast.json",
    settings.kp_1m_url: "kp_1m.json",
    settings.ovation_url: "ovation.json",
}


def fake_noaa(fail: set[str] | None = None):
    """httpx MockTransport serving saved NOAA responses (no network in tests)."""
    fail = fail or set()

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url).split("?")[0]
        if url in fail:
            return httpx.Response(502)
        if url in ROUTES:
            return httpx.Response(200, json=load(ROUTES[url]))
        if url == settings.iss_tle_urls[0].split("?")[0]:
            return httpx.Response(200, text=(FIXTURES / "iss_tle.txt").read_text())
        if url == settings.open_meteo_url:
            return httpx.Response(200, json=load("weather.json"))
        if url == settings.cloud_caps_url.split("?")[0]:
            return httpx.Response(200, text=(FIXTURES / "clouds_caps.xml").read_text(encoding="utf-8"))
        if url.endswith("/search"):
            return httpx.Response(200, json=[{"display_name": "Tromsø, Norway", "lat": "69.65", "lon": "18.96"}])
        if url.endswith("/reverse"):
            return httpx.Response(200, json={"address": {"city": "Tromsø", "country": "Norway"}})
        return httpx.Response(404)

    return httpx.MockTransport(handler)


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(transport=fake_noaa(), data_dir=str(tmp_path),
                               admin_token="secret")) as c:
        yield c
