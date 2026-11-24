"""Evaluate JavaScript inside the running SolarRT Android app (debug builds only).

Developer tool for testing on an emulator or USB-connected phone:
    python mobile/tools/webview_eval.py "document.title"
Requires adb (Android SDK platform-tools) and the `websockets` package.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import urllib.request

import websockets

ADB = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Android", "Sdk", "platform-tools", "adb.exe")
PACKAGE = "com.sdebnath.solarrt"
PORT = 9333


def adb(*args: str) -> str:
    return subprocess.run([ADB, *args], capture_output=True, text=True, check=True).stdout.strip()


async def evaluate(expression: str) -> object:
    pid = adb("shell", "pidof", PACKAGE)
    if not pid:
        raise SystemExit(f"{PACKAGE} is not running")
    adb("forward", f"tcp:{PORT}", f"localabstract:webview_devtools_remote_{pid}")
    pages = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json"))
    page = next(p for p in pages if p.get("type") == "page")
    async with websockets.connect(page["webSocketDebuggerUrl"], max_size=None) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {
            "expression": expression, "awaitPromise": True, "returnByValue": True}}))
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("id") == 1:
                res = msg.get("result", {})
                if "exceptionDetails" in res:
                    return {"exception": res["exceptionDetails"].get("text"),
                            "detail": res.get("result", {}).get("description")}
                return res.get("result", {}).get("value")


if __name__ == "__main__":
    print(json.dumps(asyncio.run(evaluate(sys.argv[1])), indent=2, ensure_ascii=False))
