from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from solarrt import api as api_module
from solarrt.iss import IssTracker, parse_tle
from tests.conftest import FIXTURES, fake_noaa


@pytest.fixture
def tracker():
    return IssTracker(parse_tle((FIXTURES / "iss_tle.txt").read_text()))


def test_parse_tle_rejects_garbage():
    with pytest.raises(ValueError):
        parse_tle("not a tle")


def test_position_is_physical(tracker):
    p = tracker.position(tracker.tle.epoch + timedelta(hours=1))
    assert -52 <= p["lat"] <= 52            # ISS inclination is 51.6°
    assert -180 <= p["lon"] <= 180
    assert 350 < p["alt_km"] < 450
    assert 27_000 < p["speed_kmh"] < 28_500


def test_snapshot_track_and_observer(tracker):
    s = tracker.snapshot(tracker.tle.epoch, observer=(0.0, 0.0))
    assert len(s["track"]) == 93 and s["track"][46][2] == 0  # one orbit: 46 min past + now + 46 min future
    assert s["track"][46][:2] == [round(s["lat"], 3), round(s["lon"], 3)]
    assert 2000 < s["footprint_km"] < 2500
    assert isinstance(s["observer"]["in_view"], bool)


def test_api_iss(client):
    d = client.get("/api/iss", params={"lat": 52, "lon": 4}).json()
    assert {"lat", "lon", "altitude_km", "track", "observer", "sunlit"} <= d.keys()


def test_iss_snapshot_is_cached_between_requests(monkeypatch, tmp_path):
    calls = {"n": 0}
    real = api_module.IssTracker

    class Counting(real):
        def snapshot(self, *args, **kwargs):
            calls["n"] += 1
            return super().snapshot(*args, **kwargs)

    monkeypatch.setattr(api_module, "IssTracker", Counting)
    with TestClient(api_module.create_app(transport=fake_noaa(),
                                          data_dir=str(tmp_path))) as c:
        assert c.get("/api/iss").status_code == 200
        assert c.get("/api/iss", params={"lat": 52, "lon": 4}).status_code == 200
    assert calls["n"] == 1  # one propagation served both requests within the 10 s TTL


def test_iss_propagation_error_becomes_503(monkeypatch, tmp_path):
    class Broken:
        def __init__(self, tle):
            self.tle = tle

        def snapshot(self):
            raise ValueError("SGP4 propagation error 1")

    monkeypatch.setattr(api_module, "IssTracker", Broken)
    with TestClient(api_module.create_app(transport=fake_noaa(),
                                          data_dir=str(tmp_path))) as c:
        r = c.get("/api/iss")
        assert r.status_code == 503
        assert "ISS position" in r.json()["detail"]

