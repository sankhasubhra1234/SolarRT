# Build the SolarRT Android app (APK).
#
#   powershell -ExecutionPolicy Bypass -File mobile\build.ps1 -ApiBase https://solarrt.example.com
#   powershell -ExecutionPolicy Bypass -File mobile\build.ps1 -ApiBase http://10.0.2.2:8000   # emulator -> this PC
#   ... -Release      # signed release APK + AAB (needs mobile\keystore.properties, see docs\ANDROID.md)
#
# The phone app shows the same web UI as the website/desktop app (copied from solarrt\static)
# and fetches all data from the SolarRT server given by -ApiBase.
param(
    [Parameter(Mandatory = $true)][string]$ApiBase,
    [switch]$Release
)
$ErrorActionPreference = 'Stop'
# Windows PowerShell's "-Encoding utf8" adds a byte-order mark that Gradle rejects: write plain UTF-8.
function Write-Utf8([string]$Path, [string]$Text) {
    [System.IO.File]::WriteAllText((Join-Path (Get-Location) $Path), $Text, (New-Object System.Text.UTF8Encoding $false))
}
$mobile = $PSScriptRoot
$root = Split-Path -Parent $mobile
Set-Location $mobile

# --- toolchain (process-local; nothing is changed system-wide)
if (-not $env:JAVA_HOME) {
    $jdk = Get-ChildItem "$env:ProgramFiles\Microsoft" -Directory -Filter 'jdk-21*' -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $jdk) { throw 'JDK 21 not found. Install it with: winget install Microsoft.OpenJDK.21' }
    $env:JAVA_HOME = $jdk.FullName
}
if (-not $env:ANDROID_HOME) { $env:ANDROID_HOME = "$env:LOCALAPPDATA\Android\Sdk" }
if (-not (Test-Path "$env:ANDROID_HOME\platforms")) { throw "Android SDK not found in $env:ANDROID_HOME (see docs\ANDROID.md)" }
$env:Path = "$env:JAVA_HOME\bin;$env:Path"

$ApiBase = $ApiBase.TrimEnd('/')
if ($Release -and -not $ApiBase.StartsWith('https://')) { throw 'Release builds must use an https:// server address.' }
$version = (Get-Content "$root\solarrt\__init__.py" | Select-String '__version__ = "(.+)"').Matches[0].Groups[1].Value

Write-Host "==> Copying web UI (SolarRT $version) and pointing it at $ApiBase"
if (Test-Path www) { Remove-Item -Recurse -Force www }
New-Item -ItemType Directory www | Out-Null
Copy-Item -Recurse "$root\solarrt\static" www\static
Copy-Item "$root\solarrt\static\index.html" www\index.html
$cfg = @{ apiBase = $ApiBase; version = $version } | ConvertTo-Json -Compress
Write-Utf8 'www\static\config.js' "window.SOLARRT_CONFIG = $cfg;`n"

# Plain-http servers (local testing only) need cleartext traffic allowed; https never does.
$cap = Get-Content capacitor.config.json -Raw | ConvertFrom-Json
$cleartext = $ApiBase.StartsWith('http://')
$cap | Add-Member -NotePropertyName server -NotePropertyValue ([pscustomobject]@{ cleartext = $cleartext }) -Force
Write-Utf8 'capacitor.config.json' ($cap | ConvertTo-Json -Depth 10)

Write-Host '==> Syncing Capacitor'
npx cap sync android
if ($LASTEXITCODE -ne 0) { throw 'cap sync failed' }

# Keep the Android version in step with the app version (versionCode from the number, e.g. 2.0.0 -> 20000).
$gradleFile = 'android\app\build.gradle'
$parts = $version.Split('.') + @('0', '0')
$code = [int]$parts[0] * 10000 + [int]$parts[1] * 100 + [int]$parts[2]
$gradle = ([System.IO.File]::ReadAllText((Join-Path (Get-Location) $gradleFile))).TrimStart([char]0xFEFF)
Write-Utf8 $gradleFile ($gradle -replace 'versionCode \d+', "versionCode $code" -replace 'versionName "[^"]*"', "versionName `"$version`"")

Write-Host '==> Building with Gradle'
Push-Location android
try {
    if ($Release) { .\gradlew.bat assembleRelease bundleRelease --no-daemon } else { .\gradlew.bat assembleDebug --no-daemon }
    if ($LASTEXITCODE -ne 0) { throw 'Gradle build failed' }
} finally { Pop-Location }

$out = "$root\dist\android"
New-Item -ItemType Directory -Force $out | Out-Null
if ($Release) {
    Copy-Item android\app\build\outputs\apk\release\app-release.apk "$out\SolarRT-$version.apk" -Force
    Copy-Item android\app\build\outputs\bundle\release\app-release.aab "$out\SolarRT-$version.aab" -Force
    Write-Host "Done: dist\android\SolarRT-$version.apk (sideload) and .aab (Google Play)"
} else {
    Copy-Item android\app\build\outputs\apk\debug\app-debug.apk "$out\SolarRT-$version-debug.apk" -Force
    Write-Host "Done: dist\android\SolarRT-$version-debug.apk (for testing)"
}
