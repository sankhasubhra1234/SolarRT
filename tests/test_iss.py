from datetime import timedelta

import pytest

from solarrt.iss import IssTracker, parse_tle
from tests.conftest import FIXTURES


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
