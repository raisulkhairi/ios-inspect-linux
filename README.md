<p align="center">
  <img src="assets/banner.png" alt="ios-inspect: Debug Safari on iPhone, right from Linux" width="100%">
</p>

# ios-inspect-linux

Debug websites in **Safari on iPhone** and in **WKWebView** straight from **Linux**, no Mac required.
You get the familiar Chrome DevTools: Console, Network, Elements, Sources.

```
iPhone (Safari)  ──USB──▶  ios-inspect  ──▶  Chrome DevTools on Linux
```

> Apple ships the iOS Web Inspector only inside Safari on macOS. `ios-inspect` uses
> [pymobiledevice3](https://github.com/doronz88/pymobiledevice3) to reach the Web Inspector
> service on the iPhone over USB and shows it in Chrome/Chromium.

## Features

- **Console**: see `console.log` output and errors from the iPhone, run JavaScript in the page.
- **Network**: requests, responses, headers, status codes, timing.
- **Elements**: inspect the DOM and edit CSS live.
- **Sources**: browse JS files and set breakpoints.
- **One command**: waits for the iPhone, starts the bridge, and opens the browser for you.
- **Auto-reconnect**: if the cable comes loose, just plug it back in.
- **`ios-inspect doctor`**: checks your setup and tells you what to fix.

Tested on an iPhone XR running iOS 18.7, Pop!_OS (Ubuntu 24.04), and Python 3.12.

## Requirements

| Requirement | Notes |
|---|---|
| Linux | Tested on Ubuntu/Pop!_OS; any distro with `usbmuxd` should work |
| Python 3.9+ | |
| `usbmuxd` | USB daemon for iOS devices (`sudo apt install usbmuxd`) |
| Chrome / Chromium | Displays DevTools |
| iPhone + data cable | Charge-only cables will not work |
| Internet access | The DevTools UI is downloaded when it opens |

## Installation

```bash
# 1. Install usbmuxd
sudo apt install usbmuxd

# 2. Install ios-inspect into a virtualenv
python3 -m venv ~/.venvs/ios-inspect
~/.venvs/ios-inspect/bin/pip install git+https://github.com/raisulkhairi/ios-inspect-linux.git

# 3. (Optional) make `ios-inspect` available on your PATH
mkdir -p ~/.local/bin
ln -s ~/.venvs/ios-inspect/bin/ios-inspect ~/.local/bin/ios-inspect
```

Or with [pipx](https://pipx.pypa.io/):

```bash
pipx install git+https://github.com/raisulkhairi/ios-inspect-linux.git
```

## iPhone setup (one time)

1. Go to **Settings → Apps → Safari → Advanced** and turn on **Web Inspector**.
   (iOS 17 and earlier: **Settings → Safari → Advanced → Web Inspector**.)
2. Plug the iPhone into your computer, unlock it, and tap **Trust** when *"Trust This Computer?"* appears.

## Usage

```bash
ios-inspect
```

Then:

1. Open the website you want to debug in **Safari on the iPhone**.
2. Your browser opens `http://127.0.0.1:9222/` automatically and lists the inspectable pages.
3. **Click the page title** (the blue link). DevTools opens.
4. When you are done, press `Ctrl+C` in the terminal.

Example output:

```
Connected: iPhone (iPhone11,8, iOS 18.7.12, USB)
Web Inspector ready: http://127.0.0.1:9222/  (1 inspectable page)
Click a page title to open DevTools. Press Ctrl+C to stop.
```

> **Tip:** in the **Network** tab, reload the page on the iPhone after DevTools opens
> so that every request from the start is captured.

### Commands

| Command | What it does |
|---|---|
| `ios-inspect` | Start the Web Inspector (same as `ios-inspect start`) |
| `ios-inspect doctor` | Check usbmuxd, the iPhone, Web Inspector, and the browser |
| `ios-inspect pages` | List Safari tabs that can be inspected |
| `ios-inspect devices` | List connected iPhones |

### `start` options

`start` is the default command, so these also work without it, e.g. `ios-inspect --no-browser`.

| Option | What it does |
|---|---|
| `--port 9333` | Use another port (default `9222`) |
| `--no-browser` | Do not open the browser automatically |
| `--no-reconnect` | Exit when the iPhone disconnects |
| `--pause-new-targets` | Pause every new JSContext on its first statement |
| `-v`, `--verbose` | Show bridge logs (for troubleshooting) |
| `--udid <UDID>` | Pick a specific iPhone when several are connected (put it before the subcommand) |
| `--browser <name>` | Use a specific browser, e.g. `--browser chromium` |

### Debugging apps (WKWebView)

WKWebView pages inside an iOS app can be inspected when the app enables:

```swift
webView.isInspectable = true   // iOS 16.4+
```

### Using it from VS Code

Run `ios-inspect --no-browser`, then add this to `.vscode/launch.json`:

```json
{
  "type": "chrome",
  "request": "attach",
  "name": "iPhone Safari",
  "address": "127.0.0.1",
  "port": 9222,
  "urlFilter": "*",
  "webRoot": "${workspaceFolder}"
}
```

## Troubleshooting

Run `ios-inspect doctor` first. Common problems:

| Symptom | Fix |
|---|---|
| Stuck on `Waiting for an iPhone...` | Re-plug or try another port/cable, unlock the iPhone, tap **Trust**. Check with `lsusb \| grep -i apple`. |
| Stuck on `Bridge is still starting...` | Unlock the iPhone and keep Safari open. If it persists, stop and rerun with `--verbose` to see the bridge log. |
| The page list is empty | Make sure Web Inspector is on, a website is open in Safari, and the iPhone is unlocked, then refresh the list. |
| `iPhone disconnected` | The cable came loose. Plug it back in; `ios-inspect` reconnects on its own. |
| DevTools shows a blank page | Check your internet connection (the DevTools UI is downloaded when it opens). |
| Console freezes under heavy logging | Open DevTools from `http://127.0.0.1:9222/`, not from `chrome://inspect`. |
| Page marked *held elsewhere*, Console/Network stay empty | The page is being debugged somewhere else (Safari on a Mac, or a second `ios-inspect`). Close that debugger first. |
| `Port 9222 is already in use` | Another `ios-inspect` (or a Chrome with remote debugging) holds the port. Stop it, or run `ios-inspect --port 9333`. |

## Limitations

- The iOS Simulator is not supported (it needs Xcode/macOS).
- USB only; debugging over Wi-Fi has not been tested.
- Apple may change the Web Inspector protocol in new iOS releases. If something breaks,
  try updating pymobiledevice3: `pip install -U pymobiledevice3`.

## How it works

`ios-inspect` itself is only a launcher. The heavy lifting (talking to the iPhone and translating
the protocol) is done by [pymobiledevice3](https://github.com/doronz88/pymobiledevice3).

```
┌─ iPhone ───────────────┐     ┌─ Linux machine ──────────────────────────────────┐
│ Safari / WKWebView     │     │                                                  │
│        │               │     │  usbmuxd     pymobiledevice3         Chromium    │
│ webinspectord ◀────────┼─USB─┼─▶ (USB  ──▶  webinspector cdp  ◀──▶  DevTools    │
│ (Web Inspector service)│     │    link)     • talks to the iPhone   (Console,   │
└────────────────────────┘     │              • translates protocol   Network…)   │
                               │              • serves :9222                      │
                               │        ▲                                         │
                               │  ios-inspect: starts, watches, opens the         │
                               │               browser, reconnects                │
                               └──────────────────────────────────────────────────┘
```

### Four layers

1. **iPhone: `webinspectord`.** The built-in iOS service that Safari on a Mac also talks to. It is
   active only when **Web Inspector** is enabled in Settings, and it tracks every Safari and
   WKWebView page that may be inspected.
2. **USB link: `usbmuxd`.** The Linux daemon that opens a channel to the iPhone over the cable.
   After pairing (tapping **Trust**), the computer may open services on the iPhone, including
   Web Inspector.
3. **Translator: `pymobiledevice3 webinspector cdp`.** The core of the system. It:
   - opens the Web Inspector service, asks for the list of apps and pages, and connects to the
     page you pick;
   - translates in both directions between the **WebKit Inspector Protocol** (what the iPhone
     speaks) and the **Chrome DevTools Protocol / CDP** (what Chrome DevTools speaks);
   - serves `127.0.0.1:9222`:

     | Endpoint | Contents |
     |---|---|
     | `/` | Page list |
     | `/json` | Target list for Chrome, VS Code, Playwright, etc. |
     | `ws://…/devtools/page/<id>` | Per-page WebSocket that carries DevTools messages |
     | `/devtools/inspector.html` | The DevTools UI (downloaded from the internet) |
4. **Display: Chrome DevTools.** Plain DevTools. To it, `127.0.0.1:9222` looks like any other
   Chrome, so it never needs to know there is an iPhone on the other end.

### Example flow: one `console.log`

```
iPhone: the page runs console.log("hello")
  → webinspectord sends an event (WebKit protocol) over USB
  → usbmuxd forwards it to pymobiledevice3
  → it is translated into the CDP event "Runtime.consoleAPICalled"
  → sent over the WebSocket to DevTools
  → "hello" appears in the Console tab
```

It works the other way too: a command typed into the Console (for example `document.title`) is
translated, run on the iPhone, and the result is sent back. The Network, Elements, and Sources
tabs work the same way.

### What `ios-inspect` does

Code in [`src/ios_inspect/cli.py`](src/ios_inspect/cli.py):

```
start
  └─▶ wait for the iPhone to appear in usbmuxd (polls every 2 seconds)
        └─▶ run "pymobiledevice3 webinspector cdp" as a child process
              └─▶ wait for the :9222 server to be ready (polls /json/version)
                    └─▶ open Chromium at http://127.0.0.1:9222/ (once)
                          └─▶ wait for the bridge to exit
                                ├─ iPhone disconnected        → back to "wait for the iPhone"
                                ├─ error, iPhone still there  → retry after 5 seconds
                                └─ Ctrl+C                     → stop the bridge and exit
```

- `doctor` checks pymobiledevice3, usbmuxd, the iPhone, the Web Inspector response, and the
  browser, one by one.
- `pages` and `devices` print data from pymobiledevice3.

### Design consequences

- **One page, one debugger.** A page already held by another debugger (Safari on a Mac, or a
  second bridge) is marked *held elsewhere* and sends no events to our DevTools.
- **Depends on pymobiledevice3.** If Apple changes the protocol in a new iOS release, it is
  pymobiledevice3 that needs updating, not `ios-inspect`.
- **The DevTools UI comes from the internet**, so without a connection it may show a blank page.

## License

[GPL-3.0-or-later](LICENSE). This project uses
[pymobiledevice3](https://github.com/doronz88/pymobiledevice3) (GPL-3.0).
