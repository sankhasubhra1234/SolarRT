# SolarRT 2

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A live aurora and geomagnetic-activity monitor that runs as a website and as an installable Windows desktop app.

- **Regional aurora activity**: NOAA's OVATION aurora forecast drawn on an interactive world map, plus a ranked list of aurora-viewing regions (Alaska, Canada, Scandinavia, UK & Ireland, New Zealand, Tasmania…).
- **Kp index**: the current estimate, the last 3-hour value, the 24-hour max, the forecast peak and a chart of 3 days observed plus forecast, coloured by NOAA G-storm level.
- **Your location**: found automatically from your IP address, or precisely with *Locate me*, or by searching a place. It shows the aurora chance at your spot, the strongest aurora within 800 km, and whether the sky is dark enough to see it.
- **ISS live tracker**: the 🛰 ISS button on the map shows the International Space Station moving in real time, with the last 46 minutes of its track, the next 46 minutes (one full orbit), and the area from which it's above the horizon. A card shows its altitude, speed, sunlit or in Earth's shadow, and its distance from you. Positions are calculated from CelesTrak's published orbit data using the SGP4 model, accurate to about 1 km.
- **Clouds & weather**: the ☁ Clouds map button overlays EUMETSAT's worldwide infrared satellite cloud image, updated every 3 hours. The location card shows the local weather from Open-Meteo: cloud cover (low, mid and high), visibility, temperature, a 24-hour cloud strip with night marked, and the next dark and clear hour.
- **Aurora alerts**: you choose what triggers an alert (aurora chance at your location, aurora within 800 km on your horizon, and/or a Kp level) and what sky it needs: *any conditions*, *only when dark*, or *only when dark and clear* (maximum cloud % and optional ≥10 km visibility). Alerts arrive as Windows notifications in the desktop app, browser notifications on the website, plus an in-app pop-up and a beep. There's at most one alert per 3 hours, unless activity gets stronger. Alerts only run while the app is open.
- **Feedback**: rate with five smiley faces (Terrible → Love it) and add an optional comment and contact detail.
- **Light / dark mode**: the header button cycles Auto (follows your system), Light and Dark. It changes the page colours and the map background.
- Day/night shading on the map. The data refreshes itself: Kp every minute, the aurora forecast every 5 minutes, the ISS every second.

