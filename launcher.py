"""Entry script for the packaged desktop app (PyInstaller needs a plain script, not a package module)."""

from solarrt.desktop import main

if __name__ == "__main__":
    main()
