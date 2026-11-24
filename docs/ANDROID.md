# SolarRT for Android

The Android app is a separate, installable app (`com.sdebnath.solarrt`) with the same features as the
website and desktop app: the aurora map, Kp index, regional activity, ISS tracker, clouds and weather,
aurora alerts, local time, light/dark theme and feedback. It uses the SolarRT web UI (`solarrt/static`)
packaged with [Capacitor](https://capacitorjs.com/), plus native phone features:

| Feature | On Android |
|---|---|
| Locate me / welcome prompt | Native location permission and GPS (`@capacitor/geolocation`) |
| Aurora alerts | Native Android notifications (`@capacitor/local-notifications`) with the SolarRT status-bar icon |
| Data | Fetched from your hosted SolarRT server (set at build time with `-ApiBase`) |
| Feedback | Sent to that server, tagged `edition: android` |

> **The app needs a SolarRT server running online.** A phone can't run the Python server itself.
> Until the website is live, test builds can use this PC's server (see *Test on your phone*).

## One-time setup (already done on the development PC)

- JDK 21: `winget install Microsoft.OpenJDK.21`
- Android SDK command-line tools in `%LOCALAPPDATA%\Android\Sdk`, with
  `platform-tools`, `platforms/android-36` and `build-tools/36.1.0`
- Node.js, then `cd mobile && npm install`

## Build

```powershell
# Test build that talks to this PC (Android emulator address for localhost)
powershell -ExecutionPolicy Bypass -File mobile\build.ps1 -ApiBase http://10.0.2.2:8000

# Test build for a real phone on the same Wi-Fi (use this PC's IP address)
powershell -ExecutionPolicy Bypass -File mobile\build.ps1 -ApiBase http://192.168.1.50:8000

# Release build for users (https server required, signing key required, see below)
powershell -ExecutionPolicy Bypass -File mobile\build.ps1 -ApiBase https://your-solarrt-server -Release
```

Output goes to `dist\android\`:
- `SolarRT-<version>-debug.apk` for testing
- `SolarRT-<version>.apk` (signed, for direct download) and `SolarRT-<version>.aab` (for Google Play)

The script copies the web UI into `mobile/www`, writes the server address into `config.js`, syncs
Capacitor and runs Gradle. It also keeps the Android version (`versionName`/`versionCode`) equal to
`solarrt/__init__.py`. Plain `http://` addresses are only allowed in test builds; release builds refuse
them.

## Test on your phone

1. Start the server so other devices on your Wi-Fi can reach it:
   `.venv\Scripts\python -m solarrt --host 0.0.0.0`. Allow Python through Windows Firewall on
   **private** networks only when Windows asks.
2. Build with `-ApiBase http://<this PC's IP>:8000`. Find the IP with `ipconfig`.
3. Copy `dist\android\SolarRT-2.0.0-debug.apk` to the phone and open it. Android asks you to allow
   installing from that source the first time.

On the emulator: `emulator -avd SolarRT_Pixel`, then
`adb install -r dist\android\SolarRT-2.0.0-debug.apk`. `mobile/tools/webview_eval.py` can run
JavaScript inside a debug build for testing.

## Release signing (do this yourself, once)

Android only installs updates signed with the **same key**, so create it once and keep it safe.
**If you lose the key or its password, you can never update the app again.**

## CORS / Capacitor Note

The Android app uses [Capacitor](https://capacitorjs.com/) to host the web UI internally.
- **Test builds** (`-Debug`): Allow `http://` addresses (your PC's IP, `10.0.2.2` for emulator). The `CapacitorHttp` plugin handles CORS internally.
- **Release builds** (`-Release`): **Must use `https://` addresses only**. Release builds refuse `http://` addresses.
- The Caddy reverse proxy on the server trusts `*` for `forwarded-allow-ips` because port 8000 is only reachable on the internal Docker network. For production with a custom domain, ensure your domain has a valid HTTPS certificate (Caddy/Let's Encrypt handles this automatically).
- If you need to customize allowed CORS origins, set `SOLARRT_CORS_ORIGINS` as a comma-separated list in `.env`. The default allows the deployed domain.

```powershell
cd mobile
& "$env:ProgramFiles\Microsoft\jdk-21*\bin\keytool.exe" -genkeypair -v -keystore solarrt-release.jks `
  -alias solarrt -keyalg RSA -keysize 4096 -validity 10000
```

Then create `mobile\keystore.properties` (it's in `.gitignore` and never committed):

```properties
storeFile=solarrt-release.jks
storePassword=YOUR_STORE_PASSWORD
keyAlias=solarrt
keyPassword=YOUR_KEY_PASSWORD
```

Back up `solarrt-release.jks` and the passwords somewhere safe outside this PC, such as a password
manager. For Google Play, enrol in **Play App Signing**: Google keeps the app-signing key, and your
key becomes the upload key, which can be reset if lost.

## Publishing options

- **Direct download:** host the signed `.apk` on the SolarRT website. Users must allow
  "install unknown apps" for their browser.
- **Google Play:** one-time $25 developer registration, then upload the `.aab`. Play requires a
  privacy policy URL, a data-safety form (location: approximate/precise, used on device and sent to
  your server for the forecast; feedback: optional), screenshots and a content rating.

## Limitations

- Alerts are checked while the app is open on screen. Android pauses apps in the background, so
  background alerts would need a push service or a background task, which is on the roadmap.
- The app needs an internet connection; all data comes from the SolarRT server.

## iPhone (later)

The same `mobile` project can add iOS with `npx cap add ios`. Building needs a Mac with Xcode (or a
cloud Mac) and an Apple Developer account ($99/year). The web UI and native plugins used here already
support iOS.
