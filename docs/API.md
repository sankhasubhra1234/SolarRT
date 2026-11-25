# SolarRT API

The hosted Worker and the Python server both expose these routes. Coordinates use decimal degrees, with north and east positive.

| Method | Route | Response |
| --- | --- | --- |
| GET | `/api/health` | Service status, application name, version and edition |
| GET | `/api/kp` | Current Kp estimate, recent maximum, forecast peak and chart series |
| GET | `/api/aurora` | Forecast time and a 360 × 181 grid encoded as base64 unsigned bytes |
| GET | `/api/regions` | Viewing regions ranked by maximum aurora probability |
| GET | `/api/location?lat=57.15&lon=-2.09` | Local probability, nearby activity, solar elevation and viewing assessment |
| GET | `/api/weather?lat=57.15&lon=-2.09` | Current weather, hourly outlook and next dark, clear hour |
| GET | `/api/clouds` | EUMETSAT map layer, service URL and image timestamp |
| GET | `/api/iss` | Propagated ISS position, speed, orbital epoch, visibility footprint and ground track |
| GET | `/api/geocode?q=Aberdeen` | Matching place names and coordinates |
| GET | `/api/reverse?lat=57.15&lon=-2.09` | Place name for a coordinate pair |
| POST | `/api/feedback` | Accepts a rating from 1 to 5 and an optional comment or contact detail |
| GET | `/api/feedback` | Feedback summary for an authenticated administrator |

Pass both `lat` and `lon` to the ISS endpoint to include the observer’s distance and whether the station is above the geometric horizon. Forecast and observation timestamps describe the underlying measurements. Endpoints that can serve cached observations include freshness fields.

Feedback administration uses an `Authorization: Bearer <token>` header. The Worker reads its secret from `ADMIN_TOKEN` and stores entries in a SQLite-backed Durable Object. The Python server reads `SOLARRT_ADMIN_TOKEN` and uses a local JSON Lines file.
