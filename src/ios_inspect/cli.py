"""ios-inspect: debug Safari / WKWebView on an iPhone from Linux.

Thin launcher around `pymobiledevice3 webinspector cdp`: waits for the device,
starts the bridge, opens the DevTools landing page in a Chromium-based browser,
and restarts the bridge when the cable is unplugged and plugged back in.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from importlib.metadata import PackageNotFoundError, version

BROWSERS = (
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
    "brave-browser",
    "microsoft-edge",
)


def pmd3(*args: str) -> list[str]:
    return [sys.executable, "-m", "pymobiledevice3", *args]


def list_devices() -> list[dict]:
    try:
        out = subprocess.run(
            pmd3("usbmux", "list"), capture_output=True, text=True, timeout=20
        ).stdout
        return json.loads(out or "[]")
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        return []


def pick_device(udid: str | None) -> dict | None:
    for dev in list_devices():
        if udid is None or dev.get("UniqueDeviceID") == udid:
            return dev
    return None


def wait_for_device(udid: str | None) -> dict:
    dev = pick_device(udid)
    if dev:
        return dev
    print("Waiting for an iPhone to be plugged in and unlocked...", flush=True)
    while True:
        time.sleep(2)
        dev = pick_device(udid)
        if dev:
            return dev


def get_json(url: str, timeout: float = 3) -> object | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read())
    except (OSError, ValueError):
        return None


def find_browser(explicit: str | None) -> str | None:
    for name in (explicit, os.environ.get("BROWSER"), *BROWSERS):
        if name and shutil.which(name):
            return shutil.which(name)
    return None


def open_browser(browser: str | None, url: str) -> None:
    path = find_browser(browser)
    if not path:
        print(f"No Chromium-based browser found. Open it manually: {url}")
        return
    subprocess.Popen(
        [path, url],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def describe(dev: dict) -> str:
    return (
        f"{dev.get('DeviceName', 'iPhone')} ({dev.get('ProductType', '?')}, "
        f"iOS {dev.get('ProductVersion', '?')}, {dev.get('ConnectionType', '?')})"
    )


def cmd_start(args: argparse.Namespace) -> int:
    base = f"http://{args.host}:{args.port}"
    opened = args.no_browser
    proc: subprocess.Popen | None = None

    def stop(*_: object) -> None:
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(5)
            except subprocess.TimeoutExpired:
                proc.kill()
        print("\nStopped.")
        sys.exit(0)

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    while True:
        dev = wait_for_device(args.udid)
        print(f"Connected: {describe(dev)}", flush=True)

        cmd = pmd3(
            "webinspector", "cdp", "--host", args.host, "--port", str(args.port),
            "--udid", dev["UniqueDeviceID"],
        )
        if args.pause_new_targets:
            cmd.append("--pause-new-targets")
        log = None if args.verbose else subprocess.DEVNULL
        proc = subprocess.Popen(cmd, stdout=log, stderr=log)

        started = time.time()
        warned = False
        ready = False
        while proc.poll() is None:
            if get_json(f"{base}/json/version"):
                ready = True
                break
            if not warned and time.time() - started > 30:
                print("Bridge is still starting... (unlock the iPhone; run with --verbose "
                      "if this persists)", flush=True)
                warned = True
            time.sleep(0.5)

        if ready and proc.poll() is None:
            # The bridge serves /json before it has fetched the page list from the device.
            list_deadline = time.time() + 5
            pages = get_json(f"{base}/json") or []
            while not pages and time.time() < list_deadline and proc.poll() is None:
                time.sleep(0.5)
                pages = get_json(f"{base}/json") or []
            print(f"Web Inspector ready: {base}/  ({len(pages)} inspectable page{'' if len(pages) == 1 else 's'})")
            if not pages:
                print("  No pages yet. Open a website in Safari on the iPhone, then refresh the list.")
            if not opened:
                open_browser(args.browser, f"{base}/")
                opened = True
            print("Click a page title to open DevTools. Press Ctrl+C to stop.", flush=True)
            proc.wait()

        code = proc.returncode
        if args.no_reconnect:
            return code or 1
        if pick_device(args.udid) and code not in (0, None):
            print(f"Bridge exited (code {code}). Run with --verbose for details.")
            print("Retrying in 5 seconds...", flush=True)
            time.sleep(5)
        else:
            print("iPhone disconnected. Plug it back in to continue.", flush=True)


def check(ok: bool, label: str, hint: str = "") -> bool:
    print(f"  [{'OK' if ok else 'X '}] {label}")
    if not ok and hint:
        print(f"        -> {hint}")
    return ok


def cmd_doctor(args: argparse.Namespace) -> int:
    print("ios-inspect doctor")
    try:
        pmd3_version = version("pymobiledevice3")
    except PackageNotFoundError:
        pmd3_version = None
    results = [
        check(bool(pmd3_version), f"pymobiledevice3 {pmd3_version or 'not installed'}",
              "pip install pymobiledevice3"),
        check(bool(shutil.which("usbmuxd") or os.path.exists("/usr/sbin/usbmuxd")),
              "usbmuxd installed", "sudo apt install usbmuxd  (or your distro's usbmuxd package)"),
    ]
    dev = pick_device(args.udid)
    results.append(check(bool(dev), f"iPhone detected: {describe(dev)}" if dev else "iPhone detected",
                         "Plug in a data cable, unlock the iPhone, tap Trust. Also check `lsusb | grep -i apple`."))
    if dev:
        tabs = subprocess.run(
            pmd3("webinspector", "opened-tabs", "--udid", dev["UniqueDeviceID"], "-t", "5"),
            capture_output=True, text=True, timeout=40,
        )
        n = tabs.stdout.count("TYPE:")
        results.append(check(
            tabs.returncode == 0 and n > 0, f"Web Inspector responding ({n} page{'' if n == 1 else 's'})",
            "iOS 18+: Settings > Apps > Safari > Advanced > Web Inspector = ON, "
            "then open a website in Safari.",
        ))
    browser = find_browser(args.browser)
    results.append(check(bool(browser), f"Browser: {browser or 'not found'}",
                         "Install Chromium or Google Chrome."))
    print("All good." if all(results) else "Some checks failed (see the X marks).")
    return 0 if all(results) else 1


def cmd_pages(args: argparse.Namespace) -> int:
    dev = pick_device(args.udid)
    if not dev:
        print("No iPhone detected. Run `ios-inspect doctor`.")
        return 1
    return subprocess.call(
        pmd3("webinspector", "opened-tabs", "--udid", dev["UniqueDeviceID"], "-t", "5")
    )


def cmd_devices(args: argparse.Namespace) -> int:
    devices = list_devices()
    if not devices:
        print("No iPhone detected.")
        return 1
    for dev in devices:
        print(f"{dev.get('UniqueDeviceID')}  {describe(dev)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ios-inspect",
        description="Debug Safari / WKWebView on an iPhone from Linux (console, network, elements).",
    )
    try:
        own_version = version("ios-inspect-linux")
    except PackageNotFoundError:
        own_version = "dev"
    parser.add_argument("--version", action="version", version=f"%(prog)s {own_version}")
    parser.add_argument("--udid", help="Pick a specific iPhone when several are connected")
    parser.add_argument("--browser", help="Browser name or path (default: the Chrome/Chromium found)")
    sub = parser.add_subparsers(dest="command")

    start = sub.add_parser("start", help="Start the Web Inspector (default)")
    start.add_argument("--host", default="127.0.0.1")
    start.add_argument("--port", type=int, default=9222)
    start.add_argument("--no-browser", action="store_true", help="Do not open the browser automatically")
    start.add_argument("--no-reconnect", action="store_true",
                       help="Exit when the iPhone disconnects instead of waiting for it")
    start.add_argument("--pause-new-targets", action="store_true",
                       help="Pause every new JSContext on its first statement")
    start.add_argument("-v", "--verbose", action="store_true", help="Show bridge logs")

    sub.add_parser("doctor", help="Check the setup: usbmuxd, iPhone, Web Inspector, browser")
    sub.add_parser("pages", help="List inspectable Safari tabs / WebViews")
    sub.add_parser("devices", help="List connected iPhones")

    args = parser.parse_args(argv)
    if args.command in (None, "start"):
        if args.command is None:
            args = parser.parse_args([*(argv if argv is not None else sys.argv[1:]), "start"])
        return cmd_start(args)
    return {"doctor": cmd_doctor, "pages": cmd_pages, "devices": cmd_devices}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
