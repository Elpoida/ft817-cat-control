"""FT-817/818 CAT Control, clean-room rewrite: HTTP API and web panel."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import backends
import cat
import i18n
import keyer
import rig

APP_NAME = "FT-817/818 CAT Control (clean-room)"
VERSION = "1.3.2-cleanroom"
FROZEN = bool(getattr(sys, "frozen", False))
HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(getattr(sys, "_MEIPASS", HERE), "static")


def data_dir():
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    path = os.path.join(base, "FT-817-818 CAT Control (clean-room)")
    os.makedirs(path, exist_ok=True)
    return path


APPIMAGE = bool(os.environ.get("APPIMAGE"))
DATA = data_dir() if (FROZEN or APPIMAGE) else HERE
MEMFILE = os.path.join(DATA, "memorie.json")
CWFILE = os.path.join(DATA, "cw.json")
CONNFILE = os.path.join(DATA, "conn.json")
RIG = rig.Rig()
MEM_LOCK = threading.Lock()
QUIT = threading.Event()
STARTED = time.time()


def default_lang():
    try:
        import configparser
        ini = configparser.ConfigParser()
        ini.read(os.path.join(os.path.dirname(sys.executable) if FROZEN else HERE, "settings.ini"), encoding="utf-8")
        lang = ini.get("app", "lang", fallback="")
        if lang in i18n.LANGS:
            return lang
    except Exception:
        pass
    return "en"


i18n.set_lang(default_lang())


def load_json(path, fallback):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return fallback


def save_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(obj, handle, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def ports(_body, _query):
    return {
        "ports": backends.list_ports(),
        "pyserial": backends.have_pyserial(),
        "bauds": list(rig.BAUDS),
        "defaults": rig.DEFAULTS,
    }


def info(_body, _query):
    return {
        "product": "ft817-cleanroom",
        "version": VERSION,
        "lang": i18n.get_lang(),
        "free": True,
        "models": {key: {"name": value["name"], "watts": value["watts"]} for key, value in cat.MODELS.items()},
        "power_levels": cat.POWER_LEVELS,
        "ctcss": cat.CTCSS_TONES,
        "dcs": cat.DCS_CODES,
        "modes": list(cat.SET_MODES),
        "dig": cat.DIG_MODES,
        "tone_modes": list(cat.TONE_MODES),
        "rx_ranges": cat.RX_RANGES,
        "ee_fields": {name: {"values": spec[3], "writable": spec[4]} for name, spec in cat.EE_FIELDS.items()},
        "ant_values": cat.ANT_VALUES,
        "bands": [{"id": b[0], "lo": b[1], "hi": b[2]} for b in cat.BANDS],
    }


def connect(body, _query):
    cfg = dict(body or {})
    result = RIG.connect(cfg)
    RIG.set_cw_config(CW["config"])
    try:
        saved = {key: cfg.get(key, rig.DEFAULTS[key]) for key in rig.DEFAULTS}
        saved["auto"] = bool(cfg.get("auto", True))
        save_json(CONNFILE, saved)
    except OSError:
        pass
    return result


def disconnect(_body, _query):
    RIG.disconnect()
    return {}


def cmd(body, _query):
    body = dict(body or {})
    op = body.pop("op", "")
    if not op:
        raise ValueError("missing op")
    if op == "ptt":
        return RIG.ptt(bool(body.get("on")))
    if op == "ptt_keepalive":
        return RIG.ptt_keepalive()
    if op == "tune":
        return RIG.tune(bool(body.get("on")))
    if op == "swr_stop":
        return RIG.sweep_stop()
    if op == "memread_stop":
        return RIG.memread_stop()
    if op == "cw_send":
        return RIG.cw_send(str(body.get("text", "")), bool(body.get("live")))
    if op == "cw_stop":
        return RIG.cw_stop()
    if op == "cw_beacon":
        result = RIG.cw_beacon_set(bool(body.get("on")), str(body.get("text", "")),
                                   body.get("interval", 60), body.get("repeat", 0))
        save_cw()
        return result
    wait = body.pop("wait", True)
    return RIG.submit(op, body, wait=bool(wait), timeout=30.0 if op in ("scope", "swr_sweep", "read_memories") else 10.0)


def mem_load(_body, _query):
    with MEM_LOCK:
        data = load_json(MEMFILE, {"memories": []})
    memories = data.get("memories") if isinstance(data, dict) else data
    return {"memories": memories if isinstance(memories, list) else []}


def mem_save(body, _query):
    memories = (body or {}).get("memories")
    if not isinstance(memories, list):
        raise ValueError("memories must be a list")
    clean = []
    for item in memories:
        if not isinstance(item, dict):
            continue
        try:
            hz = int(item.get("f"))
        except (TypeError, ValueError):
            continue
        mode = str(item.get("m", "USB"))
        entry = {"name": str(item.get("name", ""))[:32], "f": hz, "m": mode}
        for key in ("rpt", "off", "tone", "ctcss", "dcs", "ch", "src"):
            if key in item:
                entry[key] = item[key]
        clean.append(entry)
    with MEM_LOCK:
        save_json(MEMFILE, {"memories": clean})
    return {"count": len(clean)}


def cw_get(_body, _query):
    return {
        "config": CW["config"],
        "macros": ["{MYCALL}", "{CALL}", "{RST}", "{NR}", "{LOC}"],
        "prosigns": list(keyer.PROSIGNS),
    }


def cw_save(body=None, _query=None):
    if body is not None:
        CW["config"] = RIG.set_cw_config((body or {}).get("config", body))
        with MEM_LOCK:
            save_json(CWFILE, CW["config"])
    else:
        CW["config"] = RIG.keyer.config
        with MEM_LOCK:
            save_json(CWFILE, CW["config"])
    return {"config": CW["config"]}


def trace(_body, query):
    try:
        since = int((query or {}).get("since", ["0"])[0])
    except (TypeError, ValueError):
        since = 0
    return {"trace": RIG.get_trace(since)}


def radio_memories(_body, _query):
    return {"memories": RIG.radio_memories()}


def lang(body, _query):
    i18n.set_lang(str((body or {}).get("lang", "")))
    return {"lang": i18n.get_lang()}


def license_info(_body, _query):
    return {"licensed": True, "free": True, "call": "", "serial": ""}


def quit_app(_body, _query):
    QUIT.set()
    return {"bye": True}


CW = {"config": keyer.sanitize(load_json(CWFILE, keyer.default_config()))}
RIG.set_cw_config(CW["config"])


def cw_nr_changed(config):
    CW["config"] = config
    with MEM_LOCK:
        try:
            save_json(CWFILE, config)
        except OSError:
            pass


RIG.cw_config_callback = cw_nr_changed

ROUTES = {
    ("GET", "/api/ports"): ports,
    ("GET", "/api/info"): info,
    ("GET", "/api/state"): lambda _b, _q: {"state": RIG.state},
    ("GET", "/api/trace"): trace,
    ("GET", "/api/memories"): mem_load,
    ("GET", "/api/radio_memories"): radio_memories,
    ("GET", "/api/cw"): cw_get,
    ("GET", "/api/license"): license_info,
    ("POST", "/api/connect"): connect,
    ("POST", "/api/disconnect"): disconnect,
    ("POST", "/api/cmd"): cmd,
    ("POST", "/api/memories"): mem_save,
    ("POST", "/api/cw"): cw_save,
    ("POST", "/api/lang"): lang,
    ("POST", "/api/license/remove"): license_info,
    ("POST", "/api/quit"): quit_app,
}


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".svg": "image/svg+xml",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC, **kwargs)

    def log_message(self, fmt, *args):
        return

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/events":
            return self._events()
        if parsed.path.startswith("/api/"):
            return self._api("GET", parsed)
        if parsed.path in ("/", ""):
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            return self._json(404, {"ok": False, "error": "not found"})
        return self._api("POST", parsed)

    def _events(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        client = self.connection
        client.settimeout(0.2)
        version = -1
        last = 0.0
        try:
            while not QUIT.is_set():
                now = time.monotonic()
                if version != RIG.version or now - last > 0.5:
                    version, payload = RIG.snapshot(version, timeout=0.05)
                    self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                    self.wfile.flush()
                    last = now
                else:
                    time.sleep(0.04)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def _api(self, method, parsed):
        route = ROUTES.get((method, parsed.path))
        if route is None:
            return self._json(404, {"ok": False, "error": "unknown endpoint"})
        body = {}
        if method == "POST":
            try:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b"{}"
                body = json.loads(raw.decode("utf-8") or "{}") if raw.strip() else {}
            except (ValueError, UnicodeDecodeError):
                return self._json(200, {"ok": False, "error": "invalid JSON"})
        try:
            result = route(body, parse_qs(parsed.query))
            payload = {"ok": True}
            if isinstance(result, dict):
                payload.update(result)
            return self._json(200, payload)
        except Exception as exc:
            return self._json(200, {"ok": False, "error": str(exc)})

    def _json(self, code, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def log_line(message):
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}"
    if sys.stdout:
        try:
            print(line, flush=True)
        except Exception:
            pass
    try:
        with open(os.path.join(DATA, "ft817-cleanroom.log"), "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        pass


def ui_alive(url):
    try:
        with urllib.request.urlopen(url + "api/info", timeout=0.6) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data.get("product") == "ft817-cleanroom"
    except Exception:
        return False


def open_ui(url, app_mode=True):
    if app_mode:
        if os.name == "nt":
            candidates = [
                os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
                os.path.join(os.environ.get("ProgramFiles", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
                os.path.join(os.environ.get("ProgramFiles", ""), "Google", "Chrome", "Application", "chrome.exe"),
                os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
            ]
            for exe in candidates:
                if exe and os.path.isfile(exe):
                    try:
                        subprocess.Popen([exe, f"--app={url}", "--window-size=1560,1040"],
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        return True
                    except OSError:
                        pass
        else:
            for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "microsoft-edge", "brave-browser"):
                exe = shutil.which(name)
                if exe:
                    try:
                        subprocess.Popen([exe, f"--app={url}", "--window-size=1560,1040"],
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        return True
                    except OSError:
                        pass
    try:
        return bool(webbrowser.open(url))
    except Exception:
        return False


def make_server(host, port):
    last = None
    for candidate in range(port, port + 20):
        try:
            server = ThreadingHTTPServer((host, candidate), Handler)
            server.daemon_threads = True
            server.timeout = 0.5
            return server, candidate
        except OSError as exc:
            last = exc
    raise last


def main(argv=None):
    parser = argparse.ArgumentParser(description="FT-817/818 CAT control panel")
    parser.add_argument("--host", default="127.0.0.1", help="listen address (0.0.0.0 for LAN access)")
    parser.add_argument("--port", type=int, default=817, help="HTTP port (default 817)")
    parser.add_argument("--sim", action="store_true", help="use the FT-817/818 simulator")
    parser.add_argument("--com", help="serial port, for example COM5")
    parser.add_argument("--baud", type=int, choices=list(rig.BAUDS), default=4800)
    parser.add_argument("--model", choices=list(rig.MODEL_CHOICES), default="auto")
    parser.add_argument("--app", action="store_true", help="open a dedicated browser app window")
    parser.add_argument("--no-app", action="store_true", help="always use the normal browser")
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser")
    args = parser.parse_args(argv)
    app_mode = bool(args.app or ((FROZEN or APPIMAGE) and not args.no_app))
    if args.sim or args.com:
        cfg = dict(rig.DEFAULTS)
        cfg.update(sim=bool(args.sim), port=args.com or "", baud=args.baud, model=args.model)
        try:
            RIG.connect(cfg)
            RIG.set_cw_config(CW["config"])
        except Exception as exc:
            log_line(f"connection failed: {exc}")
    else:
        saved = load_json(CONNFILE, None)
        if isinstance(saved, dict) and saved.get("auto", True) and (saved.get("sim") or saved.get("port")):
            try:
                RIG.connect(saved)
                RIG.set_cw_config(CW["config"])
                log_line(f"auto-connected to {saved.get('port') or 'simulator'} (saved settings)")
            except Exception as exc:
                log_line(f"saved connection failed: {exc}")
    probe_host = "127.0.0.1" if args.host in ("0.0.0.0", "::") else args.host
    existing = f"http://{probe_host}:{args.port}/"
    if not args.no_browser and ui_alive(existing):
        open_ui(existing, app_mode)
        return 0
    try:
        server, port = make_server(args.host, args.port)
    except Exception as exc:
        log_line(f"cannot start HTTP server: {exc}")
        if os.name == "nt":
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(0, f"Cannot start the local UI server: {exc}", APP_NAME, 0x10)
            except Exception:
                pass
        return 1
    url = f"http://{probe_host}:{port}/"
    if not args.no_browser:
        threading.Timer(0.4, lambda: open_ui(url, app_mode)).start()
    log_line(f"{APP_NAME} {VERSION} on {url}")
    try:
        while not QUIT.is_set():
            server.handle_request()
    except KeyboardInterrupt:
        pass
    finally:
        QUIT.set()
        RIG.disconnect()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
