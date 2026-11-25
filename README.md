# SolarRT · Solar Real Time

SolarRT helps you decide when to step outside to look for the aurora. Pick a place on the map to compare NOAA’s aurora forecast with local darkness, cloud cover and visibility. The ISS layer shows where the International Space Station is now and where its orbit takes it next.

**[Open SolarRT](https://solarrt.sankhadn.workers.dev/)** · [User guide](docs/USER_GUIDE.md) · [API reference](docs/API.md) · [Release notes](CHANGELOG.md)

## Explore the dashboard

| Question | Where to look |
| --- | --- |
| Where is the aurora strongest? | The OVATION map shows forecast probabilities. The regional list compares 14 viewing areas. |
| Could I see it from here? | Search for a place or pick a point. Compare its overhead probability with activity within 800 km, then check the next dark, clear hour. |
| How active is the geomagnetic field? | The Kp panel shows the current estimate, recent observations and the forecast peak. |
| Where is the ISS? | Toggle the ISS layer to see its position, altitude, visibility footprint and ground track from 46 minutes ago to 46 minutes ahead. |

Aurora alerts use your chosen thresholds while the application is open. The weather panel uses Open-Meteo, the cloud overlay uses EUMETSAT imagery, and the ISS tracker propagates published orbital elements with SGP4.

## Run the web app locally

From the repository root, use Node.js 24 and npm to run the same Worker used by the hosted site.

```sh
cd worker
npm install
npx wrangler dev
```

Open the local URL printed by Wrangler. To check the API, append `/api/health`. Wrangler builds the web assets from [solarrt/static](solarrt/static) and provides local storage for development.

## Find your way around the source

| Directory | Purpose |
| --- | --- |
| [worker](worker) | Hosted API, aurora calculations, ISS propagation, feedback storage and Cloudflare deployment settings |
| [solarrt](solarrt) | Python API, scientific calculations, desktop launcher and shared browser interface |
| [tests](tests) | Python tests and saved observations for repeatable checks |
| [packaging](packaging) | Windows executable and installer build scripts |
| [mobile](mobile) | Capacitor Android project with native location and notifications |
| [deploy](deploy) | Docker Compose, Caddy and maintenance scripts for self-hosting |
| [previews](previews) | Standalone interface experiments |
| [docs](docs) | User, developer and deployment guides |

## Build and operate

- [Development and Windows packaging](docs/DEVELOPMENT.md)
- [Android build and signing](docs/ANDROID.md)
- [Self-hosting the Python server](docs/DEPLOY.md)
- [Security notes](docs/SECURITY.md) and [privacy policy](solarrt/static/privacy.html)

Released under the [MIT License](LICENSE).
