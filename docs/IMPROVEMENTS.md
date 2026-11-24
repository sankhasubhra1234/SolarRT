# SolarRT improvement backlog

> **Purpose:** a durable, self-contained work plan for improving SolarRT. Written after a
> read-only review of the whole codebase on **24 November 2026**. Nothing in this document has
> been implemented yet.
>
> **How to use it in a new session:** read this file top to bottom, then start with
> **Batch A** in [Suggested execution order](#suggested-execution-order). Work one item at a
> time, tick its checkbox, and run the verification command listed with it. Do not change the
> live deployment while working through the backlog; every item here is a repo change that can
> be tested locally first.

---

## Baseline (verified 24 Nov 2026)

| Fact | Value |
|---|---|
| App version | `2.0.0` |
| Python (dev venv) | 3.14.4 |
| Test suite | **93 passed** in ~3 s — +24 tests from P1-6/P1-8 additions |
| App boot | `python -m solarrt --port 8777` → `/api/health` returns `{"status":"ok"}` |
| Version control | **Git repo initialized** — `git status` clean; `git tag v2.0.0` |
| OS | Windows 10/11, PowerShell |

Commands used to verify the baseline:

```powershell
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m solarrt --port 8777
# in another shell:
Invoke-RestMethod http://127.0.0.1:8777/api/health
```

Known benign warnings: none (ruff, mypy, and ruff-format all pass; the earlier `starlette.testclient` deprecation note is superseded by P1-4).

### Source map

```
solarrt/
  api.py        FastAPI app, endpoints, caching orchestration, feedback forwarding
  noaa.py       NOAA parsers, Kp/G-scale, OVATION grid, sun position
  regions.py    aurora regions + activity levels
  iss.py        TLE parsing, SGP4, ground track, sunlit test
  weather.py    Open-Meteo summary, cloud-map timestamp
  feedback.py   validation, rate limiting, JSONL storage
  security.py   rate limiter, CSP/headers, body limit, client IP
  cache.py      bounded TTL cache with stale-on-error
  config.py     SOLARRT_* environment settings
  desktop.py    pywebview window + local uvicorn server
  __main__.py   CLI entry point
  static/       index.html, app.js, styles.css, config.js, theme-init.js, privacy.html, Leaflet
tests/          64 pytest tests + saved NOAA/TLE/weather fixtures
packaging/      PyInstaller spec, Inno Setup script, icon generator, build.ps1
mobile/         Capacitor Android project (generated www/ and android/ assets)
deploy/         Docker Compose, Caddy, server hardening, backups
docs/           user guide, deploy, security review, launch checklist, this file
```

---

## Ground rules for every change

1. **Run `pytest` before and after.** A change that breaks a green test is not done.
2. **Do not change an existing API response shape without versioning** (P1-8). Installed
   Android apps talk directly to the hosted server and cannot be force-updated.
3. **Keep the privacy test green.** `test_coordinates_never_logged` must keep passing; never
   log coordinates, search text or IP addresses.
4. **No new external assets** (fonts, JS, images) without vendoring them and updating the CSP
   in `solarrt/security.py`. No inline scripts.
5. **Every new upstream fetch** needs: a fixed URL, a timeout, a TTL cache entry, graceful
   stale/error handling, and a fixture-backed parser test.
6. **Update docs in the same change** — especially `README.md`, `docs/USER_GUIDE.md`,
   `docs/DEPLOY.md`, `docs/SECURITY.md` and this file.
7. **Never commit** `data/`, `dist/`, `build/`, `.venv/`, `mobile/node_modules/`,
   `mobile/www/`, `mobile/android/` build outputs, `deploy/.env`, keystores or
   `mobile/keystore.properties`.
8. **Do not touch the live server** during backlog work. Build and test locally; deploy
   deliberately with `deploy/update.sh`.

---

## Decisions needed before starting

Write the answers here when known; several items depend on them.

| # | Question | Default if undecided |
|---|---|---|
| D1 | ISS track window: 46 min past + 46 min future (one orbit), or 45 past + 95 future? | **46 / 46** and fix the README — *adopted 24 Nov 2026* |
| D2 | Minimum supported Python: 3.10, 3.13 or 3.14? | **3.13** for Docker/CI, allow 3.10+ for library use |
| D3 | Licence: MIT or Apache-2.0? | **MIT** |
| D4 | Public contact e-mail and domain for privacy policy + Nominatim User-Agent | Use the deployed domain + a real mailbox before go-live |
| D5 | CORS: document the Capacitor assumption, or add configurable origins? | **Both** — document now, optional env later |
| D6 | How long may stale data be shown before "unavailable"? | **6 h** for NOAA, **1 h** for weather — *adopted 24 Nov 2026* |
| D7 | What is the next flagship feature: tray mode, ISS passes, or solar wind? | **ISS passes** (highest user value per effort) — *adopted 24 Nov 2026* |

---

## Priority and status legend

| Priority | Meaning |
|---|---|
| **P0** | Correctness/trust bug; fix before adding features |
| **P1** | Engineering foundation; prevents future breakage |
| **P2** | Privacy, security, compliance, operability |
| **P3** | UX, product, accessibility, performance |
| **P4** | Docs and release polish |

| Effort | Meaning |
|---|---|
| **S** | Under ~1 hour |
| **M** | Half a day |
| **L** | 1–2 days |
| **XL** | More than 2 days / needs design |

Status: `- [ ]` not started · `- [x]` done. Add the date and a one-line note when done.

---

# P0 — Correctness and trust

These affect what users believe about the data. Do these first.

### - [x] P0-1 · Surface stale data, and cap how old it can be
**Done:** 24 Nov 2026 — `TTLCache.get()` returns `(value, stale, age_seconds)` and enforces
`max_stale` (6 h NOAA, 1 h weather). Every data endpoint reports `age_seconds`; `app.js` no
longer says “Updated” for stale data and shows “Data from HH:MM · stale” instead.
**Priority:** P0 · **Effort:** S–M · **Files:** `solarrt/cache.py`, `solarrt/api.py`,
`solarrt/static/app.js`, `tests/test_security.py`

**Problem**
Every endpoint returns `"stale": true/false`, and `TTLCache.get()` will serve the last good
value forever when an upstream fails. But `app.js` never reads `stale`, and `track()` sets the
header to “Updated HH:MM” on any HTTP 200. A six-hour-old aurora grid therefore looks fresh.

**Change**
1. In `cache.py`, give each call a `max_stale` (or add a `max_stale` argument to `get`) and
   expose the age. Suggested result: `(value, stale: bool, age_s: int)` or a small dataclass.
2. When `age_s > max_stale`, stop serving stale data and raise instead (so the endpoint
   returns 503).
3. In `api.py`, add `"age_seconds"` to `/api/kp`, `/api/aurora`, `/api/regions`,
   `/api/location`, `/api/weather`, `/api/clouds`, `/api/iss`.
4. In `app.js`, do not mark the UI “Updated” when `stale` is true. Show a visible chip/banner:
   “Data from 18:20 · stale” (use `age_seconds`).
5. Keep `stale` in the response for backwards compatibility.

**Acceptance**
- New test: a loader that always fails serves stale within the limit and raises after it.
- New test: `/api/kp` after an upstream failure has `stale: true` and a non-zero
  `age_seconds`; the UI test (manual or Playwright) shows the stale chip.
- Existing privacy test still passes.

---

### - [x] P0-2 · Make the ISS track window consistent
**Done:** 24 Nov 2026 — `iss.TRACK_PAST_MIN`/`TRACK_FUTURE_MIN` are 46/46 and drive
`snapshot()`; the README now matches the UI (“last 46 minutes … next 46 minutes, one orbit”).
**Priority:** P0 · **Effort:** S · **Files:** `README.md:8`, `solarrt/static/index.html:146`,
`solarrt/iss.py` (`snapshot`)

**Problem**
The README says “last 45 minutes … next 95 minutes”; the UI says “last 46 min · next 46 min”;
the code uses `past_min=46, future_min=46`. Three different stories.

**Change**
Pick **D1** (default 46/46, one orbit) and make all three match. If a longer forward track is
chosen, change `snapshot()` defaults and the UI hint together. Consider centralising the
window in `solarrt/config.py` so docs can quote it.

**Acceptance**
- `grep -R "45 min\|95 min\|46 min" README.md docs solarrt/static` returns one consistent
  story.
- `test_snapshot_track_and_observer` still asserts the new point count.

---

### - [x] P0-3 · Cache the ISS snapshot and handle SGP4 errors
**Done:** 24 Nov 2026 — the observer-independent snapshot is cached for
`ttl_iss_snapshot` (10 s); the observer distance/visibility is added per request. SGP4
`ValueError`s become HTTP 503 (“ISS position is currently unavailable”) or a snapshot up to
two minutes old. Tests assert one propagation per cache window and the 503 path.
**Priority:** P0 · **Effort:** S · **Files:** `solarrt/api.py` (`/api/iss`),
`solarrt/iss.py` (`snapshot`)

**Problem**
`/api/iss` calls `tracker.snapshot()` per request: 93 SGP4 propagations plus geodetic
iteration, per client, every 30 s. It also runs outside `cached()`, so a propagation error
becomes an unhandled 500.

**Change**
1. Cache the observer-independent snapshot for ~10 s in the shared cache:
   `snap, stale = await cached("iss_snap", 10, tracker.snapshot)`.
2. Add the observer block (`distance_km`, `in_view`) per request from the cached snapshot;
   it is cheap.
3. Wrap the snapshot call in `try/except ValueError` and return HTTP 503 with a clear message
   (“ISS position is temporarily unavailable”) or the previous snapshot if one exists.
4. Do not add per-user cache entries for ISS — that would grow the 5,000-entry user cache.

**Acceptance**
- Two `/api/iss` requests within 10 s only propagate once (assert via a counter or patched
  tracker).
- A tracker whose `snapshot` raises returns 503, not 500.
- Existing ISS tests pass.

---

### - [x] P0-4 · Make weather hourly times DST-safe
**Done:** 24 Nov 2026 — `/api/weather` requests Open-Meteo with `timeformat=unixtime`, so
hourly times are UTC epoch seconds. `summarize_weather` converts epochs directly and keeps an
ISO wall-clock fallback for old cached payloads and fixtures. A Europe/London spring-forward
test covers the transition.
**Priority:** P0 · **Effort:** M · **Files:** `solarrt/api.py` (`/api/weather` params),
`solarrt/weather.py` (`summarize_weather`), `tests/test_weather_feedback.py`

**Problem**
Open-Meteo is called with `timezone=auto`; hourly times are local wall-clock strings. All of
them are converted back to UTC with the **current** `utc_offset_seconds`. If the clocks change
within the next 24–30 h, every later hour is off by one hour.

**Change**
Preferred: keep `timezone=auto` (for the IANA name) and add `timeformat=unixtime`; convert the
epoch values with `datetime.fromtimestamp(ts, timezone.utc)`. No offset maths, no DST bug.
Alternative: request `timezone=UTC` and return UTC times, letting the browser render them in
the location zone (loses the server-known zone label unless fetched separately).

**Acceptance**
- New test with a DST transition day (e.g. Europe/London 2026-03-29) where the offset changes
  within the window; hourly UTC times are correct before and after the change.
- `test_summarize_weather_converts_local_times_and_reports_timezone` is updated or replaced.
- The UI still shows the location’s zone label.

---

### - [x] P0-5 · Stop echoing coordinates in 503 responses
**Done:** 24 Nov 2026 — 503 messages now name only the service
(`Aurora forecast`, `Kp index`, `ISS orbit`, `Weather`, …), derived from the key's prefix.
Log redaction is unchanged and the privacy test stays green.
**Priority:** P0 · **Effort:** S · **Files:** `solarrt/api.py` (`cached`, around the current
line 81)

**Problem**
```python
raise HTTPException(503, f"NOAA data for '{key}' is currently unavailable")
```
For `/api/weather`, `key` is `wx:57.15,-2.10`, so the response body contains the user’s
coordinates and wrongly blames NOAA for an Open-Meteo failure.

**Change**
- Use only the data kind in the message: `key.split(":")[0]`.
- Map kinds to friendly service names: `ovation → aurora forecast`, `kp_* → Kp index`,
  `iss_tle → ISS orbit`, `wx → weather`.
- Keep the log redaction exactly as it is (it is already correct).

**Acceptance**
- New test: `/api/weather` with a failing Open-Meteo has no coordinates in the body and does
  not say “NOAA”.
- `test_coordinates_never_logged` stays green.

---

### - [x] P0-6 · Guard feedback forwarding against loops
**Done:** 24 Nov 2026 — forwarded requests carry `X-SolarRT-Forwarded: 1`; an incoming
request with that header is stored locally but never forwarded again. The test transport sees
exactly one forward.
**Priority:** P0 · **Effort:** S · **Files:** `solarrt/api.py` (`post_feedback`),
`tests/test_weather_feedback.py`

**Problem**
If `SOLARRT_FEEDBACK_FORWARD_URL` points at a SolarRT server that also has forwarding enabled,
each hop re-forwards until the rate limiter stops it. A misconfiguration should fail safe.

**Change**
- Add an `X-SolarRT-Forwarded: 1` header when forwarding.
- Skip forwarding if the incoming request already has that header.
- Consider a short `timeout` (already `settings.http_timeout`) and log a warning on failure.

**Acceptance**
- New test: a mock transport sees exactly one forwarded request; a request that already has
  the marker is stored but not forwarded.

---

### - [x] P0-7 · Harden the XML and numeric parsers
**Done:** 24 Nov 2026 — `parse_cloud_time` uses `ElementTree` (attribute order and quoting no
longer matter) with a regex fallback for malformed documents; `parse_ovation` accepts floats
and numeric strings and rounds before clamping. Tests cover reordered/single-quoted/missing
dimensions and a float OVATION cell.
**Priority:** P0 · **Effort:** S · **Files:** `solarrt/weather.py` (`parse_cloud_time`),
`solarrt/noaa.py` (`parse_ovation`), tests

**Problem**
- `parse_cloud_time` uses a regex that depends on attribute order in the EUMETSAT
  GetCapabilities document. A reordered attribute silently disables the cloud timestamp.
- `parse_ovation` does `int(item[2])` before `round`, truncating any future float value.

**Change**
- Parse the capabilities document with `xml.etree.ElementTree` (stdlib), searching for a
  `Dimension` element whose `name == "time"`, and read its `default`. Keep the regex as a
  fallback and return `None` on malformed XML.
- In `parse_ovation`, accept `float`/numeric strings and use `round()` with the existing
  `0..100` clamp.
- Add fixture variants: reordered attributes, single quotes, a missing dimension, and a
  float OVATION value.

**Acceptance**
- `test_parse_cloud_time` covers both attribute orders and malformed XML.
- A new OVATION fixture with a float value rounds correctly.

---

# P1 — Engineering foundation

### - [x] P1-1 · Initialise git and protect generated artefacts
**Priority:** P1 · **Effort:** S · **Files:** `.gitignore`, repo root

**Done:** 24 Nov 2026 — `git init` performed; `.gitignore` protects `mobile/node_modules/`, `mobile/www/`,
`mobile/android/`, `*.gradle/`, `*.jks`, `*.keystore`, `.venv/`, `dist/`, `build/`, `*.apk`, `*.exe`,
`*.jsonl`, `.idea/`, `.vscode/`, `*.log`; baseline committed as `v2.0.0`.

**Change**
```powershell
git init
# add the entries below to .gitignore first
git add .
git commit -m "Baseline SolarRT 2.0.0"
git tag v2.0.0
```
Add to `.gitignore`:
```gitignore
mobile/node_modules/
mobile/www/
mobile/android/
mobile/.gradle/
mobile/keystore.properties
*.jks
*.keystore
.gradle/
.idea/
.vscode/
*.log
```
(`mobile/android/` is generated by Capacitor + Gradle; keep `mobile/android-overrides/` or
document any hand-edited Android files that must be tracked. If native edits are required,
track only `mobile/android/app/src/main/AndroidManifest.xml`,
`mobile/android/app/build.gradle`, resources and `capacitor.build.gradle`, and ignore build
outputs.)

**Acceptance**
- `git status --short` is clean after commit.
- `git ls-files` contains no `dist/`, `build/`, `.venv/`, `node_modules/`, `mobile/www/`,
  `*.apk`, `*.exe`, `*.jsonl` or keystore.
- `git tag` shows `v2.0.0`.

---

### - [x] P1-2 · Single source of truth for the version
**Priority:** P1 · **Effort:** M · **Files:** `solarrt/__init__.py`, `pyproject.toml`,
`packaging/version_info.txt`, `packaging/installer.iss`, `packaging/build.ps1`,
`mobile/package.json`, `mobile/android/app/build.gradle`, new script

**Done:** 24 Nov 2026 — `__version__` in `solarrt/__init__.py` is the one source of truth.
`pyproject.toml` uses `version = {attr = "solarrt.__version__"}`. `packaging/make_version.py`
syncs all 8 artefact copies (init, pyproject, version_info, installer, build.ps1, mobile/build.ps1,
package.json, gradle). Running `python packaging/make_version.py <ver>` regenerates everything.

**Change**
- Keep `solarrt/__init__.py:__version__` as the only literal.
- Add `packaging/make_version.py` that reads it and writes:
  - `packaging/version_info.txt` (filevers/prodvers and both string versions),
  - an `AppVersion` include for Inno Setup, or pass `/DAppVersion=$version` to `ISCC`,
  - the Android `versionName`/`versionCode` (already done in `mobile/build.ps1`),
  - optionally `mobile/package.json`’s `version`.
- Update `pyproject.toml` to use dynamic version if practical:
  ```toml
  [project]
  dynamic = ["version"]
  [tool.setuptools.dynamic]
  version = { attr = "solarrt.__version__" }
  ```
- Add a test that reads every version-bearing file and asserts they match.

**Acceptance**
- Bumping `__version__` and running `build.ps1` updates every artefact and message.
- A test fails if any file disagrees.

---

### - [x] P1-3 · Consolidate dependencies and the Python version story
**Priority:** P1 · **Effort:** M · **Files:** `requirements.in`, `requirements.txt`,
`Dockerfile`, `pyproject.toml`, `.github/workflows/ci.yml`

**Done:** 24 Nov 2026 — `requirements.in` with minimum versions; `requirements.txt` generated with
`pip-compile --generate-hashes`; Dockerfile uses Python 3.13-slim@sha256 digest, multi-stage build,
`--require-hashes`; `pyproject.toml` has `[project.optional-dependencies]` (desktop, dev); CI runs
matrix Python 3.13/3.14 with pytest/ruff/mypy/pip-audit/bandit.

**Change**
- Choose **D2** (default: Python 3.13 for Docker/CI; keep `>=3.10` for the library).
- Use `pip-compile --generate-hashes` from a small `requirements.in` to produce a locked
  `requirements.txt`; have the Dockerfile copy and install it with `--require-hashes`.
- Add extras:
  ```toml
  [project.optional-dependencies]
  desktop = ["pywebview>=6", "plyer>=2.1"]
  dev = ["pytest>=8", "pytest-cov", "ruff", "mypy"]
  ```
- Add a `solarrt-desktop` console script (`solarrt.desktop:main`).
- Pin Docker base images by digest; let Dependabot/Renovate update them.

**Acceptance**
- `docker compose build` and `pip install -e ".[dev,desktop]"` both work.
- CI runs the chosen Python versions.
- `pip check` is clean.

---

### - [x] P1-4 · Add lint, format and type checking
**Priority:** P1 · **Effort:** M · **Files:** `pyproject.toml`, `.editorconfig`,
`.pre-commit-config.yaml`, `solarrt/` (source code fixes)

**Done:** 24 Nov 2026 — `ruff` (lint + format), `mypy` (type check) installed and configured.
`.editorconfig` (UTF-8, LF for shell/Docker/YAML, CRLF for PowerShell if desired).
`.pre-commit-config.yaml` with hooks for ruff, mypy, pytest. Ruff errors fixed in
`solarrt/noaa.py` (RUF046 unnecessary int() calls). MyPy 5 errors fixed in `solarrt/`.

**Change**
- Python: `ruff` (lint + format), `mypy` or `pyright` on `solarrt/`.
- JS/CSS: ESLint + Prettier, or at minimum `// @ts-check` + JSDoc.
- Replace the blanket warning filter with targeted ignores; migrate tests to
  `httpx.AsyncClient` + `ASGITransport` or the supported `httpx2` path.
- Add `.editorconfig` (UTF-8, LF for shell/Docker/YAML, CRLF for PowerShell if desired).
- Add pre-commit hooks for ruff, prettier and trailing whitespace.

**Acceptance**
- `ruff check .`, `ruff format --check .`, `mypy solarrt` and the JS linter pass.
- `pytest -W error::DeprecationWarning` is clean or has documented narrow ignores.

---

### - [x] P1-5 · Continuous integration and dependency automation
**Priority:** P1 · **Effort:** M · **Files:** `.github/workflows/ci.yml`,
`.github/dependabot.yml`

**Done:** 24 Nov 2026 — `.github/workflows/ci.yml`: matrix Python 3.13/3.14, pytest/ruff/mypy/pip-audit/bandit,
wheel build + smoke-test job. `.github/dependabot.yml`: weekly updates for pip/Docker/Gradle/GitHub Actions.

**Change**
- CI on push/PR:
  - matrix Python 3.13 (and 3.14 if supported),
  - `pytest -q`,
  - `ruff check` + `ruff format --check`,
  - `pip-audit -r requirements.txt`,
  - `bandit -r solarrt`,
  - optional Android debug build (`mobile/build.ps1 -ApiBase ...`) on a runner with the SDK,
  - build the wheel and smoke-test the installed package.
- Dependabot/Renovate for pip, npm, Docker and Gradle.
- Upload coverage to Codecov or keep an artefact.

**Acceptance**
- A deliberately broken test/PR fails CI.
- Dependabot opens a PR for an outdated pin.

---

### - [x] P1-6 · Close the highest-value test gaps
**Priority:** P1 · **Effort:** M–L · **Files:** `tests/`

**Done (items 1–3, 5-part):**
- **TTLCache**: stale-within-limit, stale-expired, concurrent refresh (one loader call), eviction removes locks — 3 tests added (`tests/test_cache.py`).
- **/api/iss**: propagation error → 503; fallback TLE URL; snapshot cache hit — 2 tests added (`tests/test_iss.py`).
- **Feedback forwarding**: one forward, loop marker respected, failure still returns 201 — 1 test added (`tests/test_weather_feedback.py`).
- **Geometry**: `AuroraGrid.max_within` near the poles and across 180°; `summarize_regions` for Alaska/Russia/NZ bounds — 5 tests added (`tests/test_regions.py`).
- **Weather DST**: Europe/London spring-forward test covers the transition — 2 tests added (`tests/test_weather_feedback.py`).

**Remaining:** API contract snapshot tests (P1-8 prerequisite); frontend pure function extraction (P1-7 prerequisite).

---

### - [ ] P1-7 · Split `app.js` into maintainable modules
**Priority:** P1 · **Effort:** L · **Files:** `solarrt/static/app.js` (all 1,080 lines),
`solarrt/static/index.html`, tests

**Problem**
Map, tiles, ISS, clouds, weather, alerts, feedback, clock, theme, first-run and startup all
live in one IIFE with mutable module-level state. It is hard to test or safely modify, and
every new feature makes it worse.

**Change**
- Convert to ES modules loaded with `<script type="module" src="/static/app.js">`
  (CSP `script-src 'self'` already allows this; no inline code).
- Suggested split:
  ```
  static/js/api.js        fetch wrapper + error shape
  static/js/state.js      shared state + localStorage helpers
  static/js/time.js       formatting + zones
  static/js/map.js        Leaflet setup, basemap, night polygon, aurora tiles
  static/js/location.js   IP/GPS/search/pick + location card
  static/js/kp.js         Kp card + chart
  static/js/iss.js        tracker, interpolation, layer
  static/js/clouds.js     WMS layer
  static/js/weather.js    weather rendering
  static/js/alerts.js     evaluation, notifications, cooldown
  static/js/ui.js         theme, clock, dialogs, toasts, feedback
  static/js/main.js       startup + refresh loops
  ```
- Keep the same file paths served under `/static/`; update `revalidate_ui` if needed.
- Add JSDoc types to the pure functions as they move.

**Acceptance**
- No behaviour change; manual smoke test of every card.
- Pure functions are imported by unit tests.
- `index.html` contains no inline script; CSP test still passes.

---

### - [ ] P1-8 · API response models and versioning
**Priority:** P1 · **Effort:** M · **Files:** `solarrt/api.py`, new `solarrt/models.py`,
`solarrt/static/app.js`, docs

**Problem**
Endpoints return untyped dicts, so OpenAPI does not describe responses and a shape change is
invisible until a client breaks. The distributed Android app has no forced-update path.

**Change**
- Add Pydantic models for: health, Kp summary, aurora, regions, location, weather, clouds,
  ISS, geocode/reverse, feedback.
- Mount routes under `/api/v1`; keep `/api` as an alias for at least one release.
- Add a deprecation note in `docs/DEPLOY.md` and a compatibility table.
- Consider `X-API-Version` or a `/api/version` endpoint.

**Acceptance**
- `/openapi.json` shows response schemas.
- Existing `/api/*` tests keep passing.
- Mobile app continues to work against `/api/*`.

---

### - [ ] P1-9 · Make the mobile build reproducible and release-safe
**Priority:** P1 · **Effort:** M · **Files:** `mobile/build.ps1`,
`mobile/capacitor.config.json`, `mobile/package.json`, `.gitignore`

**Problem**
`build.ps1` rewrites the tracked `capacitor.config.json` in place; the committed file has
`"cleartext": true`. A manual `npx cap sync` can therefore ship a cleartext release. The script
also copies `index.html` twice (`www/index.html` and `www/static/index.html`) and does not run
the Python tests.

**Change**
- Add `mobile/capacitor.config.template.json`; generate `mobile/capacitor.config.json` at build
  time and gitignore it.
- In `-Release`, fail if `apiBase` is not `https://` **and** assert `server.cleartext == false`
  after generation.
- Run `pytest -q` before copying assets (same guard as `packaging/build.ps1`).
- Copy only referenced files; drop the duplicate `static/index.html`.
- Add an optional `-Verify` switch that calls `GET {ApiBase}/api/health` and prints the
  version/edition.
- Pin `npx cap sync` to the local CLI (`npx --no-install cap sync android`) to avoid
  downloading a different version.

**Acceptance**
- Release build with an `http://` base fails with a clear message.
- Generated config is not tracked; `git status` is clean after a build.
- Debug build still works on the emulator and a real phone.

---

### - [ ] P1-10 · Fix desktop single-instance and port fallback
**Priority:** P1 · **Effort:** M · **Files:** `solarrt/desktop.py`

**Problem**
If port 47811 is busy, `pick_port()` silently chooses a random port. WebView storage is
origin-bound, so the user’s saved location disappears. Launching twice opens two servers.

**Change**
- Before picking a port, probe `http://127.0.0.1:47811/api/health`:
  - if it is SolarRT, focus/open that instance and exit;
  - otherwise show a clear message and exit (do not silently lose the location).
- On Windows, add a named mutex (`CreateMutexW`) as a second guard.
- Keep the random-port fallback only behind an explicit `--port 0`/debug flag.

**Acceptance**
- Double-clicking the exe twice results in one window.
- Killing the app and relaunching keeps the saved location.
- An unrelated service on 47811 produces an actionable message.

---

### - [ ] P1-11 · Centralise shared thresholds and constants
**Priority:** P1 · **Effort:** S–M · **Files:** new `solarrt/constants.py`, `solarrt/config.py`,
`solarrt/api.py`, `solarrt/static/app.js`, `index.html`, docs

**Problem**
800 km, 5/10/15/30/50 % levels, −12° darkness, 30 % cloud, 10 km visibility and the 3-hour
cooldown appear in several of `regions.py`, `weather.py`, `api.py`, `app.js`, `index.html`
and the README. Changing one leaves the others stale.

**Change**
- Define named constants once (server side).
- Expose the user-facing ones in an endpoint (e.g. include `nearby_radius_km` in
  `/api/location`, which already returns it) or generate a small `static/js/constants.js`.
- Replace hard-coded numbers in the FAQ/alert/form text with generated or documented values.

**Acceptance**
- A grep for `800` finds only the constant and docs that intentionally quote it.
- Changing the radius in one place updates the API, UI copy and tests.

---

### - [ ] P1-12 · Verify the wheel/sdist actually contains the UI
**Priority:** P1 · **Effort:** S · **Files:** `pyproject.toml`, `MANIFEST.in` (new),
`Dockerfile`, CI

**Problem**
`[tool.setuptools.package-data] solarrt = ["static/**/*"]` may not include nested
`static/vendor/leaflet/images/*` in every setuptools version. PyInstaller and Docker copy the
source tree, so the problem would only appear for `pip install solarrt` users.

**Change**
- Build `sdist` and `wheel`; install the wheel into a clean venv; import the app and request
  `/`, `/static/app.js`, `/static/vendor/leaflet/leaflet.js` and a Leaflet marker image.
- Add `MANIFEST.in` (`recursive-include solarrt/static *`) if the sdist is incomplete.
- Add this check to CI.

**Acceptance**
- Clean-venv install serves the complete UI with no 404s.

---

# P2 — Privacy, security, compliance and operations

### - [ ] P2-1 · Give the upstream User-Agent a contact
**Priority:** P2 · **Effort:** S · **Files:** `solarrt/config.py`, `docs/SECURITY.md`

**Problem**
`User-Agent` is `SolarRT/2.0.0 (aurora monitor)`. OpenStreetMap’s Nominatim usage policy
requires an identifying contact (URL or e-mail).

**Change**
Make it configurable:
```python
user_agent: str = os.environ.get(
    "SOLARRT_USER_AGENT",
    f"SolarRT/{__version__} (+https://YOUR-DOMAIN; YOUR-EMAIL)")
```
Use **D4**. Document the requirement in `docs/DEPLOY.md`.

**Acceptance**
- The deployed server sends a UA with a reachable contact.
- A startup warning is logged if the placeholder domain/e-mail is still present.

---

### - [ ] P2-2 · Strengthen the privacy policy
**Priority:** P2 · **Effort:** S · **Files:** `solarrt/static/privacy.html`, `docs/LAUNCH_CHECKLIST.md`

**Problem**
The policy says “contact us through the feedback form” and “keeps answers … for up to 24
hours”. The actual TTLs are 60 s (Kp), 5 min (aurora), 10 min (weather) and 24 h (geocode);
the policy should be precise. GDPR/Play Store reviewers expect a controller contact.

**Change**
- Add a real contact e-mail (and postal/controller details if applicable).
- Replace the broad cache sentence with the actual TTLs, or say “from one minute to 24 hours
  depending on the feed”.
- Mention that the desktop app forwards feedback to the hosted server when configured.
- Add an “effective date / changes” note (already present) and a retention statement (already
  present — keep it accurate).

**Acceptance**
- A reviewer can identify who controls the data and how to contact them.
- Every claim matches `solarrt/config.py` TTLs and `feedback.py` retention.

---

### - [ ] P2-3 · Verify map and cloud attribution
**Priority:** P2 · **Effort:** S · **Files:** `solarrt/static/app.js` (tile attribution),
`index.html` footer, `docs/DEPLOY.md`

**Problem**
The basemap credit is “Esri · OpenStreetMap · NOAA SWPC · CelesTrak”. ArcGIS Online basemaps
often require additional credits (e.g. HERE, Garmin, USGS, …) depending on the layer.
EUMETSAT’s WMS terms may also require a specific credit/link.

**Change**
- Read the current Esri terms for `World_Dark_Gray_Base`/`Reference` and add the required
  credit line.
- Confirm EUMETSAT’s required attribution for `mumi:worldcloudmap_ir108`.
- Keep the credits visible on the map and in the footer.

**Acceptance**
- Credits match the providers’ current requirements; noted in `docs/DEPLOY.md`.

---

### - [ ] P2-4 · Decide and document the CORS story
**Priority:** P2 · **Effort:** S–M · **Files:** `solarrt/api.py`, `mobile/capacitor.config.json`,
`docs/ANDROID.md`

**Problem**
The Android app works because `CapacitorHttp` is enabled and bypasses CORS. A plain web
client, a PWA on another origin, or a future iOS wrapper without that plugin will fail. There
is no `Access-Control-Allow-Origin` anywhere.

**Change**
- Document the CapacitorHttp assumption in `docs/ANDROID.md` and `docs/DEPLOY.md`.
- Optionally add `SOLARRT_CORS_ORIGINS` (comma-separated, default empty) and a small
  CORSMiddleware configuration. Never use `*` with credentials; the API uses no cookies.
- Add a test for an allowed and a disallowed origin.

**Acceptance**
- The current Android app still works.
- A documented origin can call the API from a browser; others are rejected.

---

### - [ ] P2-5 · Correct HTTP caching headers
**Priority:** P2 · **Effort:** S · **Files:** `solarrt/api.py` (`revalidate_ui`),
`solarrt/security.py`

**Problem**
- API responses carry no `Cache-Control`, so intermediaries may cache coordinate-bearing
  URLs.
- `/static/vendor/*` gets only heuristic caching; Leaflet is never revalidated or hashed.
- Geocode/reverse vary by `Accept-Language` but do not send `Vary`.

**Change**
- `Cache-Control: no-store` (or `private, max-age=0`) for `/api/*`.
- `Cache-Control: public, max-age=31536000, immutable` for `/static/vendor/*`; add a content
  hash to the URL or accept manual cache busting on upgrades.
- `Vary: Accept-Language` on `/api/geocode` and `/api/reverse`.
- Keep `no-cache` for UI files.

**Acceptance**
- Header tests cover API, UI, vendor and language-varying endpoints.
- Reloading after a UI update still fetches the new `app.js`.

---

### - [ ] P2-6 · Add a root security policy
**Priority:** P2 · **Effort:** S · **Files:** new `SECURITY.md` (repo root)

**Problem**
`docs/SECURITY.md` is an internal review. There is no reporting policy for researchers, and
“use the feedback form” is not a private channel.

**Change**
- Add a root `SECURITY.md` with supported versions, a private contact (e-mail and/or GitHub
  Security Advisories), scope, and a “please do not open a public issue” note.
- Link it from `README.md` and the About dialog if appropriate.

**Acceptance**
- GitHub shows the “Report a vulnerability” entry; a researcher can find the contact in one
  click.

---

### - [ ] P2-7 · Make proxy and host trust explicit
**Priority:** P2 · **Effort:** S–M · **Files:** `solarrt/security.py`, `solarrt/config.py`,
`Dockerfile`, `deploy/configure.sh`, `docs/DEPLOY.md`

**Problem**
Rate limiting depends on `request.client.host`, which is only the real visitor IP because the
container runs uvicorn with `--proxy-headers --forwarded-allow-ips='*'` and is not published.
Deploying differently silently makes every visitor share one bucket. `SOLARRT_ALLOWED_HOSTS`
defaults to `*`.

**Change**
- Document the required uvicorn flags and the “never publish port 8000” rule.
- Add a startup warning when `allowed_hosts == ("*",)` and the server is not bound to
  loopback.
- In `deploy/configure.sh`, derive `SOLARRT_ALLOWED_HOSTS` from `SOLARRT_DOMAIN` automatically.
- Consider a `SOLARRT_TRUSTED_PROXIES` setting instead of `*`.

**Acceptance**
- A misconfigured public bind logs a clear warning.
- The deploy script cannot create an `.env` where the host allow-list and domain disagree.

---

### - [ ] P2-8 · Paginate or stream the feedback reader
**Priority:** P2 · **Effort:** S–M · **Files:** `solarrt/api.py` (`list_feedback`),
`solarrt/feedback.py`

**Problem**
`GET /api/feedback` loads the whole JSONL file (up to 20 MB) and returns every entry on each
call. Admin-only, but still a memory/latency spike.

**Change**
- Add `?limit=100&before=<id|time>` (or `since`) and return `{count, average, by_rating,
  entries, next_cursor}`.
- Read the file line-by-line and stop once enough entries are collected for the summary, or
  keep a small in-memory index/counter updated on `add()`.
- Keep the full read available via an explicit `?all=1` for backups/debugging.

**Acceptance**
- Default response is bounded; an admin can page through all entries.
- Existing summary fields remain available.

---

### - [ ] P2-9 · Add request IDs and a deeper status endpoint
**Priority:** P2 · **Effort:** M · **Files:** `solarrt/api.py`, `solarrt/security.py`,
`solarrt/cache.py`, `docs/DEPLOY.md`

**Problem**
Logs cannot correlate a user-visible error with the upstream failure that caused it, and
`/api/health` only says the process is up. There is no way to see “NOAA is failing” without
reading logs.

**Change**
- Add a request ID (UUID) in a middleware, return it as `X-Request-ID`, and include it in log
  lines. Never log the URL for `/api/*`.
- Add `/api/status` (admin token) returning cache ages, last upstream error kinds (no URLs or
  coordinates), version, uptime and stale flags.
- Keep `/api/health` fast and unauthenticated for uptime monitors.

**Acceptance**
- A 503 body includes a request ID that matches the log line.
- `/api/status` shows cache ages; it never contains coordinates or search text.

---

### - [ ] P2-10 · Tighten the supply chain
**Priority:** P2 · **Effort:** S–M · **Files:** `Dockerfile`, `requirements*.txt`,
`.github/dependabot.yml`, docs

**Change**
- Pin base images by digest (`python:3.13-slim@sha256:...`,
  `caddy:2.10-alpine@sha256:...`).
- Install Python dependencies from a hashed lock file (`--require-hashes`).
- Keep `package-lock.json` and commit it (already present).
- Optionally generate an SBOM (Syft) in CI and attach it to releases.
- Re-run `pip-audit` and `npm audit` before each release.

**Acceptance**
- Docker build fails if a dependency hash changes unexpectedly.
- Dependabot PRs are the only routine way pins move.

---

# P3 — UX, product, accessibility and performance

### - [ ] P3-1 · Add a PWA shell (cheap iPhone/Android win)
**Priority:** P3 · **Effort:** S–M · **Files:** `solarrt/static/index.html`,
new `solarrt/static/manifest.webmanifest`, `packaging/make_icon.py`, `mobile/build.ps1`

**Problem**
The app has no web manifest, `apple-touch-icon` or `theme-color`. The documented iPhone flow
(“Share → Add to Home Screen”) produces a generic Safari shortcut. Android users cannot
install the website as an app.

**Change**
- Generate 192×192 and 512×512 PNG icons (plus a 180×180 `apple-touch-icon`) from the existing
  SVG/ICO.
- Add `manifest.webmanifest` with `name`, `short_name`, `start_url: "/"`,
  `display: "standalone"`, `background_color`, `theme_color`, icons and a maskable icon.
- Link it from `index.html`; add `<meta name="theme-color">` for light/dark.
- Include the manifest and icons in the Capacitor copy (they are under `static/`).

**Acceptance**
- Lighthouse installability passes for the website.
- iOS Add to Home Screen shows the SolarRT icon and a standalone window.
- The Android app still builds and looks unchanged.

---

### - [ ] P3-2 · Reset alert cooldowns when the location changes
**Priority:** P3 · **Effort:** S · **Files:** `solarrt/static/app.js` (`checkAlerts`,
`showLocation`)

**Problem**
`alertCfg.last` is global and persisted. Move to a new city, and an active alert for the old
place suppresses alerts at the new place for up to three hours.

**Change**
- Clear `alertCfg.last` when the saved location changes (or key it by rounded lat/lon).
- Keep the cooldown when only the theme/timezone changes.
- Add a small “alerts since HH:MM” note if useful.

**Acceptance**
- Selecting a new location can alert immediately.
- Staying at the same location respects the cooldown.

---

### - [ ] P3-3 · Say “now” when it is already dark and clear
**Priority:** P3 · **Effort:** S · **Files:** `solarrt/weather.py`, `solarrt/static/app.js`

**Problem**
`next_dark_clear` always returns the next hourly slot, so even if it is dark and clear right
now the card says “Next dark & clear sky: 23:00”.

**Change**
- If `dark_now && clear_now`, return/flag `"now"` and render “Dark and clear right now”.
- Otherwise keep the next-hour logic.
- Add a test for both branches.

---

### - [ ] P3-4 · Do not draw the ISS at Null Island
**Priority:** P3 · **Effort:** S · **Files:** `solarrt/static/app.js` (`setIss`, `fetchIss`)

**Problem**
`setIss(true)` adds the marker/ring layer before `fetchIss()` resolves, so a marker and a
1 km footprint flash at 0°,0° until the request completes. If the request fails, it stays
there.

**Change**
- Fetch first; add the layer only after a successful response.
- On failure, keep the card hidden/empty and show the existing error status.
- On toggle off, remove the layer as today.

**Acceptance**
- No marker at 0°,0° on a slow or failed ISS request.
- Toggling on/off repeatedly leaves exactly one layer.

---

### - [ ] P3-5 · Add fallbacks for `color-mix()`
**Priority:** P3 · **Effort:** S · **Files:** `solarrt/static/app.js` (`renderWeather`),
`solarrt/static/styles.css` (smileys)

**Problem**
`color-mix()` requires Chrome 111+ (2023). Older Android WebViews render an invalid background
and the 24-hour cloud strip/smiley highlight disappears.

**Change**
- Set a solid fallback first, then the `color-mix()` value:
  ```js
  s.style.background = "var(--accent)";
  s.style.background = `color-mix(in srgb, var(--muted) ${cl}%, var(--accent))`;
  ```
- Same pattern in the smiley selected state.

**Acceptance**
- In a browser/WebView without `color-mix`, the strip and smileys remain visible.

---

### - [ ] P3-6 · Accessibility pass
**Priority:** P3 · **Effort:** M · **Files:** `solarrt/static/index.html`, `styles.css`,
`app.js`

**Problem**
- No `prefers-reduced-motion` guard for toast/transition/map animations.
- The smiley radiogroup has `role="radio"` but no arrow-key navigation or roving tabindex.
- Search results lack `aria-live` and arrow-key selection.
- `#map` has no accessible name; the wrapper label helps but is not enough.
- Emoji-only buttons rely on platform fonts.

**Change**
- Add `@media (prefers-reduced-motion: reduce)` to disable animations/transitions and use
  `map.flyTo` without animation.
- Implement roving tabindex + ArrowLeft/Right/Up/Down for the smileys.
- Add `aria-live="polite"` to the search results list and arrow-key + Enter handling.
- Add `role="application"`/`aria-label` to the map container, or a visually hidden
  description plus keyboard instructions.
- Run axe or Lighthouse accessibility and fix the findings.

**Acceptance**
- Keyboard-only first run, location pick, alert configuration and feedback submission work.
- Reduced-motion mode has no motion.
- No serious axe violations.

---

### - [ ] P3-7 · Replace emoji icons with an SVG set
**Priority:** P3 · **Effort:** M · **Files:** `solarrt/static/` (new `icons/` or inline sprite),
`index.html`, `app.js`, `styles.css`

**Problem**
🛰/☁/📌/🌙/◐ render inconsistently across Windows, Android and browser versions; some look
like boxes in older WebViews.

**Change**
- Add a small inline SVG sprite (satellite, cloud, pin, moon, sun, alert, feedback) with
  `currentColor`.
- Keep text labels; use `aria-hidden` on decorative SVGs.
- Use the same icons in the map controls, cards and dialogs.

**Acceptance**
- Visual parity on Windows, Android and a desktop browser.
- No CSP changes (inline SVG in HTML is fine; external SVG via `<img>` is same-origin).

---

### - [ ] P3-8 · Improve the mobile “server unreachable” experience
**Priority:** P3 · **Effort:** M · **Files:** `solarrt/static/app.js`, `mobile/build.ps1`,
`docs/ANDROID.md`

**Problem**
The Android app fetches everything from a fixed server compiled at build time. If the server
moves or is down, every card shows a generic error and the only fix is a new APK.

**Change**
- Show a distinct banner: “Can’t reach the SolarRT server — check your connection or the
  server address.”
- Add a retry/backoff and keep the last successful data visible (with the stale chip from
  P0-1).
- Optional: a hidden/advanced settings screen to override the server URL, validated as
  `https://` in release builds, persisted in local storage.
- Document the override and the fixed-build limitation.

**Acceptance**
- Airplane mode produces a clear message, not a broken UI.
- Returning to connectivity recovers automatically without restarting the app.

---

### - [ ] P3-9 · Run in the system tray (desktop roadmap item 8)
**Priority:** P3 · **Effort:** L · **Files:** `solarrt/desktop.py`, new `solarrt/tray.py`,
`packaging/SolarRT.spec`, `packaging/installer.iss`, docs

**Problem**
Alerts only work while the window is open. The roadmap calls for tray mode so alerts keep
working when the window is closed.

**Change**
- Keep the local server running in a background thread.
- Use `pystray` (or a native shell notification icon) with: Open, Test alert, Pause alerts,
  Quit.
- Closing the window hides to tray (first time, show a balloon explaining how to quit).
- Optionally start with Windows (per-user Run key, opt-in in settings).
- Handle a single instance (P1-10) so tray + second launch focuses the window.

**Acceptance**
- With the window closed, an alert still produces a Windows notification.
- Quit from the tray stops the server cleanly.
- Uninstall removes the Run entry and tray shortcut.

---

### - [ ] P3-10 · ISS visible-pass predictions (desktop roadmap item 9)
**Priority:** P3 · **Effort:** L · **Files:** `solarrt/iss.py`, `solarrt/api.py`,
`solarrt/static/` (ISS card), tests

**Problem**
The app shows where the ISS is now, but not the useful question: “When can I see it from
here?”

**Change**
- Add `passes(lat, lon, hours=48, min_elevation=10)` to `IssTracker`:
  - sample the orbit at 10–30 s, compute topocentric elevation/azimuth,
  - find rise/culmination/set above `min_elevation`,
  - keep passes where the station is sunlit (existing `iss_sunlit`) and the observer is dark
    (sun elevation < −6 or −12),
  - return start/peak/end times, max elevation, azimuth, duration, brightness hint.
- Endpoint `GET /api/iss/passes?lat=&lon=` cached ~10 min per rounded location.
- UI: “Next visible pass: tonight 21:14, 43° high in the NW, 4 min.”
- Document that predictions are approximate and depend on the TLE age.

**Acceptance**
- Unit tests against a fixed TLE and observer produce a plausible pass (or none) and never
  raise on polar/antimeridian observers.
- The UI handles “no visible passes in the next 48 h”.
- Response includes the TLE epoch so users can judge freshness.

---

### - [ ] P3-11 · Solar wind and X-ray panels (desktop roadmap item 10)
**Priority:** P3 · **Effort:** L · **Files:** `solarrt/noaa.py`, `solarrt/api.py`,
`solarrt/static/` (new card), tests + fixtures

**Problem**
The Kp index is a consequence; the drivers (Bz, speed, density, X-ray flux) are missing. The
original SolarRT had them and the roadmap lists them.

**Change**
- Add parsers + fixtures for:
  - DSCOVR/ACE solar wind plasma (speed, density, temperature),
  - interplanetary magnetic field (Bz, Bt),
  - GOES primary X-ray flux (0.05–0.4 nm, 0.1–0.8 nm) with flare class (A/B/C/M/X).
- Expose `GET /api/solar-wind` and `GET /api/xray` (or one `/api/space-weather`) with TTLs,
  stale handling and source timestamps.
- UI: a compact “Solar wind” card (Bz negative and speed high = good for aurora) and a flare
  indicator with class/colour.
- Keep the same graceful-degradation behaviour as Kp.

**Acceptance**
- Fixture tests for each parser, including missing/NaN values.
- Cards show stale/age (P0-1) and never break the page if a feed is down.
- Docs and FAQ explain what Bz/speed mean in plain language.

---

### - [ ] P3-12 · Performance cleanups
**Priority:** P3 · **Effort:** M · **Files:** `solarrt/static/app.js`, `solarrt/api.py`,
`solarrt/cache.py`

**Problem / change**
1. **Aurora tiles:** `AuroraLayer.createTile` calls `map.unproject` twice per 4 px cell
   (~4,096 calls per tile per redraw). Precompute latitude per pixel row and longitude per
   column, and use an 8 px step below zoom 4. Measure with the browser profiler.
2. **Nominatim lock:** `nominatim()` holds the global lock during the HTTP request; one slow
   call blocks all searches. Use a token bucket that reserves the 1 req/s slot, releases the
   lock, then performs the request.
3. **Audio context:** `beep()` creates a new `AudioContext` per alert. Reuse one and suspend it
   when idle.
4. **Health/allocation:** avoid re-parsing the TLE for `tle.epoch` on every snapshot; cache the
   epoch on `IssTracker`.
5. **Static caching:** covered by P2-5; measure Lighthouse before/after.

**Acceptance**
- A before/after note in the PR with timings for a 3×3 tile area at zoom 3 and zoom 6.
- No functional change; all tests pass.

---

# P4 — Documentation, legal and release polish

### - [ ] P4-1 · Bring the docs in line and add screenshots
**Priority:** P4 · **Effort:** S–M · **Files:** `README.md`, `docs/USER_GUIDE.md`,
`docs/DEPLOY.md`, `docs/ANDROID.md`, `docs/SECURITY.md`, `docs/LAUNCH_CHECKLIST.md`

**Change**
- Fix the ISS window (P0-2) and any other drift found.
- Add 2–3 screenshots (light/dark, map + cards) under `docs/images/` and reference them from
  the README.
- Add a short architecture diagram (ASCII is fine) showing browser/desktop/Android → FastAPI →
  NOAA/Open-Meteo/EUMETSAT/CelesTrak/Nominatim/Esri.
- Refresh `docs/SECURITY.md` after P2 items land (test counts, headers, known limitations).
- Add a “Known limitations” section to the README (alerts only while open; forecast accuracy;
  mobile needs a server).

**Acceptance**
- A new reader can go from clone to running app using only the README.
- Every quoted number matches the code.

---

### - [ ] P4-2 · Choose and add a licence
**Priority:** P4 · **Effort:** S · **Files:** new `LICENSE`, `README.md`, `pyproject.toml`,
`packaging/installer.iss`

**Problem**
“Free to use” is not a licence. Without one, others cannot legally reuse or contribute.

**Change**
- Choose **D3** (MIT or Apache-2.0). Add `LICENSE`, the `license` field in `pyproject.toml`,
  a README badge/section, and the licence text in the installer/About dialog if appropriate.
- Keep the author credit requirement if desired (e.g. MIT’s copyright notice).

**Acceptance**
- GitHub detects the licence; the package metadata declares it.

---

### - [ ] P4-3 · Add project hygiene files
**Priority:** P4 · **Effort:** S · **Files:** new `CHANGELOG.md`, `CONTRIBUTING.md`,
`.editorconfig`, `.pre-commit-config.yaml`, `.github/ISSUE_TEMPLATE/*`

**Change**
- `CHANGELOG.md` in Keep a Changelog format, starting with 2.0.0.
- `CONTRIBUTING.md`: setup, tests, style, PR expectations, security reporting (link
  `SECURITY.md`).
- Issue templates: bug report (with version/edition/platform, log location), feature request.
- `.editorconfig` as described in P1-4.
- Document the release process: bump version in one place (P1-2), run tests, build, tag, deploy.

**Acceptance**
- A contributor can follow `CONTRIBUTING.md` without asking questions.
- The changelog has entries for every release after 2.0.0.

---

### - [ ] P4-4 · Sign the Windows build
**Priority:** P4 · **Effort:** M · **Files:** `packaging/build.ps1`, `packaging/installer.iss`,
docs

**Problem**
Unsigned executables trigger SmartScreen warnings, which will lose a large share of desktop
users.

**Change**
- Obtain a code-signing certificate (OV/EV or a cloud signing service).
- Sign `SolarRT.exe` and the installer with `signtool` (timestamped).
- Add the signing step to `build.ps1` behind a config/env check; document the secrets
  handling.
- Optionally sign the Android APK/AAB (already documented) and publish checksums.

**Acceptance**
- `Get-AuthenticodeSignature` reports `Valid` for both binaries.
- SmartScreen no longer warns on a fresh Windows VM.

---

### - [ ] P4-5 · Update the launch checklist as items land
**Priority:** P4 · **Effort:** S · **Files:** `docs/LAUNCH_CHECKLIST.md`

**Change**
- Tick off the completed backlog items (CI, licence, security policy, privacy contact, PWA,
  signing).
- Add checks for: stale banner, API v1, mobile release build assertion, feedback pagination,
  attribution verification.
- Keep the checklist as the final go-live gate.

**Acceptance**
- Every checklist line has either ✅ or a clear owner/action.

---

# Suggested execution order

Each batch is independently shippable and leaves the app working.

### Batch A — Trust fixes (P0)
`P0-1` → `P0-2` → `P0-3` → `P0-4` → `P0-5` → `P0-6` → `P0-7`

**Done when:** tests pass; stale data is visible and bounded; ISS/weather are correct; no
coordinates in errors; forwarding cannot loop.

### Batch B — Repository and release foundation
`P1-1` → `P1-2` → `P1-3` → `P1-4` → `P1-5` → `P1-12`

**Done when:** git tag exists; CI is green; version/deps have one source; a wheel install
serves the UI.

### Batch C — Test the risky paths
`P1-6` (items 1–6 first, frontend tests after P1-7)

**Done when:** cache/ISS/geometry/weather/forwarding are covered and coverage is reported.

### Batch D — Frontend and API evolution
`P1-7` → `P1-8` → `P1-9` → `P1-10` → `P1-11`

**Done when:** `app.js` is modular, `/api/v1` exists, mobile builds are reproducible, desktop
is single-instance, constants are shared.

### Batch E — Privacy, security and operations
`P2-1` → `P2-2` → `P2-3` → `P2-4` → `P2-5` → `P2-6` → `P2-7` → `P2-8` → `P2-9` → `P2-10`

**Done when:** contact info is correct, headers/CORS are deliberate, logs are correlatable,
the supply chain is pinned.

### Batch F — UX and product
`P3-1` → `P3-2` → `P3-3` → `P3-4` → `P3-5` → `P3-6` → `P3-7` → `P3-12`

**Done when:** PWA works, accessibility passes, no visual compatibility bugs, tiles are
fast.

### Batch G — Roadmap features
`P3-8` → `P3-9` → `P3-10` → `P3-11`

**Done when:** the mobile app degrades gracefully, tray mode works, ISS passes and solar-wind
panels ship behind tests and docs.

### Batch H — Release polish
`P4-1` → `P4-2` → `P4-3` → `P4-4` → `P4-5`

**Done when:** README/screenshots are current, licence and changelog exist, binaries are
signed, and the launch checklist is complete.

---

## Verification recipes

### Run the app and hit the main endpoints

```powershell
.venv\Scripts\python -m solarrt --port 8777
# another shell:
Invoke-RestMethod http://127.0.0.1:8777/api/health
Invoke-RestMethod "http://127.0.0.1:8777/api/location?lat=64.84&lon=-147.72"
Invoke-RestMethod "http://127.0.0.1:8777/api/weather?lat=64.84&lon=-147.72"
Invoke-RestMethod "http://127.0.0.1:8777/api/iss?lat=64.84&lon=-147.72"
```

### Test stale behaviour without the internet

Use `httpx.MockTransport` (see `tests/conftest.py:fake_noaa`) and a loader that raises. Freeze
`time.monotonic` with `monkeypatch` to cross the TTL and the max-stale boundary.

### Test the frontend

Add Vitest for the pure modules, then a single Playwright test:

```powershell
npm install --save-dev vitest @playwright/test
npx playwright install chromium
```

Start the server on a random port and point Playwright at it. Do not call live upstream
services in tests; intercept with `page.route`.

### Build the desktop app

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build.ps1
```

Requires Inno Setup 6 for the installer step. The script runs pytest first.

### Build the Android app

```powershell
powershell -ExecutionPolicy Bypass -File mobile\build.ps1 -ApiBase http://10.0.2.2:8000
```

Release builds require HTTPS and `mobile/keystore.properties` (see `docs/ANDROID.md`).

---

## Risk notes

- **Do not rename or reshape API fields** until `/api/v1` exists and the mobile app has a
  migration plan. Older APKs cannot be updated remotely.
- **Do not add a service worker with aggressive caching** without a cache-busting strategy;
  users can get stuck on an old `app.js`.
- **Do not change the CSP** to allow inline scripts or arbitrary origins; it is a core
  protection and a tested invariant.
- **Do not log URLs** for `/api/*`; coordinates and search text are in query strings.
- **Do not serve stale data forever** after P0-1; a weather forecast from yesterday is worse
  than an honest error.
- **Be careful with time zones**; DST transitions and half-hour offsets are the usual source of
  “the aurora time is wrong” reports.
- **Test on a phone**, not only the desktop browser; WebView versions and `color-mix`,
  `dialog`, `:has`, etc. differ.

---

## Session kickoff prompt

Paste this into a new session to resume:

> Read `docs/IMPROVEMENTS.md` in the SolarRT2 repository. Start with Batch A (P0-1 through
> P0-7). Work one item at a time, run `pytest` after each, tick the checkbox with the date, and
> update any docs the change affects. Do not modify the live deployment. If a decision in the
> “Decisions needed” table blocks an item, ask me before proceeding.

---

*End of backlog. Keep this file updated as items are completed; it is the single source of
truth for planned work.*
