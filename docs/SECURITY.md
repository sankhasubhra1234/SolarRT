# SolarRT security review

**Reviewed:** 17 November 2026, before going live · **Scope:** web server/API (`solarrt/`), web UI
(`solarrt/static/`), desktop app, Android app (`mobile/`), deployment (`deploy/`, `Dockerfile`)

## How it was checked

| Check | Tool / method | Result |
|---|---|---|
| Known vulnerabilities in Python dependencies | `pip-audit -r requirements.txt` | None found |
| Known vulnerabilities in Android dependencies | `npm audit --omit=dev` | None found |
| Static analysis of Python code | `bandit -r solarrt` | 1 low-confidence warning, a false positive (string comparison, not a socket bind) |
| Manual code review | All API routes, middleware, caches, storage, front-end DOM handling, desktop bridge, mobile config | Findings below, all fixed |
| Browser policy test | Loaded the full app (map, clouds, ISS, weather, dialogs) under the new Content Security Policy | 0 violations; all tiles and features work |
| Automated security tests | `tests/test_security.py` (19 tests) | Pass |

## Findings and fixes

| # | Finding | Severity | Fix |
|---|---|---|---|
| 1 | In-memory caches had no size limit, so requests for endless different places or coordinates could exhaust memory | High | Caches are bounded, with least-recently-used eviction. Per-user data has its own cache, so it can't push out shared NOAA data |
| 2 | Place search shares one 1-request-per-second slot to OpenStreetMap. A flood could stall search for everyone and get the server's IP banned there | Medium | Per-client limit (20/min); queueing for the slot is capped at 10 s |
| 3 | No per-client limit on the API | Medium | 240 requests/min per client (health checks exempt) |
| 4 | Behind the HTTPS proxy, all visitors would share one IP, so the limits would affect everyone at once | Medium | Uvicorn trusts the forwarded visitor IP; the app port is only reachable from the proxy |
| 5 | Admin token was accepted in the URL (ends up in logs and browser history) and compared with `!=` | Medium | Token only in the `Authorization: Bearer` header, compared with `secrets.compare_digest` |
| 6 | Feedback file and its rate-limit table could grow without limit | Medium | 20 MB file cap (then 503) and a bounded rate-limit table |
| 7 | No browser security headers | Medium | Strict CSP (`script-src 'self'`, no inline scripts), `X-Frame-Options: DENY`, `frame-ancestors 'none'`, `nosniff`, Referrer-Policy, Permissions-Policy, COOP; HSTS added by Caddy |
| 8 | Desktop app's local server accepted any `Host`, so a web page could use DNS rebinding to reach it | Low | Host allow-list (`127.0.0.1`, `localhost`); production uses its domain |
| 9 | No request-size limit | Low | 64 KB at the app and at Caddy |
| 10 | `Accept-Language` used unvalidated in cache keys and outgoing requests | Low | Validated against a language-tag pattern, otherwise `en` |
| 11 | Coordinates and search text reached logs (uvicorn access log, httpx URL logging, cache warnings) | Privacy | Access log off; httpx at WARNING; logs carry only the data kind. A test asserts that no coordinates or search text are logged |
| 12 | `/docs` (API explorer) public in production | Info | Off in production (`SOLARRT_ENABLE_DOCS=0`) |

## Design notes (already sound)

- **No user-supplied URLs are fetched** (no SSRF): the server only calls fixed upstream addresses.
- **Front end:** dynamic text is inserted with `textContent`; the one HTML popup escapes values;
  external links use `rel="noopener"`.
- **Input validation:** coordinates are range-checked, search text is length-limited, and feedback is
  validated by a strict model (rating 1–5, comment ≤ 2000, contact ≤ 200).
- **Secrets:** none in the code. The admin token and Android signing passwords live in files excluded from
  git (`deploy/.env`, `mobile/keystore.properties`).
- **Container:** non-root user, read-only filesystem, all Linux capabilities dropped,
  `no-new-privileges`, memory and process limits, no published app port.
- **Server:** SSH keys only, no root login, firewall (22/80/443), automatic security updates, fail2ban
  (`deploy/setup-server.sh`).
- **Desktop:** the window's JavaScript bridge exposes only `notify()`, and the local server listens only on
  `127.0.0.1`.
- **Android:** release builds refuse plain-`http` servers; cleartext and WebView debugging exist only in
  debug builds. Permissions requested: location (coarse/fine), notifications, internet.
- **Pinned versions:** Python packages, npm packages (exact), Leaflet (vendored), Docker base images.

## Known limitations / accepted risks

- Rate limits are per server process and in memory, which is right for a single VPS. Several servers would
  need a shared store (e.g. Redis).
- `style-src 'unsafe-inline'` is needed by the Leaflet map library; scripts stay strict.
- The Docker image wasn't built on the review PC (no Docker installed). Build it and run
  `docker compose ps` on the server as part of going live.
- Third-party services (NOAA, Open-Meteo, EUMETSAT, CelesTrak, Nominatim, Esri) can be unavailable;
  the app serves stale data and degrades gracefully.

## Keeping it secure

- Run `./update.sh` monthly (it rebuilds on the latest patched base image), and whenever dependencies change.
- Before each release: `pip-audit -r requirements.txt`, `cd mobile && npm audit`, `pytest`.
- Rotate `SOLARRT_ADMIN_TOKEN` if it might have leaked (edit `.env`, then `docker compose up -d`).

## Reporting a vulnerability

Please report it privately through the in-app feedback form (choose any rating and describe the issue,
with contact details) rather than publicly.
