# Go-live checklist

Work through this in order. ✅ = already done in the project; ☐ = your action.

## Before launch: code & safety
- ✅ Security review done and all findings fixed ([SECURITY.md](SECURITY.md))
- ✅ Dependency audits clean (pip-audit, npm audit); static scan clean (bandit)
- ✅ Automated tests pass (`pytest`: API, data parsing, ISS, weather, feedback, security, privacy)
- ✅ Privacy policy written and linked in the app (`/static/privacy.html`)
- ✅ FAQ in the app, plus a [user guide](USER_GUIDE.md)
- ✅ Coordinates and search text are never written to logs (enforced by a test)
- ☐ Read the privacy policy and confirm it matches how you'll run SolarRT; add a contact e-mail
  if you'd like one shown (recommended under GDPR)

## Server
- ☐ Create the VPS (Ubuntu 24.04) with your SSH key
- ☐ Run `deploy/setup-server.sh`, then confirm you can log in as the new user
- ☐ Upload the code; create `deploy/.env` (domain, allowed hosts, admin token)
- ☐ `docker compose up -d --build` → `docker compose ps` shows the app **healthy**
- ☐ Open `https://<domain>`: page loads, padlock shown, map/Kp/weather/ISS/clouds work
- ☐ Check headers at https://securityheaders.com (expect A or better) and HTTPS at
  https://www.ssllabs.com/ssltest/ (expect A)
- ☐ Read feedback once with the admin token to confirm it's protected and working
- ☐ Set up the daily backup cron and an uptime monitor on `/api/health`

## Apps
- ☐ Android: create the release signing key (back it up!), then build with
  `-ApiBase https://<domain> -Release` and install the APK on a real phone to test
- ☐ Desktop: set `SOLARRT_FEEDBACK_FORWARD_URL=https://<domain>/api/feedback` and rebuild the installer
- ☐ (Optional) Google Play: developer account, privacy policy URL `https://<domain>/static/privacy.html`,
  data-safety form (location: approximate/precise, not stored; feedback: optional, stored), screenshots

## After launch
- ☐ Monthly: `./update.sh` on the server; audits before each release
- ☐ Read and answer feedback; delete feedback older than 24 months (as the privacy policy promises)
