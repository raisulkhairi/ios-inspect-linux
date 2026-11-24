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
    print("Menunggu iPhone dicolok dan dibuka kuncinya...", flush=True)
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
        print(f"Browser Chromium tidak ditemukan. Buka manual: {url}")
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
        print("\nBerhenti.")
        sys.exit(0)

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    while True:
        dev = wait_for_device(args.udid)
        print(f"Terhubung: {describe(dev)}", flush=True)

        cmd = pmd3(
            "webinspector", "cdp", "--host", args.host, "--port", str(args.port),
            "--udid", dev["UniqueDeviceID"],
        )
        if args.pause_new_targets:
            cmd.append("--pause-new-targets")
        log = None if args.verbose else subprocess.DEVNULL
        proc = subprocess.Popen(cmd, stdout=log, stderr=log)

        deadline = time.time() + 30
        while time.time() < deadline and proc.poll() is None:
            if get_json(f"{base}/json/version"):
                break
            time.sleep(0.5)

        if proc.poll() is None:
            pages = get_json(f"{base}/json") or []
            print(f"Web Inspector siap: {base}/  ({len(pages)} halaman bisa di-inspect)")
            if not pages:
                print("  Belum ada halaman. Buka website di Safari iPhone lalu refresh daftar.")
            if not opened:
                open_browser(args.browser, f"{base}/")
                opened = True
            print("Klik judul halaman untuk membuka DevTools. Ctrl+C untuk berhenti.", flush=True)
            proc.wait()

        code = proc.returncode
        if args.no_reconnect:
            return code or 1
        if pick_device(args.udid) and code not in (0, None):
            print(f"Bridge berhenti (exit {code}). Jalankan dengan --verbose untuk detail.")
            print("Mencoba lagi dalam 5 detik...", flush=True)
            time.sleep(5)
        else:
            print("iPhone terputus. Colok ulang untuk melanjutkan.", flush=True)


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
        check(bool(pmd3_version), f"pymobiledevice3 {pmd3_version or 'tidak terpasang'}",
              "pip install pymobiledevice3"),
        check(bool(shutil.which("usbmuxd") or os.path.exists("/usr/sbin/usbmuxd")),
              "usbmuxd terpasang", "sudo apt install usbmuxd  (atau paket usbmuxd distro kamu)"),
    ]
    dev = pick_device(args.udid)
    results.append(check(bool(dev), f"iPhone terdeteksi: {describe(dev)}" if dev else "iPhone terdeteksi",
                         "Colok kabel data, buka kunci iPhone, tap Trust. Cek juga `lsusb | grep -i apple`."))
    if dev:
        tabs = subprocess.run(
            pmd3("webinspector", "opened-tabs", "--udid", dev["UniqueDeviceID"], "-t", "5"),
            capture_output=True, text=True, timeout=40,
        )
        n = tabs.stdout.count("TYPE:")
        results.append(check(
            tabs.returncode == 0 and n > 0, f"Web Inspector merespons ({n} halaman)",
            "iOS 18+: Settings > Apps > Safari > Advanced > Web Inspector = ON, "
            "lalu buka website di Safari.",
        ))
    browser = find_browser(args.browser)
    results.append(check(bool(browser), f"Browser: {browser or 'tidak ditemukan'}",
                         "Pasang Chromium / Google Chrome."))
    print("Semua siap." if all(results) else "Ada yang perlu diperbaiki (lihat tanda X).")
    return 0 if all(results) else 1


def cmd_pages(args: argparse.Namespace) -> int:
    dev = pick_device(args.udid)
    if not dev:
        print("iPhone tidak terdeteksi. Jalankan `ios-inspect doctor`.")
        return 1
    return subprocess.call(
        pmd3("webinspector", "opened-tabs", "--udid", dev["UniqueDeviceID"], "-t", "5")
    )


def cmd_devices(args: argparse.Namespace) -> int:
    devices = list_devices()
    if not devices:
        print("Tidak ada iPhone terdeteksi.")
        return 1
    for dev in devices:
        print(f"{dev.get('UniqueDeviceID')}  {describe(dev)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ios-inspect",
        description="Debug Safari / WKWebView di iPhone dari Linux (console, network, elements).",
    )
    try:
        own_version = version("ios-inspect-linux")
    except PackageNotFoundError:
        own_version = "dev"
    parser.add_argument("--version", action="version", version=f"%(prog)s {own_version}")
    parser.add_argument("--udid", help="Pilih iPhone tertentu jika lebih dari satu tercolok")
    parser.add_argument("--browser", help="Path/nama browser (default: Chrome/Chromium yang ada)")
    sub = parser.add_subparsers(dest="command")

    start = sub.add_parser("start", help="Jalankan Web Inspector (default)")
    start.add_argument("--host", default="127.0.0.1")
    start.add_argument("--port", type=int, default=9222)
    start.add_argument("--no-browser", action="store_true", help="Jangan buka browser otomatis")
    start.add_argument("--no-reconnect", action="store_true",
                       help="Keluar saat iPhone terputus, jangan menunggu dicolok ulang")
    start.add_argument("--pause-new-targets", action="store_true",
                       help="Hentikan tiap JSContext baru di statement pertamanya")
    start.add_argument("-v", "--verbose", action="store_true", help="Tampilkan log bridge")

    sub.add_parser("doctor", help="Cek setup: usbmuxd, iPhone, Web Inspector, browser")
    sub.add_parser("pages", help="Tampilkan tab Safari / WebView yang bisa di-inspect")
    sub.add_parser("devices", help="Tampilkan iPhone yang tercolok")

    args = parser.parse_args(argv)
    if args.command in (None, "start"):
        if args.command is None:
            args = parser.parse_args([*(argv if argv is not None else sys.argv[1:]), "start"])
        return cmd_start(args)
    return {"doctor": cmd_doctor, "pages": cmd_pages, "devices": cmd_devices}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
