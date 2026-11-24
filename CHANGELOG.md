# SolarRT Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-11-24

### Added
- P0-1: Stale data visibility with `age_seconds` and `max_stale` enforcement (6h NOAA, 1h weather)
- P0-2: ISS track window unified at 46/46 min (one full orbit)
- P0-3: ISS snapshot cached 10s; SGP4 errors → HTTP 503 instead of 500
- P0-4: DST-safe weather via Open-Meteo `timeformat=unixtime`
- P0-5: 503 messages name only the service, never coordinates (privacy)
- P0-6: Feedback forwarding loop guard with `X-SolarRT-Forwarded: 1` header
- P0-7: `ElementTree` XML parser for cloud timestamps; float-safe OVATION rounding
- P1-2: Single version source via `make_version.py` (syncs 8 artefacts)
- P1-3: Python 3.13 for Docker/CI; `requirements.in` + `requirements.txt` (hashed)
- P1-4: `ruff` + `mypy` + `.editorconfig` + `.pre-commit-config.yaml` added
- P1-5: CI workflow (matrix Python 3.13/3.14) + Dependabot weekly updates
- P1-6: 19 new tests added (cache, ISS, forwarding, geometry, DST, API contracts)
- P1-8: Pydantic response models in `solarrt/models.py`
- P1-11: Shared constants in `solarrt/constants.py`

### Changed
- Version consolidated to single source (`solarrt/__init__.py`)
- Dockerfile: Python 3.13-slim, multi-stage build, `--require-hashes`
- CI: matrix Python 3.13/3.14 with pytest/ruff/mypy/pip-audit/bandit
- `solarrt/weather.py`: DST-safe `_hour_time()` with epoch fallback
- `solarrt/api.py`: cached() returns triples `(value, stale, age_seconds)`
- `solarrt/api.py`: `/api/iss` observer block per request; SGP4 → 503
- `solarrt/api.py`: `/api/geocode` and `/api/reverse` unpack 3-tuple from cache
- `solarrt/config.py`: `max_stale_noaa` (6h), `max_stale_weather` (1h), `ttl_iss_snapshot` (10s)
- `solarrt/iss.py`: centralised `TRACK_PAST_MIN` / `TRACK_FUTURE_MIN` / `TRACK_STEP_S`
- `solarrt/noaa.py`: `parse_ovation()` accepts floats/numeric strings, rounds/clamp 0..100
- `solarrt/weather.py`: `parse_cloud_time()` uses `ElementTree` + regex fallback
- `solarrt/static/app.js`: stale-aware status UI; loaders return payloads
- `README.md`: ISS description corrected to 46/46

### Fixed
- `tests/test_api.py::test_geocode_and_reverse` → `KeyError: 'results'` unpack fix
- `tests/test_security.py::test_search_rate_limit` → geocode 3-tuple unpack
- `tests/test_iss.py::test_api_iss` → async loader wrapper for `tracker.snapshot`
- Ruff RUF046 errors in `solarrt/noaa.py`
- MyPy 5 errors across `solarrt/` source files

### Deprecated
- `starlette.testclient` usage (superseded by P1-4 tooling modernisation)

## [1.0.0] - 2024-01-01
### Added
- Initial release