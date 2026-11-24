"""Run the SolarRT web app:  python -m solarrt  [--host 0.0.0.0] [--port 8000] [--open]"""

from __future__ import annotations

import argparse
import logging
import threading
import webbrowser

import uvicorn

from .config import settings


def main() -> None:
    parser = argparse.ArgumentParser(prog="solarrt", description="SolarRT aurora monitor web app")
    parser.add_argument("--host", default=settings.host)
    parser.add_argument("--port", type=int, default=settings.port)
    parser.add_argument("--open", action="store_true", help="open the app in your browser")
    parser.add_argument("--reload", action="store_true", help="auto-reload on code changes (dev)")
    parser.add_argument("--access-log", action="store_true",
                        help="log every request (off by default: URLs contain users' coordinates)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if args.open:
        # Only builds the URL to open in a browser; it doesn't bind a socket.
        url = f"http://{'localhost' if args.host in ('0.0.0.0', '127.0.0.1') else args.host}:{args.port}"  # nosec B104
        threading.Timer(1.5, webbrowser.open, args=(url,)).start()
    uvicorn.run("solarrt.api:app", host=args.host, port=args.port, reload=args.reload,
                access_log=args.access_log)


if __name__ == "__main__":
    main()
