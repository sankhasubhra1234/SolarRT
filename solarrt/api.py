"""FastAPI application: JSON API under /api plus the web UI as static files."""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import APP_NAME, __version__
from .cache import TTLCache
from .config import settings
from .feedback import FeedbackFull, FeedbackIn, FeedbackStore
from .iss import IssTracker, parse_tle
from .weather import CURRENT_FIELDS, HOURLY_FIELDS, parse_cloud_time, summarize_weather
from .noaa import (AuroraGrid, NoaaClient, build_kp_summary, haversine_km, sky_darkness,
                   sun_elevation)
from .regions import activity_level, summarize_regions
from .security import RateLimiter, SecurityMiddleware, client_ip, safe_language

log = logging.getLogger(__name__)
# httpx logs every outgoing URL at INFO, and weather/place-search URLs contain users'
# coordinates or search text, so keep it to warnings and errors only (privacy).
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
STATIC_DIR = Path(__file__).parent / "static"
NEARBY_RADIUS_KM = 800  # aurora high in the sky can be seen low on the horizon from this far

# Friendly service names for 503 messages. Only the key's kind is used, never the whole key,
# because per-location keys contain coordinates and must never be echoed back or logged.
SERVICE_NAMES = {
    "ovation": "Aurora forecast",
    "kp_1m": "Kp index",
    "kp_3h": "Kp index",
    "kp_forecast": "Kp index",
    "iss_tle": "ISS orbit",
    "iss_snap": "ISS position",
    "wx": "Weather",
    "clouds": "Cloud imagery",
}


def _service_name(key: str) -> str:
    return SERVICE_NAMES.get(key.split(":", 1)[0], "Space-weather")


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _age(seconds: float) -> float:
    """Cache ages are reported to one decimal place so a just-expired entry is not shown as 0."""
    return round(max(0.0, seconds), 1)


