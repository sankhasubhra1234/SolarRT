from datetime import datetime, timezone

import pytest

from solarrt.noaa import (KpPoint, build_kp_summary, g_scale, haversine_km, kp_label,
                          parse_kp_1m, parse_kp_3h, parse_kp_forecast, parse_ovation,
                          sky_darkness, sun_elevation)
from tests.conftest import load


@pytest.mark.parametrize("kp,g", [(0, 0), (4.33, 0), (4.67, 1), (5.0, 1), (5.67, 2), (7.0, 3),
                                  (8.33, 4), (8.67, 5), (9.0, 5)])
def test_g_scale(kp, g):
    assert g_scale(kp) == g


@pytest.mark.parametrize("kp,label", [(4.67, "5-"), (5.0, "5o"), (5.33, "5+"), (0.33, "0+"), (0, "0o")])
def test_kp_label(kp, label):
    assert kp_label(kp) == label


def test_parse_kp_3h_current_format():
    pts = parse_kp_3h(load("kp_3h.json"))
    assert pts and all(isinstance(p.kp, float) for p in pts)
    assert pts == sorted(pts, key=lambda p: p.time)


def test_parse_kp_3h_legacy_rows_format():
    legacy = [["time_tag", "Kp", "a_running", "station_count"],
              ["2024-08-01 00:00:00.000", "2.33", "9", "8"],
              ["2024-08-01 03:00:00.000", "5.67", "48", "8"]]
    pts = parse_kp_3h(legacy)
    assert [p.kp for p in pts] == [2.33, 5.67]


def test_parse_kp_tolerates_garbage():
    assert parse_kp_3h(None) == []
    assert parse_kp_3h([{"time_tag": "bad", "Kp": 1}, {"Kp": "x"}, 5]) == []
    assert parse_kp_1m({"not": "a list"}) is None


def test_parse_kp_forecast_kinds():
    pts = parse_kp_forecast(load("kp_forecast.json"))
    assert {p.kind for p in pts} <= {"observed", "estimated", "predicted"}


def test_parse_kp_1m_latest():
    p = parse_kp_1m(load("kp_1m.json"))
    assert p is not None and 0 <= p.kp <= 9


def test_summary_relabels_future_estimates_as_forecast():
    t = lambda h: datetime(2026, 1, 1, h, tzinfo=timezone.utc)
    forecast = [KpPoint(t(0), 2, "observed"), KpPoint(t(3), 3, "estimated"),
                KpPoint(t(6), 6, "estimated"), KpPoint(t(9), 4, "predicted")]
    s = build_kp_summary(None, [KpPoint(t(0), 2, "observed")], forecast, now=t(4))
    kinds = [p["kind"] for p in s["series"]]
    assert kinds == ["observed", "estimated", "predicted", "predicted"]
    assert s["forecast_peak_24h"]["kp"] == 6 and s["forecast_peak_24h"]["g"] == 2


def test_ovation_grid_lookup():
    grid = parse_ovation(load("ovation.json"))
    assert len(grid.values) == 360 * 181
    raw = {(c[0], c[1]): c[2] for c in load("ovation.json")["coordinates"]}
    (lon, lat), val = max(raw.items(), key=lambda kv: kv[1])
    lon_signed = lon - 360 if lon >= 180 else lon
    assert grid.value(lat, lon_signed) == pytest.approx(val)
    assert grid.max_within(lat + 2, lon_signed, 400)[0] == val


def test_ovation_bad_input():
    with pytest.raises(ValueError):
        parse_ovation({"nope": 1})


def test_haversine():
    assert haversine_km(0, 0, 0, 1) == pytest.approx(111.2, abs=0.5)


def test_sun_elevation_sanity():
    noon = datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc)
    assert sun_elevation(23.44, 0, noon) == pytest.approx(90, abs=1.5)
    assert sun_elevation(0, 180, noon) < -60
    assert sky_darkness(-20) == "Dark" and sky_darkness(5) == "Daylight"