Space-weather data comes from the [NOAA Space Weather Prediction Center](https://www.swpc.noaa.gov/), and ISS orbit data from [CelesTrak](https://celestrak.org/).

## Install the desktop app (Windows)

Run `SolarRT-Setup-2.0.0.exe`. It installs just for you, with no admin rights needed, and adds a Start-menu shortcut and an optional desktop shortcut. Uninstall it from *Settings → Apps*.

The desktop app runs the same server privately on your PC (port 47811, localhost only) and shows the app in its own window using Microsoft Edge WebView2, which comes with Windows 10/11. Logs and saved settings are kept in `%LOCALAPPDATA%\SolarRT`.

## Android app

`mobile/` holds the Android app: the same UI and features, with native GPS and notifications. Build it with
`powershell -ExecutionPolicy Bypass -File mobile\build.ps1 -ApiBase <server address>`. The full guide, including
testing on a phone and release signing, is in [docs/ANDROID.md](docs/ANDROID.md).

## Build the desktop app and installer

Requires [Inno Setup 6](https://jrsoftware.org/isinfo.php) for the installer step (`winget install JRSoftware.InnoSetup`).

```powershell
.venv\Scripts\python -m pip install -r requirements.txt
powershell -ExecutionPolicy Bypass -File packaging\build.ps1
```

This runs the tests, renders the icon, builds `dist\SolarRT\SolarRT.exe` with PyInstaller, then builds `dist\installer\SolarRT-Setup-2.0.0.exe`. To run the desktop app from source without building: `.venv\Scripts\python -m solarrt.desktop`.

When releasing a new version, update the version number in `solarrt/__init__.py`, `pyproject.toml`, `packaging/version_info.txt` and `packaging/installer.iss`.

## Run it locally

```powershell
cd SolarRT2
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m solarrt --open
```

The app opens at <http://localhost:8000>. API docs are at <http://localhost:8000/docs>.

Options: `--host 0.0.0.0` to share it on your network, `--port 9000` to use another port, and `--reload` to auto-restart while you edit code.

## Run the tests

```powershell
.venv\Scripts\python -m pytest
```

The tests use saved NOAA responses in `tests/fixtures`, so they don't need the internet.

## Host it as a website

`deploy/` has a ready-to-run production setup for your own VPS: Docker Compose with Caddy for automatic
HTTPS, a server-hardening script, and update and backup scripts. Follow [docs/DEPLOY.md](docs/DEPLOY.md), then
[docs/LAUNCH_CHECKLIST.md](docs/LAUNCH_CHECKLIST.md).

## Documentation

| Document | For |
|---|---|
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | People using SolarRT |
| In-app **FAQ** and [privacy policy](solarrt/static/privacy.html) | People using SolarRT (also linked in the app's bottom bar) |
| [docs/DEPLOY.md](docs/DEPLOY.md) | Putting the server online on a VPS |
| [docs/LAUNCH_CHECKLIST.md](docs/LAUNCH_CHECKLIST.md) | Step-by-step go-live list |
| [docs/SECURITY.md](docs/SECURITY.md) | Security review, protections in place, how to keep it secure |
| [docs/ANDROID.md](docs/ANDROID.md) | Building, signing and publishing the Android app |

## Reading feedback

Feedback is saved as one JSON line per entry in `feedback.jsonl`, inside the data folder (`SOLARRT_DATA_DIR`): `data/` for the website and `%LOCALAPPDATA%\SolarRT` for the desktop app. On the server, set `SOLARRT_ADMIN_TOKEN` and request `/api/feedback` with the header `Authorization: Bearer <your token>` to see every entry with its average rating. The token is never accepted in the URL.

Feedback sent from the desktop app stays on that user's PC until you set `SOLARRT_FEEDBACK_FORWARD_URL` to your hosted site's `/api/feedback` address. That forwards each entry to you.

## Project layout

```
solarrt/
  __main__.py   command-line entry point (python -m solarrt)
  api.py        FastAPI app: /api/* JSON endpoints + serves the web UI
  noaa.py       NOAA feed fetching and parsing, Kp/G-scale helpers, aurora grid, sun position
  regions.py    aurora-viewing regions and their activity summary
  iss.py        ISS position and ground track from TLE + SGP4
  weather.py    local weather summary (Open-Meteo) and cloud-map timestamp
  feedback.py   feedback validation, rate limiting and storage
  security.py   rate limiting, request-size limit, security headers (CSP etc.)
  desktop.py    desktop edition: local server + native window (pywebview)
  cache.py      TTL cache that serves stale data if NOAA is briefly down
  config.py     URLs, cache lifetimes, host/port (SOLARRT_* env vars)
  static/       web UI (index.html, app.js, styles.css, Leaflet)
tests/          pytest suite + saved NOAA / TLE fixtures
packaging/      PyInstaller spec, Inno Setup script, icon, build.ps1
launcher.py     entry script for the packaged exe
```

## API

| Endpoint | Returns |
|---|---|
| `GET /api/kp` | current, last 3 h, 24 h max, forecast peak, chart series |
| `GET /api/aurora` | OVATION grid (360×181, base64 bytes), forecast time |
| `GET /api/regions` | regions ranked by aurora probability |
| `GET /api/location?lat=&lon=` | chance here, nearby max, sky darkness, verdict |
| `GET /api/weather?lat=&lon=` | cloud cover, visibility, 24 h forecast, next dark & clear hour |
| `GET /api/clouds` | cloud map layer (EUMETSAT WMS) and its image time |
| `POST /api/feedback` / `GET /api/feedback` | send feedback / read it (`Authorization: Bearer` admin token) |
| `GET /api/iss?lat=&lon=` | ISS position, altitude, speed, sunlit, track, footprint, distance from you |
| `GET /api/geocode?q=` / `GET /api/reverse?lat=&lon=` | place search (OpenStreetMap Nominatim) |

## Roadmap

1. ✅ Web app: aurora map, regional activity, Kp, user location
2. ✅ Installable Windows desktop app
3. ✅ Light/dark mode and the ISS live tracker
4. ✅ Clouds & weather, aurora alerts (with or without weather conditions), feedback
5. ✅ Android app (debug build tested on Android 16; release needs your signing key and a live server)
6. Go live: hosting, documentation, FAQ, full security review
7. iPhone app (needs a Mac or cloud Mac + Apple Developer account)
8. Run in the system tray so alerts keep working with the window closed
9. ISS pass predictions ("next visible pass over you")
10. Solar wind (Bz, speed) and X-ray flare panels from the original SolarRT
#   S o l a r R T  
 