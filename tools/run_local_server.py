# -*- coding: utf-8 -*-
"""
Bulletproof Dual-Stack (IPv4 + IPv6) & Dual-Port (8088 + 8080) Local PC Launcher
================================================================================
Eliminates `localhost refused to connect (ERR_CONNECTION_REFUSED)` on Windows
Microsoft Edge / Chrome / Firefox by:
1. Binding BOTH port `8088` AND port `8080` simultaneously in a single lightweight process.
2. Binding BOTH IPv4 (`127.0.0.1`) AND IPv6 (`[::1]`) loopback sockets without triggering
   Windows Defender Firewall popups.
3. Waiting until `GET /api/v1/health` returns `200 OK` BEFORE opening `http://localhost:8088`
   in the user's browser (zero startup race condition).
4. Detecting if the server is already running in the background and opening the browser
   immediately instead of crashing on port-in-use.
"""

import argparse
import asyncio
import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path
from typing import List

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


def _is_health_ok(url: str, timeout: float = 0.8) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AlBahithLauncher/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def _create_loopback_sockets(ports: List[int], lan: bool = False) -> List[socket.socket]:
    sockets: List[socket.socket] = []
    v4_host = "0.0.0.0" if lan else "127.0.0.1"
    v6_host = "::" if lan else "::1"

    for port in ports:
        # 1. IPv4 Socket
        try:
            s4 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s4.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s4.bind((v4_host, port))
            s4.setblocking(False)
            sockets.append(s4)
        except OSError as exc:
            print(f"[WARN] IPv4 {v4_host}:{port} busy or unavailable: {exc}")

        # 2. IPv6 Socket (`IPV6_V6ONLY=1` so it coexists cleanly with IPv4 on both Windows & Linux)
        try:
            s6 = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            s6.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if hasattr(socket, "IPPROTO_IPV6") and hasattr(socket, "IPV6_V6ONLY"):
                try:
                    s6.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                except OSError:
                    pass
            s6.bind((v6_host, port))
            s6.setblocking(False)
            sockets.append(s6)
        except OSError:
            pass

    return sockets


def _wait_and_open_browser(primary_port: int) -> None:
    health_url = f"http://127.0.0.1:{primary_port}/api/v1/health"
    target_url = f"http://localhost:{primary_port}/"
    for _ in range(80):  # up to 12 seconds
        if _is_health_ok(health_url, timeout=0.5):
            time.sleep(0.15)
            try:
                webbrowser.open(target_url)
            except Exception:
                pass
            return
        time.sleep(0.15)


async def _serve(ports: List[int], open_browser: bool, lan: bool) -> int:
    import uvicorn

    primary_port = ports[0]
    # If already running and healthy in background, just open browser and return cleanly!
    if _is_health_ok(f"http://127.0.0.1:{primary_port}/api/v1/health"):
        print(f"[OK] الباحث الحديثي is already running at http://localhost:{primary_port}/")
        if open_browser:
            try:
                webbrowser.open(f"http://localhost:{primary_port}/")
            except Exception:
                pass
        return 0

    sockets = _create_loopback_sockets(ports, lan=lan)
    if not sockets:
        print("[ERROR] Could not bind ports 8088 or 8080. Check if another program is holding them.")
        return 1

    print("============================================================================")
    print("  الباحث الحديثي — اردو، عربی (Local PC Dual-Port Server Active)")
    print(f"  Primary URL   : http://localhost:{ports[0]}/")
    if len(ports) > 1:
        print(f"  Secondary URL : http://localhost:{ports[1]}/")
    print("  Cloud Backup  : https://abusufyaan93.github.io/al-bahith-hadith-urdu/")
    print("============================================================================")

    if open_browser:
        threading.Thread(target=_wait_and_open_browser, args=(primary_port,), daemon=True).start()

    # Redirect stdio safely when launched under `pythonw.exe` (silent background mode on Windows)
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")

    cfg = uvicorn.Config(
        "backend.main:app",
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(cfg)
    try:
        await server.serve(sockets=sockets)
    finally:
        for s in sockets:
            try:
                s.close()
            except Exception:
                pass
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run الباحث الحديثي Dual-Stack Local Server on 8088 & 8080")
    parser.add_argument("--ports", default="8088,8080", help="Comma-separated ports to listen on (default: 8088,8080)")
    parser.add_argument("--open-browser", action="store_true", help="Open http://localhost:8088 once /api/v1/health is 200 OK")
    parser.add_argument("--lan", action="store_true", help="Bind 0.0.0.0 / :: instead of loopback")
    args = parser.parse_args()

    ports = [int(p.strip()) for p in args.ports.split(",") if p.strip().isdigit()]
    if not ports:
        ports = [8088, 8080]

    os.chdir(str(BASE_DIR))
    code = asyncio.run(_serve(ports=ports, open_browser=args.open_browser, lan=args.lan))
    sys.exit(code)


if __name__ == "__main__":
    main()
