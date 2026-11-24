"""Desktop edition: runs the SolarRT server privately on this computer and shows the
web UI in a native window (Microsoft Edge WebView2 via pywebview).

Run from source:   python -m solarrt.desktop
Packaged build:    SolarRT.exe (see build/ and README)
"""

from __future__ import annotations

import logging
import os
import socket
import sys
import threading
import time
import webbrowser
from logging.handlers import RotatingFileHandler
from pathlib import Path

import uvicorn

from . import APP_NAME, __version__

log = logging.getLogger("solarrt.desktop")


def data_dir() -> Path:
    """Per-user folder for logs and the window's saved settings (e.g. your location)."""
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def setup_logging() -> Path:
    logs = data_dir() / "logs"
    logs.mkdir(exist_ok=True)
    logfile = logs / "solarrt.log"
    handler = RotatingFileHandler(logfile, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handlers: list[logging.Handler] = [handler]
    if sys.stderr is not None:  # windowed .exe builds have no console
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, handlers=handlers,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    return logfile


# A fixed port keeps the page's address the same between launches. The window's storage
# (your saved location) is tied to that address, so a random port would forget it.
PREFERRED_PORT = 47811


def pick_port(preferred: int = PREFERRED_PORT) -> int:
    for port in (preferred, 0):  # fall back to any free port if ours is taken
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
            except OSError:
                log.warning("Port %s is busy; using a random port (saved location won't carry over)", port)
                continue
            return s.getsockname()[1]
    raise RuntimeError("No free local port")


class LocalServer:
    """Uvicorn running in a background thread, bound to localhost only."""

    def __init__(self, port: int) -> None:
        from .api import app  # imported here so start-up errors land in the log

        self.port = port
        self.url = f"http://127.0.0.1:{port}/"
        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_config=None,
                                loop="asyncio", http="h11", ws="none", lifespan="on",
                                access_log=False)
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, name="solarrt-server", daemon=True)

    def start(self, timeout: float = 20.0) -> None:
        self.thread.start()
        deadline = time.monotonic() + timeout
        while not self.server.started:
            if not self.thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("The local SolarRT server failed to start (see log file)")
            time.sleep(0.05)
        log.info("Server listening on %s", self.url)

    def stop(self) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=5)


class DesktopApi:
    """Functions the web UI can call as window.pywebview.api.<name>() in the desktop app."""

    def notify(self, title: str, message: str) -> bool:
        try:
            from plyer import notification
            notification.notify(title=str(title)[:64], message=str(message)[:250],
                                app_name=APP_NAME, timeout=15)
            return True
        except Exception:
            log.exception("Desktop notification failed")
            return False


def message_box(text: str, title: str = APP_NAME) -> None:
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, title, 0x40)  # MB_ICONINFORMATION
    else:
        print(f"{title}: {text}", file=sys.stderr)


def main() -> None:
    logfile = setup_logging()
    log.info("Starting %s %s (desktop)", APP_NAME, __version__)
    # Must be set before solarrt.config is imported (it happens inside LocalServer).
    os.environ.setdefault("SOLARRT_DATA_DIR", str(data_dir()))
    os.environ.setdefault("SOLARRT_EDITION", "desktop")
    # Only answer requests addressed to this PC's loopback name (blocks DNS-rebinding tricks
    # by web pages trying to reach the local server).
    os.environ.setdefault("SOLARRT_ALLOWED_HOSTS", "127.0.0.1,localhost")
    try:
        server = LocalServer(pick_port())
        server.start()
    except Exception as exc:
        log.exception("Startup failed")
        message_box(f"{APP_NAME} could not start:\n{exc}\n\nLog: {logfile}")
        return

    try:
        import webview

        window = webview.create_window(
            f"{APP_NAME} — Aurora & Kp Monitor", server.url,
            width=1360, height=860, min_size=(900, 600), background_color="#070B14",
            js_api=DesktopApi(),
        )
        if window is None:
            raise RuntimeError("WebView window creation failed")
        window.events.closed += server.stop
        webview.start(
            gui="edgechromium" if sys.platform == "win32" else None,
            private_mode=False,  # keep the saved location between runs
            storage_path=str(data_dir() / "webview"),
        )
    except Exception:
        # No WebView2 runtime (or another GUI problem): fall back to the default browser.
        log.exception("Native window unavailable; falling back to the web browser")
        webbrowser.open(server.url)
        message_box(f"{APP_NAME} is open in your web browser.\n\n"
                    "Keep this message open while you use it — press OK to quit.\n\n"
                    "(For the built-in window, install Microsoft Edge WebView2 Runtime.)")
    finally:
        server.stop()
        log.info("Exited")


if __name__ == "__main__":
    main()
