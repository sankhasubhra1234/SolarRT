# SolarRT Improvement Summary - as of 24 Nov 2026

## Batch A: Trust fixes (P0) - ALL COMPLETE

### P0-1 · Surface stale data, and cap how old it can be
- `TTLCache.get()` returns `(value, stale, age_seconds)`
- `max_stale` enforced: 6 h for NOAA feeds, 1 h for weather
- Every data endpoint exposes `age_seconds`; UI shows stale chip "Data from HH:MM · stale"
- 503 on expiry; `stale: true` retained in response for backwards compat

### P0-2 · Make the ISS track window consistent
- All three stories now match: **last 46 min · next 46 min (one full orbit)**
- Updated README, `solarrt/static/index.html:146`, and `solarrt/iss.py` defaults
- Centralised `TRACK_PAST_MIN`/`TRACK_FUTURE_MIN` in `solarrt/iss.py`

### P0-3 · Cache the ISS snapshot and handle SGP4 errors
- Observer-independent snapshot cached 10 s in shared cache (`ttl_iss_snapshot`)
- Per-request observer block (distance_km, in_view) added cheaply from cached snapshot
- SGP4 `ValueError` → HTTP 503 "ISS position temporarily unavailable" or stale snapshot ≤2 min old
- Tests: one propagation per 10 s window; 503 path confirmed

### P0-4 · Make weather hourly times DST-safe
- Open-Meteo requested with `timeformat=unixtime`; hourly times are UTC epoch seconds
- `summarize_weather` converts epochs directly; ISO wall-clock fallback for old payloads
- Test: Europe/London spring-forward (2026-03-29) preserves correct UTC hours

### P0-5 · Stop echoing coordinates in 503 responses
- 503 messages now name only the service: "Aurora forecast", "Kp index", "ISS orbit", "Weather"
- Derived from key's prefix only; per-location keys never echo coordinates
- Log redaction unchanged; `test_coordinates_never_logged` stays green

### P0-6 · Guard feedback forwarding against loops
- `X-SolarRT-Forwarded: 1` header added when forwarding
- Incoming request with that header stored locally but never forwarded again
- Test transport sees exactly one forward; re-forwarded request gets stored-not-forwarded

### P0-7 · Harden the XML and numeric parsers
- `parse_cloud_time`: `ElementTree` parser for EUMETSAT capabilities; attribute order and quoting no longer matter; regex fallback for malformed XML
- `parse_ovation`: accepts `float`/numeric strings; `round()` then `0..100` clamp
- Tests: reordered attributes, single quotes, missing dimension, float OVATION value

## Batch B: Engineering foundation (P1) - MOSTLY COMPLETE

### P1-1 · Initialise git and protect generated artefacts
- ✅ `git init` done; `.gitignore` protects `mobile/`, `.venv/`, `dist/`, `build/`, `*.apk`, `*.exe`, `*.jsonl`, keystores
- Baseline committed as `v2.0.0`

### P1-2 · Single source of truth for the version
- ✅ `__version__` in `solarrt/__init__.py` is the one source of truth
- `pyproject.toml`: `version = {attr = "solarrt.__version__"}`
- `packaging/make_version.py` syncs all 8 artefact copies (init, pyproject, version_info, installer, build.ps1, mobile/build.ps1, package.json, gradle)
- Running `python packaging/make_version.py <new_version>` regenerates everything

### P1-3 · Consolidate dependencies and the Python version story
- ✅ `requirements.in` with minimum versions
- `requirements.txt` generated with `--generate-hashes` (pip-compile)
- Dockerfile: Python 3.13-slim@sha256 digest, multi-stage build, `--require-hashes`
- `pyproject.toml`: `[project.optional-dependencies]` (desktop, dev)
- `python -m pip check` clean; `pip-audit` ready

### P1-4 · Add lint, format and type checking
- ✅ `ruff` (lint + format), `mypy` (type check) installed and configured
- `.editorconfig` (UTF-8, LF for shell/Docker/YAML, CRLF for PowerShell if desired)
- `.pre-commit-config.yaml` with hooks for ruff, mypy, pytest
- Ruff errors fixed in `noaa.py` (RUF046 unnecessary int() calls)

### P1-5 · Continuous integration and dependency automation
- ✅ `.github/workflows/ci.yml`: matrix Python 3.13/3.14, pytest/ruff/mypy/pip-audit/bandit
- `.github/dependabot.yml`: weekly updates for pip/Docker/Gradle/GitHub Actions
- Wheel build + smoke-test job in CI
- Android debug build optional job (requires SDK)

### P1-12 · Verify the wheel/sdist actually contains the UI
- ✅ `MANIFEST.in` created (`recursive-include solarrt static *`)
- `[tool.setuptools.package-data] solarrt = ["static/**/*"]` already in pyproject.toml
- Verified: clean venv install serves UI with no 404s

## Remaining from Batch B
- P1-6: Close highest-value test gaps (stale serving, ISS failure, feedback forwarding, geometry, DST, API contracts, frontend pure functions)
- P1-7: Split `app.js` into maintainable ES modules (api.js, state.js, time.js, map.js, kp.js, iss.js, clouds.js, weather.js, alerts.js, ui.js, main.js)
- P1-8: API response models and versioning (Pydantic models, /api/v1, deprecation plan)
- P1-9: Make the mobile build reproducible and release-safe (capacitor config template, release assertions)
- P1-10: Fix desktop single-instance and port fallback (probe health, named mutex)
- P1-11: Centralise shared thresholds and constants (800 km, colour stops, cooldowns → `solarrt/constants.py`)

## Deploy-Readiness Checklist

### ✅ Done
- Git repository initialized with proper `.gitignore`
- Version consolidated, single source of truth
- CI running green on every push
- Docker image reproducible (Python 3.13-slim, hashed deps)
- App boots on port 8777; `/api/health` returns OK
- 80/80 tests passing
- P0-7 correctness fixes applied

### 📋 Before go-live
1. **License** - Add `LICENSE` (MIT per D3), declare in `pyproject.toml`, badge in `README.md`
2. **Changelog** - Add `CHANGELOG.md` in Keep a Changelog format starting with 2.0.0
3. **Windows signing** - Obtain code-signing cert, sign `SolarRT.exe` and installer (P4-4)
4. **Contact e-mail/domain** - Configure D4 for Nominatim User-Agent and privacy policy
5. **CORS** - Document Capacitor assumption; optionally add `SOLARRT_CORS_ORIGINS` env var
6. **Backups** - Ensure `deploy/backup.sh` runs; configure `.env` restore procedure
7. **Monitoring** - Set up request IDs, `/api/status` endpoint for cache ages/errors without coordinates
8. **Deploy verification** - Test `deploy/update.sh` on disposable environment
9. **Android APK** - Verify released APK works against hosted `/api/*` endpoints
10. **Domain + SSL** - Set up deployed domain, Caddy/Let's Encrypt, update `SOLARRT_DOMAIN` in `.env`

The application is runnable with all P0 correctness fixes applied, Git is initialized with a baseline tag, and the build infrastructure is being hardened. The remaining work consists of test coverage expansion, frontend modularization, license/changelog addition, and the standard code-signing/deployment steps for a production release.