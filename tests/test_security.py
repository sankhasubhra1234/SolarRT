import asyncio

import pytest
from fastapi.testclient import TestClient

from solarrt import api as api_module
from solarrt.cache import TTLCache
from solarrt.config import Settings
from solarrt.feedback import FeedbackFull, FeedbackIn, FeedbackStore
from solarrt.security import RateLimiter, safe_language
from tests.conftest import fake_noaa


def test_security_headers_on_pages_and_api(client):
    for path in ("/", "/api/health", "/static/app.js"):
        h = client.get(path).headers
        assert "script-src 'self'" in h["content-security-policy"]
        assert "frame-ancestors 'none'" in h["content-security-policy"]
        assert h["x-content-type-options"] == "nosniff"
        assert h["x-frame-options"] == "DENY"
        assert "geolocation=(self)" in h["permissions-policy"]


def test_page_has_no_inline_scripts(client):
    html = client.get("/").text
    assert "<script>" not in html and "onsubmit=" not in html and "onclick=" not in html


def test_request_body_limit(client):
    r = client.post("/api/feedback", content=b"{" + b" " * 70_000 + b"}",
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 413


def test_rate_limiter_window_and_memory_bound():
    rl = RateLimiter(limit=2, window_s=60, max_clients=3)
    assert rl.allow("a") and rl.allow("a") and not rl.allow("a")
    for c in "bcdef":
        rl.allow(c)
    assert len(rl._hits) == 3  # oldest clients forgotten


def test_api_rate_limit(monkeypatch, tmp_path):
    monkeypatch.setattr(api_module, "settings", Settings(rate_limit_api=3, rate_limit_search=1))
    with TestClient(api_module.create_app(transport=fake_noaa(), data_dir=str(tmp_path))) as c:
        codes = [c.get("/api/kp").status_code for _ in range(4)]
        assert codes == [200, 200, 200, 429]
        assert c.get("/api/health").status_code == 200  # health checks never limited


def test_search_rate_limit(monkeypatch, tmp_path):
    monkeypatch.setattr(api_module, "settings", Settings(rate_limit_api=100, rate_limit_search=2))
    with TestClient(api_module.create_app(transport=fake_noaa(), data_dir=str(tmp_path))) as c:
        codes = [c.get("/api/geocode", params={"q": f"place{i}"}).status_code for i in range(3)]
        assert codes == [200, 200, 429]


def test_trusted_hosts(monkeypatch, tmp_path):
    monkeypatch.setattr(api_module, "settings", Settings(allowed_hosts=("127.0.0.1", "localhost")))
    with TestClient(api_module.create_app(transport=fake_noaa(), data_dir=str(tmp_path)),
                    base_url="http://localhost") as c:
        assert c.get("/api/health").status_code == 200
        assert c.get("/api/health", headers={"host": "evil.example"}).status_code == 400


def test_docs_can_be_disabled(monkeypatch, tmp_path):
    monkeypatch.setattr(api_module, "settings", Settings(enable_docs=False))
    with TestClient(api_module.create_app(transport=fake_noaa(), data_dir=str(tmp_path))) as c:
        assert c.get("/docs").status_code == 404 and c.get("/openapi.json").status_code == 404


def test_cache_is_bounded():
    cache = TTLCache(max_entries=3)

    async def fill():
        for i in range(10):
            async def load(i=i):
                return i
            await cache.get(f"k{i}", 60, load)
    asyncio.run(fill())
    assert len(cache) == 3


def test_feedback_file_size_cap(tmp_path):
    store = FeedbackStore(tmp_path, max_bytes=300)
    store.add(FeedbackIn(rating=5, comment="x" * 200))
    with pytest.raises(FeedbackFull):
        store.add(FeedbackIn(rating=5, comment="more"))


def test_coordinates_never_logged(client, caplog):
    import logging
    caplog.set_level(logging.DEBUG)
    client.get("/api/weather", params={"lat": 57.1234, "lon": -2.5678})
    client.get("/api/geocode", params={"q": "Secret Village"})
    text = caplog.text
    assert "57.12" not in text and "-2.5" not in text and "Secret Village" not in text


def test_privacy_page_served(client):
    r = client.get("/static/privacy.html")
    assert r.status_code == 200 and "Privacy policy" in r.text and "<script>" not in r.text


@pytest.mark.parametrize("header,expected", [
    ("en-GB,en;q=0.9", "en-GB"), ("nb", "nb"), ("", "en"), (None, "en"),
    ("x" * 50, "en"), ("en<script>", "en"), ("de-DE;q=1", "de-DE"),
])
def test_safe_language(header, expected):
    assert safe_language(header) == expected

def test_streamed_feedback_body_limit(client):
    response = client.post("/api/feedback", content=iter([b" " * 40000] * 2),
                           headers={"Content-Type": "application/json"})
    assert response.status_code == 413


def test_status_admin_uses_bearer_header(client):
    assert client.get("/api/status").json()["admin"] == {}
    authorized = client.get("/api/status", headers={"Authorization": "Bearer secret"})
    assert "uptime_seconds" in authorized.json()["admin"]
