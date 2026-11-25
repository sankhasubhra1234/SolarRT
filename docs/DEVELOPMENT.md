# Development and packaging

## Hosted edition

Cloudflare builds from the `worker` directory on the GitHub `main` branch. Wrangler runs `assets.mjs` to copy the shared browser interface before bundling the Worker. Edit the source in `solarrt/static` when changing the dashboard.

From `worker`, run `npm install`, followed by `npx wrangler dev` for local development. Use `npx wrangler deploy --dry-run` to validate the production bundle. Production bindings and migrations are declared in [the Wrangler configuration](../worker/wrangler.jsonc).

## Python edition on Windows

From the repository root, create a virtual environment and start the local web interface.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt defusedxml
.\.venv\Scripts\python -m solarrt --open
```

The default address is `http://127.0.0.1:8000`. The local API documentation is available at `/docs`. To launch the native desktop window, run `.\.venv\Scripts\python -m solarrt.desktop`.

## Tests

```powershell
.\.venv\Scripts\python -m pytest -q
```

The Python suite uses [saved fixtures](../tests/fixtures) for NOAA forecasts, weather, cloud imagery metadata and orbital elements.

## Windows installer

Install Inno Setup 6 and run the following command from the repository root with the Python environment above in place.

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build.ps1
```

The build script produces the desktop executable under `dist/SolarRT` and the installer under `dist/installer`. The desktop app uses Edge WebView2 and saves its local settings under `%LOCALAPPDATA%\SolarRT`.

[Android build guide](ANDROID.md) · [VPS deployment](DEPLOY.md) · [Launch checklist for self-hosting](LAUNCH_CHECKLIST.md)