def create_app(transport: httpx.AsyncBaseTransport | None = None, data_dir: str | None = None,
               admin_token: str | None = None) -> FastAPI:
    """transport lets tests inject a mock HTTP layer instead of calling the real services;
    data_dir / admin_token override the configured feedback storage and admin token."""
    cache = TTLCache(max_entries=100)        # shared global data (NOAA, ISS, clouds)
    user_cache = TTLCache(max_entries=5000)  # per-location/per-query data (weather, place search)
    state: dict[str, Any] = {}
    geocode_lock = asyncio.Lock()
    last_geocode = [0.0]

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with httpx.AsyncClient(transport=transport, follow_redirects=True,
                                     headers={"User-Agent": settings.user_agent}) as client:
            state["client"] = client
            state["noaa"] = NoaaClient(client)
            yield

    docs = settings.enable_docs
    app = FastAPI(title=f"{APP_NAME} API", version=__version__, lifespan=lifespan,
                  docs_url="/docs" if docs else None, redoc_url=None,
                  openapi_url="/openapi.json" if docs else None)
    # Order matters: the last added runs first. Host check, then limits + security headers.
    app.add_middleware(SecurityMiddleware,
                       api_limit=RateLimiter(settings.rate_limit_api, 60),
                       search_limit=RateLimiter(settings.rate_limit_search, 60))
    if "*" not in settings.allowed_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.allowed_hosts))

    async def cached(key: str, ttl: int, loader, store: TTLCache = cache,
                     max_stale: float | None = None):
        """Fetch through a cache and return ``(value, stale, age_seconds)``.

        A failure is turned into a 503 whose message names only the data kind, so a
        per-location key can never leak coordinates into the response body.
        """
        try:
            return await store.get(key, ttl, loader, max_stale=max_stale)
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            # Per-user keys contain coordinates: only log the kind for those (privacy).
            log.error("Fetching %s failed: %s", key if store is cache else key.split(":")[0],
                      type(exc).__name__)
            raise HTTPException(503, f"{_service_name(key)} is currently unavailable") from exc

    async def grid() -> tuple[AuroraGrid, bool, float]:
        return await cached("ovation", settings.ttl_ovation, state["noaa"].ovation,
                            max_stale=settings.max_stale_noaa)

    async def kp_summary() -> tuple[dict[str, Any], bool, float]:
        noaa: NoaaClient = state["noaa"]
        (now_1m, s1, a1), (hist, s2, a2), (fc, s3, a3) = await asyncio.gather(
            cached("kp_1m", settings.ttl_kp_1m, noaa.kp_1m,
                   max_stale=settings.max_stale_noaa),
            cached("kp_3h", settings.ttl_kp_3h, noaa.kp_3h,
                   max_stale=settings.max_stale_noaa),
            cached("kp_forecast", settings.ttl_kp_3h, noaa.kp_forecast,
                   max_stale=settings.max_stale_noaa),
        )
        return build_kp_summary(now_1m, hist, fc), (s1 or s2 or s3), max(a1, a2, a3)

    # ------------------------------------------------------------------ API routes

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "app": APP_NAME, "version": __version__,
                "edition": os.environ.get("SOLARRT_EDITION", "web")}

    @app.get("/api/kp")
    async def kp():
        summary, stale, age = await kp_summary()
        return {**summary, "stale": stale, "age_seconds": _age(age), "source": "NOAA SWPC"}

    @app.get("/api/aurora")
    async def aurora():
        g, stale, age = await grid()
        return {
            "observation_time": _iso(g.observation_time),
            "forecast_time": _iso(g.forecast_time),
            "width": 360, "height": 181,
            "encoding": "base64 uint8, row = latitude -90..90, column = longitude 0..359",
            "data": g.encoded(),
            "hemisphere_max": g.hemisphere_max(),
            "stale": stale,
            "age_seconds": _age(age),
        }

    @app.get("/api/regions")
    async def regions():
        g, stale, age = await grid()
        return {"forecast_time": _iso(g.forecast_time), "regions": summarize_regions(g),
                "stale": stale, "age_seconds": _age(age)}

    @app.get("/api/location")
    async def location(lat: float = Query(..., ge=-90, le=90),
                       lon: float = Query(..., ge=-180, le=180)):
        g, stale, age = await grid()
        here = g.value(lat, lon)
        near_val, near_lat, near_lon = g.max_within(lat, lon, NEARBY_RADIUS_KM)
        elev = sun_elevation(lat, lon)
        dark = sky_darkness(elev)
        try:
            summary, _, _ = await kp_summary()
            current_kp = summary["current"]
        except HTTPException:
            current_kp = None

        if here >= 30:
            chance, verdict = "high", "Aurora likely overhead"
        elif here >= 10:
            chance, verdict = "moderate", "Aurora possible overhead"
        elif near_val >= 10:
            side = "northern" if lat >= 0 else "southern"
            chance, verdict = "low", f"Possibly visible low on the {side} horizon"
        else:
            chance, verdict = "none", "Aurora unlikely from here right now"
        if chance != "none" and elev > -6:
            verdict += " — but it's too bright to see it now"

        return {
            "lat": lat, "lon": lon,
            "probability": round(here, 1),
            "level": activity_level(here),
            "nearby": {
                "max": near_val, "lat": near_lat, "lon": near_lon,
                "distance_km": round(haversine_km(lat, lon, near_lat, near_lon)) if near_val else None,
                "radius_km": NEARBY_RADIUS_KM,
            },
            "sun_elevation": round(elev, 1),
            "sky": dark,
            "chance": chance,
            "verdict": verdict,
            "kp": current_kp,
            "forecast_time": _iso(g.forecast_time),
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "stale": stale,
            "age_seconds": _age(age),
        }

    # ------------------------------------------------------------------ ISS

    async def load_iss() -> IssTracker:
        last_error: Exception | None = None
        for url in settings.iss_tle_urls:  # primary source, then fallback
            try:
                r = await state["client"].get(url, timeout=settings.http_timeout)
                r.raise_for_status()
                return IssTracker(parse_tle(r.text))
            except (httpx.HTTPError, ValueError) as exc:
                log.warning("ISS TLE from %s failed: %s", url, exc)
                last_error = exc
        raise last_error or ValueError("No ISS TLE source")

    async def iss_snapshot() -> tuple[dict[str, Any], bool, float]:
        tracker, tle_stale, tle_age = await cached(
            "iss_tle", settings.ttl_iss_tle, load_iss, max_stale=settings.max_stale_noaa)

        async def load_snapshot():
            return tracker.snapshot()  # SGP4 is synchronous; run it on the event loop as before

        # The snapshot is observer-independent, so one propagation serves every client. SGP4
        # errors become a 503 (or a snapshot no older than two minutes if one is cached).
        snap, snap_stale, snap_age = await cached(
            "iss_snap", settings.ttl_iss_snapshot, load_snapshot, max_stale=120)
        return snap, tle_stale or snap_stale, max(tle_age, snap_age)

    @app.get("/api/iss")
    async def iss(lat: float | None = Query(None, ge=-90, le=90),
                  lon: float | None = Query(None, ge=-180, le=180)):
        snap, stale, age = await iss_snapshot()
        out = dict(snap)
        if lat is not None and lon is not None:
            # Cheap per-request observer block; the expensive snapshot itself is shared.
            distance = haversine_km(lat, lon, snap["lat"], snap["lon"])
            out["observer"] = {"distance_km": round(distance),
                               "in_view": distance <= snap["footprint_km"]}
        return {**out, "stale": stale, "age_seconds": _age(age)}

    # ------------------------------------------------------------------ weather & clouds

    @app.get("/api/weather")
    async def weather(lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-180, le=180)):
        lat_r, lon_r = round(lat, 2), round(lon, 2)  # ~1 km; lets nearby requests share the cache

        async def load():
            r = await state["client"].get(settings.open_meteo_url, timeout=settings.http_timeout, params={
                "latitude": lat_r, "longitude": lon_r, "current": CURRENT_FIELDS,
                "hourly": HOURLY_FIELDS, "forecast_hours": 30, "timezone": "auto",
                # Epoch seconds are unambiguous across a DST change; ISO local times are not.
                "timeformat": "unixtime",
            })
            r.raise_for_status()
            return r.json()
        data, stale, age = await cached(f"wx:{lat_r},{lon_r}", settings.ttl_weather, load,
                                        user_cache, max_stale=settings.max_stale_weather)
        return {**summarize_weather(data, lat, lon), "stale": stale, "age_seconds": _age(age)}

    @app.get("/api/clouds")
    async def clouds():
        async def load():
            r = await state["client"].get(settings.cloud_caps_url, timeout=settings.http_timeout)
            r.raise_for_status()
            return parse_cloud_time(r.text)
        try:
            image_time, stale, age = await cache.get("clouds", settings.ttl_clouds, load,
                                                     max_stale=settings.max_stale_noaa)
        except (httpx.HTTPError, ValueError):
            image_time, stale, age = None, True, 0.0
        return {"wms_url": settings.cloud_wms_url, "layer": settings.cloud_layer,
                "time": image_time, "stale": stale, "age_seconds": _age(age),
                "attribution": "Clouds © EUMETSAT (geostationary IR 10.8 µm composite)"}

    # ------------------------------------------------------------------ feedback

    feedback_store = FeedbackStore(data_dir or settings.data_dir, max_bytes=settings.feedback_max_bytes)
    admin = settings.admin_token if admin_token is None else admin_token

    @app.post("/api/feedback", status_code=201)
    async def post_feedback(fb: FeedbackIn, request: Request):
        if not feedback_store.allowed(client_ip(request)):
            raise HTTPException(429, "Thanks! You've sent a lot of feedback — please try again later.")
        try:
            entry = feedback_store.add(fb)
        except FeedbackFull as exc:
            log.error("Feedback storage is full (%s)", exc)
            raise HTTPException(503, "Feedback can't be accepted right now — please try again later.") from exc
        forwarded = False
        # Guard against a forwarding loop: if another SolarRT instance already forwarded this
        # entry, store it here but do not send it on again (a misconfiguration fails safe).
        already_forwarded = request.headers.get("x-solarrt-forwarded") == "1"
        if settings.feedback_forward_url and not already_forwarded:
            try:
                r = await state["client"].post(
                    settings.feedback_forward_url, json=fb.model_dump(),
                    headers={"X-SolarRT-Forwarded": "1"}, timeout=settings.http_timeout)
                forwarded = r.status_code < 300
            except httpx.HTTPError as exc:
                log.warning("Forwarding feedback failed: %s", exc)
        return {"ok": True, "id": entry["id"], "forwarded": forwarded}

    @app.get("/api/feedback")
    async def list_feedback(request: Request):
        # Token goes in a header ("Authorization: Bearer <token>"), never the URL, so it can't
        # leak into logs or browser history; compared in constant time.
        auth = request.headers.get("authorization", "")
        token = auth[7:] if auth.lower().startswith("bearer ") else ""
        if not admin or not secrets.compare_digest(token.encode(), admin.encode()):
            raise HTTPException(403, "Feedback can only be read with the admin token")
        return feedback_store.summary()

    # ------------------------------------------------------------------ geocoding

    async def nominatim(path: str, params: dict[str, Any]) -> Any:
        # Nominatim usage policy: max 1 request per second from this server. Requests queue
        # for the slot, but never longer than 10 s (a flood can't stall everyone indefinitely).
        try:
            await asyncio.wait_for(geocode_lock.acquire(), timeout=10)
        except asyncio.TimeoutError as exc:
            raise httpx.HTTPError("place search is busy") from exc
        try:
            wait = 1.0 - (time.monotonic() - last_geocode[0])
            if wait > 0:
                await asyncio.sleep(wait)
            last_geocode[0] = time.monotonic()
            r = await state["client"].get(f"{settings.nominatim_url}/{path}",
                                          params={**params, "format": "jsonv2"},
                                          timeout=settings.http_timeout)
        finally:
            geocode_lock.release()
        r.raise_for_status()
        return r.json()

    def lang_of(request: Request) -> str:
        """Use the browser's language for place names (validated; falls back to English)."""
        return safe_language(request.headers.get("accept-language"))

    @app.get("/api/geocode")
    async def geocode(request: Request, q: str = Query(..., min_length=2, max_length=120)):
        lang = lang_of(request)

        async def load():
            rows = await nominatim("search", {"q": q, "limit": 5, "accept-language": lang})
            return [{"name": r.get("display_name", ""), "lat": float(r["lat"]),
                     "lon": float(r["lon"])} for r in rows if "lat" in r and "lon" in r]
        try:
            results, _, _ = await user_cache.get(f"geo:{lang}:{q.strip().lower()}", settings.ttl_geocode, load)
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise HTTPException(503, "Place search is currently unavailable") from exc
        return {"results": results}

    @app.get("/api/reverse")
    async def reverse(request: Request, lat: float = Query(..., ge=-90, le=90),
                      lon: float = Query(..., ge=-180, le=180)):
        lang = lang_of(request)
        key = f"rev:{lang}:{lat:.2f},{lon:.2f}"

        async def load():
            r = await nominatim("reverse", {"lat": lat, "lon": lon, "zoom": 10,
                                            "accept-language": lang})
            a = r.get("address", {}) if isinstance(r, dict) else {}
            place = (a.get("city") or a.get("town") or a.get("village") or a.get("county")
                     or a.get("state") or "")
            return ", ".join(p for p in (place, a.get("country")) if p) or None
        try:
            name, _, _ = await user_cache.get(key, settings.ttl_geocode, load)
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(503, "Reverse geocoding is currently unavailable") from exc
        return {"name": name}

    # ------------------------------------------------------------------ web UI

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.middleware("http")
    async def revalidate_ui(request: Request, call_next):
        # The UI files change with every release: make browsers (and the desktop app's
        # WebView2 cache) check for a newer version instead of running a stale copy.
        response = await call_next(request)
        path = request.url.path
        if path == "/" or (path.startswith("/static/") and not path.startswith("/static/vendor/")):
            response.headers["Cache-Control"] = "no-cache"
        return response

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        return FileResponse(STATIC_DIR / "favicon.svg", media_type="image/svg+xml")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app


app = create_app()
