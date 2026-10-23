# FT-817/818 CAT Control — clean-room

A from-scratch, browser-based control panel for the Yaesu **FT-817, FT-817ND and
FT-818ND** using the radio's CAT interface. It provides a local HTTP/JSON API, a
Server-Sent Events state stream, a responsive web panel, a CAT-speaking
simulator, EEPROM-backed settings, memory read/import, panorama, SWR sweep and a
CW keyer.

This project is an independent clean-room implementation created from
behavioural and protocol analysis. See [CLEANROOM.md](CLEANROOM.md)
for the method and boundaries. It contains no original application source, no
licence keys and no DRM/paywall code.

## Quick start

### Packaged builds (recommended)

Download the Windows EXE or Linux AppImage from
[GitHub Releases](https://github.com/Elpoida/ft817-cat-control/releases).
They include Python and pyserial; no `pip install` and no separate web server are
needed.

- **Windows:** double-click `FT817CAT-cleanroom.exe`.
- **Linux:** `chmod +x FT817CAT-cleanroom-x86_64.AppImage` then run it.

The connection dialog appears on first launch. For a real radio, leave
**Simulator** unchecked, choose the port, set the CAT rate and model, then press
**Connect**. The UI opens in a dedicated browser app window.

### From source

```bat
py server.py --sim
```

Then open <http://localhost:817/>. The simulator needs no radio. For a real
radio from source, install pyserial first:

```bat
py -m pip install pyserial
py server.py --com COM5 --baud 38400 --model 817
```

On the radio set menu **14 CAT RATE** to the same baud rate. The CAT cable goes
to the rear **ACC** socket (CT-62 or a USB-CAT interface). Use 8 data bits, no
parity, 2 stop bits (8N2).

Other options:

```text
--host 0.0.0.0     listen on the LAN (no authentication; trusted networks only)
--port 817         HTTP port
--sim              FT-817ND simulator (add --model 818 for FT-818ND)
--model auto|817|818
--no-browser       do not open a browser
```

Shortcuts: `run_simulator.bat` and `run.bat` (the latter forwards arguments).

## Releases

Prebuilt packages are attached to GitHub Releases:

- **Windows:** `FT817CAT-cleanroom.exe` — double-click; it starts its built-in
  local server and opens a dedicated browser app window. No Python, web server
  or installer is required. The build is unsigned, so SmartScreen may ask for
  confirmation.
- **Linux:** `FT817CAT-cleanroom-x86_64.AppImage` — `chmod +x` and run. A portable
  CPython and pyserial are bundled. If FUSE 2 is unavailable, run it with
  `--appimage-extract-and-run`.

The Windows build stores data in `%APPDATA%\FT-817-818 CAT Control (clean-room)`;
the AppImage uses `${XDG_DATA_HOME:-~/.local/share}/FT-817-818 CAT Control (clean-room)`.
First run starts disconnected: open **Settings**, tick **Simulator** (or choose
the COM/tty port) and press **Connect**.

Connection settings are saved to `conn.json` when **Connect automatically at
startup** is checked. On later launches the app reconnects to the same port or
simulator; if the radio is absent it starts disconnected and shows the dialog
again. The default language is English.

On Linux, real-radio access needs permission for the serial device. Add your
user to `dialout` (then log out and back in):

```bash
sudo usermod -aG dialout $USER
```

## Features

- **Display** with amber/green/blue/white/night LCD themes, mode, band, status
  icons, S-meter peak hold and TX meter.
- **Tuning** by knob drag, mouse wheel, step buttons, digit buttons, keyboard
  arrows/PageUp/PageDown and direct frequency entry. The last tuning command
  wins, so the knob does not queue up latency.
- **CAT controls**: mode, VFO A/B, A=B, A↔B, split, lock, clarifier, repeater
  shift/offset, CTCSS/DCS, PTT, power on/off.
- **Memory channels**: unlimited local memories with names, search, save,
  export/import JSON and read-from-radio import of the 200 FT-817/818 channels.
  Recalling a memory applies its mode, repeater shift/offset and CTCSS/DCS.
- **EEPROM settings** (writes opt-in): AGC, NB, MTR, power, IPO/ATT, NAR,
  antenna front/rear, DIG submode, break-in, keyer, read-only VOX/ARTS/DW/PRI.
- **Panorama** by stepping the VFO and reading the S-meter.
- **SWR sweep** around the current frequency or across the whole selected band
  (needs EEPROM writes enabled, because the power level is lowered through EEPROM).
- **TUNE** hold: FM, reduced power, carrier, automatic restore.
- **CW keyer** on DTR/RTS with WPM, Farnsworth, ratio, weight, compensation,
  macros, eight memories, beacon, browser audio monitor and optional CAT PTT.
- **CAT console** with raw five-byte commands, EEPROM read, traffic log and
  statistics. `0xBE` (reset) is blocked; `0xBC` requires EEPROM writes enabled.
- **Languages**: Italian, English, Spanish, French, Japanese and Russian for the
  main interface labels (fallback: English).

## Architecture

```text
server.py     HTTP server, JSON/SSE API, static files, persistence
rig.py        single radio-owner thread: command queue, polling, PTT watchdog,
              TUNE, panorama, SWR sweep, memory read
cat.py        pure CAT encoding/decoding, EEPROM map and memory records
backends.py   pyserial transport, CW key port, FT-817/818 simulator
keyer.py      Morse timing, macros, beacon and line keying
i18n.py       server-side message catalogue
static/       index.html, panel.css, panel.js, i18n.js
tests/        protocol, rig, keyer and API tests
packaging/    optional PyInstaller spec and Inno Setup script
```

The serial port is owned by one thread. Commands are queued, tuning commands
are merged, and polling reads frequency/mode, TX status, RX status and one
EEPROM word per cycle. A PTT watchdog releases the transmitter if the page stops
sending its heartbeat or the TOT expires; closing the page/server releases PTT.

## API

All responses use `{"ok": true, ...}` or `{"ok": false, "error": "..."}`.

```text
GET  /api/info                 product, models, limits, EEPROM fields, bands
GET  /api/ports                serial ports, pyserial availability, defaults
GET  /api/state                full state snapshot
GET  /api/events               Server-Sent Events state stream
GET  /api/trace?since=N        CAT traffic log
GET  /api/memories             saved local memories
POST /api/memories             save local memories {memories: [...]}
GET  /api/radio_memories       memories read from the radio
GET  /api/cw                   CW keyer configuration
POST /api/cw                   save CW configuration {config: {...}}
POST /api/connect              {sim, port, baud, stopbits, model, ptt, ...}
POST /api/disconnect
POST /api/cmd                  {op, ...}
POST /api/lang                 {lang}
POST /api/quit
```

Command operations include `freq`, `mode`, `vfo_ab`, `a_eq_b`, `swap`, `split`,
`lock`, `clar`, `clar_freq`, `rpt_shift`, `rpt_offset`, `tone_mode`, `ctcss`,
`dcs`, `ptt`, `ptt_keepalive`, `tune`, `power`, `ee_set`, `ee_read`, `raw`,
`scope`, `swr_sweep`, `swr_stop`, `read_memories`, `memread_stop`, `batch`,
`cw_send`, `cw_stop` and `cw_beacon`.

## Tests

```bat
py -m unittest discover -s tests -v
```

The tests cover BCD/CAT frames, band/model detection, EEPROM fields, memory
record round-trips, Morse timing, the simulator-backed rig thread and the HTTP
API. The simulator is the only supported test target; real-radio behaviour still
needs field validation.

## Safety

- Transmitting is the operator's responsibility.
- EEPROM writes are disabled by default. Enabling them and using TUNE/SWR sweeps
  changes radio settings through EEPROM; do not write arbitrary EEPROM areas
  (especially calibration data).
- The panel has no authentication. Use `--host 0.0.0.0` only on a trusted
  network, and do not expose the HTTP port to the internet.
- Closing the page or server, losing the heartbeat, `Esc`, or TOT releases PTT.

## Deliberate differences from the studied build

- No licence/paywall, no Ed25519 key material and no demo timer. The program is
  unrestricted.
- The packaged builds start their own loopback server and open a dedicated
  Edge/Chrome app window; no external web server or Python install is needed.
  Source runs default to a normal browser tab unless `--app` is used.
- The web panel is an original design, not a copy of the shipped one.
- The simulator's demo signals/memories are representative test data.
- The Windows EXE and Linux AppImage are published as GitHub release assets, not
  committed to the source tree. Build scripts are in `packaging/`.

## Licence

The source in this repository is released under the MIT licence (see
[LICENSE](LICENSE)). Yaesu, FT-817/818, CAT and related protocol facts belong to
their respective owners; no affiliation or endorsement is claimed.
