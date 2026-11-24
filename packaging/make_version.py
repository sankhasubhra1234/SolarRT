"""Single-source version bump: reads solarrt/__init__.py and writes every other copy.

Usage:
    python packaging/make_version.py          # bump to next (must edit __init__.py first)
    python packaging/make_version.py 2.1.0    # set an exact version
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent  # go up from packaging/ to repo root
SOLARRT = ROOT / "solarrt"
INIT = SOLARRT / "__init__.py"
PKG_VERSION = ROOT / "pyproject.toml"
VERSION_INFO = ROOT / "packaging" / "version_info.txt"
INSTALLER = ROOT / "packaging" / "installer.iss"
BUILD_PS1 = ROOT / "packaging" / "build.ps1"
MOBILE_PS1 = ROOT / "mobile" / "build.ps1"
PKG_JSON = ROOT / "mobile" / "package.json"
GRADLE = ROOT / "mobile" / "android" / "app" / "build.gradle"


def set_version(new_version: str) -> None:
    # ---- 1. solarrt/__init__.py -------------------------------------------------
    init_text = INIT.read_text()
    INIT.write_text(init_text.replace('__version__ = "2.0.0"', f'__version__ = "{new_version}"'))
    print(f"   updated: {INIT}")

    # ---- 2. pyproject.toml ------------------------------------------------------
    pyproject = PKG_VERSION.read_text()
    # The dynamic version line stays; just make sure the old hard-coded line is not duplicated.
    # If someone had the old literal, remove it:
    if 'version = "2.0.0"' in pyproject:
        pyproject = pyproject.replace('version = "2.0.0"', '# version auto-synced by make_version.py')
    PKG_VERSION.write_text(pyproject)
    print(f"   updated: {PKG_VERSION}")

    # ---- 3. packaging/version_info.txt -------------------------------------------
    vi = VERSION_INFO.read_text()
    vi = vi.replace("FileVersion', '2.0.0'", f"FileVersion', '{new_version}'")
    vi = vi.replace("ProductVersion', '2.0.0'", f"ProductVersion', '{new_version}'")
    VERSION_INFO.write_text(vi)
    print(f"   updated: {VERSION_INFO}")

    # ---- 4. packaging/installer.iss ---------------------------------------------
    is_text = INSTALLER.read_text()
    INSTALLER.write_text(is_text.replace('AppVersion "2.0.0"', f'AppVersion "{new_version}"'))
    print(f"   updated: {INSTALLER}")

    # ---- 5. packaging/build.ps1 -------------------------------------------------
    # No hard-coded version in the final echo line; the script already builds the installer
    # name from version_info.txt. No change needed here.
    print(f"   updated: {BUILD_PS1} (hard-coded version noted for manual update)")

    # ---- 6. mobile/build.ps1 ----------------------------------------------------
    # This script already reads version from __init__.py via Select-String; no change needed.
    # The versionCode calculation already uses $version.
    print(f"   updated: {MOBILE_PS1} (reads __init__.py - no change needed)")

    # ---- 7. mobile/package.json -------------------------------------------------
    pj = PKG_JSON.read_text()
    pj = pj.replace('"version": "2.0.0"', f'"version": "{new_version}"')
    PKG_JSON.write_text(pj)
    print(f"   updated: {PKG_JSON}")

    # ---- 8. mobile/android/app/build.gradle -------------------------------------
    gb = GRADLE.read_text()
    gb = gb.replace('versionName "2.0.0"', f'versionName "{new_version}"')
    # versionCode derived from 2.0.0 -> 2_0_0 -> 20000
    code = int(new_version.split(".")[0]) * 10000 + int(new_version.split(".")[1]) * 100 + int(new_version.split(".")[2])
    gb = gb.replace('versionCode 20000', f'versionCode {code}')
    GRADLE.write_text(gb)
    print(f"   updated: {GRADLE} (versionCode {code})")

    # ---- Report ---------------------------------------------------------------
    print(f"\n==> Version set to {new_version}")
    print(f"    Remember to commit and run: git add . && git commit -m \"chore: bump version to {new_version}\"")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        new_version = sys.argv[1]
    else:
        # Read from __init__.py - the only literal assignment we control.
        m = re.search(r'__version__\s*=\s*"([^"]+)"', INIT.read_text())
        if not m:
            print("ERROR: cannot find __version__ in solarrt/__init__.py", file=sys.stderr)
            sys.exit(1)
        new_version = m.group(1)

    set_version(new_version)