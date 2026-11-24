# PyInstaller spec for the SolarRT desktop app.  Build with:  packaging\build.ps1
# Produces a folder build (dist\SolarRT\SolarRT.exe) which the installer then wraps.

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).parent

hidden = (
    collect_submodules("uvicorn")      # uvicorn loads loops/protocols/lifespan by name
    + collect_submodules("webview.platforms.edgechromium")
    + ["webview.platforms.winforms"]
    + collect_submodules("plyer.platforms.win")  # plyer loads its Windows backend by name
    + ["plyer.platforms.win.notification"]
)

a = Analysis(
    [str(ROOT / "launcher.py")],
    pathex=[str(ROOT)],
    datas=[(str(ROOT / "solarrt" / "static"), "solarrt/static")],
    hiddenimports=hidden,
    excludes=["tkinter", "pytest", "PIL", "numpy", "matplotlib"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="SolarRT",
    icon=str(ROOT / "packaging" / "solarrt.ico"),
    version=str(ROOT / "packaging" / "version_info.txt"),
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="SolarRT", upx=False)
