# Build the SolarRT desktop app and (if Inno Setup is installed) its Windows installer.
#   powershell -ExecutionPolicy Bypass -File packaging\build.ps1
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$py = Join-Path $root '.venv\Scripts\python.exe'

Write-Host '==> Running tests'
& $py -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Tests failed - not building.' }

Write-Host '==> Rendering icon'
& $py packaging\make_icon.py

Write-Host '==> Building app with PyInstaller'
& $py -m PyInstaller packaging\SolarRT.spec --noconfirm --clean --distpath dist --workpath build\pyinstaller
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed.' }

$iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
          "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($iscc) {
    Write-Host '==> Building installer with Inno Setup'
    & $iscc packaging\installer.iss
    if ($LASTEXITCODE -ne 0) { throw 'Inno Setup failed.' }
    Write-Host "Done: dist\installer\SolarRT-Setup-2.0.0.exe"
} else {
    Write-Host 'Inno Setup 6 not found - skipped the installer. App folder: dist\SolarRT\SolarRT.exe'
}
