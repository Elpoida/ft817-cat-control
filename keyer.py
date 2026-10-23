"""CW keying engine: text to Morse timing, macros, beacon and line keying."""

from __future__ import annotations

import copy
import threading
import time

import backends

MORSE = {
    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.",
    "G": "--.", "H": "....", "I": "..", "J": ".---", "K": "-.-", "L": ".-..",
    "M": "--", "N": "-.", "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.",
    "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-",
    "Y": "-.--", "Z": "--..",
    "1": ".----", "2": "..---", "3": "...--", "4": "....-", "5": ".....",
    "6": "-....", "7": "--...", "8": "---..", "9": "----.", "0": "-----",
    ".": ".-.-.-", ",": "--..--", "?": "..--..", "'": ".----.", "!": "-.-.--",
    "/": "-..-.", "(": "-.--.", ")": "-.--.-", "&": ".-...", ":": "---...",
    ";": "-.-.-.", "=": "-...-", "+": ".-.-.", "-": "-....-", "_": "..--.-",
    '"': ".-..-.", "$": "...-..-", "@": ".--.-.",
}

PROSIGNS = {
    "<AR>": ".-.-.",
    "<SK>": "...-.-",
    "<BT>": "-...-",
    "<KN>": "-.--.",
    "<BK>": "-...-.-",
    "<AS>": ".-...",
    "<SN>": "...-.",
    "<HH>": "........",
}

DEFAULT_MEMORIES = [
    ("CQ", "CQ CQ CQ DE {MYCALL} {MYCALL} {MYCALL} K"),
    ("ANS", "{CALL} DE {MYCALL} <KN>"),
    ("RST", "{CALL} TNX UR RST {RST} {RST} <BK>"),
    ("TEST", "{CALL} {RST} {NR}"),
    ("TU", "TU {MYCALL}"),
    ("73", "{CALL} TNX QSO 73 DE {MYCALL} <SK> E E"),
    ("QRZ?", "QRZ? DE {MYCALL} K"),
    ("BEACON", "VVV VVV DE {MYCALL} {MYCALL} QTH {LOC} <AR>"),
]


def default_config():
    return {
        "params": {"wpm": 22, "farnsworth": 0, "ratio": 3.0, "weight": 50, "comp_ms": 0, "cut": False},
        "port": "",
        "line": "dtr",
        "ptt": "auto",
        "lead_ms": 60,
        "tail_ms": 250,
        "auto_cw": True,
        "station": {"mycall": "", "call": "", "rst": "599", "nr": 1, "loc": ""},
        "memories": [{"label": label, "text": text} for label, text in DEFAULT_MEMORIES],
        "beacon": {"text": DEFAULT_MEMORIES[7][1], "interval": 60, "repeat": 0},
        "monitor": {"on": True, "pitch": 650, "vol": 40},
        "live": False,
    }


def sanitize(config):
    cfg = copy.deepcopy(default_config())
    if not isinstance(config, dict):
        return cfg
    for key in ("port", "line", "ptt"):
        if isinstance(config.get(key), str):
            cfg[key] = config[key]
    for key in ("lead_ms", "tail_ms"):
        try:
            cfg[key] = max(0, min(2000, int(config.get(key, cfg[key]))))
        except (TypeError, ValueError):
            pass
    cfg["auto_cw"] = bool(config.get("auto_cw", cfg["auto_cw"]))
    cfg["live"] = bool(config.get("live", cfg["live"]))
    params = config.get("params")
    if isinstance(params, dict):
        for key in ("wpm", "farnsworth", "ratio", "weight", "comp_ms"):
            try:
                cfg["params"][key] = float(params.get(key, cfg["params"][key]))
            except (TypeError, ValueError):
                pass
        cfg["params"]["wpm"] = max(5, min(60, cfg["params"]["wpm"]))
        cfg["params"]["farnsworth"] = max(0, min(60, cfg["params"]["farnsworth"]))
        cfg["params"]["ratio"] = max(2.0, min(6.0, cfg["params"]["ratio"]))
        cfg["params"]["weight"] = max(20, min(80, cfg["params"]["weight"]))
        cfg["params"]["comp_ms"] = max(-50, min(50, cfg["params"]["comp_ms"]))
        cfg["params"]["cut"] = bool(params.get("cut", cfg["params"]["cut"]))
    station = config.get("station")
    if isinstance(station, dict):
        for key in ("mycall", "call", "rst", "loc"):
            if isinstance(station.get(key), str):
                cfg["station"][key] = station[key][:32]
        try:
            cfg["station"]["nr"] = max(1, min(9999, int(station.get("nr", cfg["station"]["nr"]))))
        except (TypeError, ValueError):
            pass
    memories = config.get("memories")
    if isinstance(memories, list):
        for index in range(8):
            source = memories[index] if index < len(memories) and isinstance(memories[index], dict) else {}
            label, text = DEFAULT_MEMORIES[index]
            cfg["memories"][index] = {
                "label": str(source.get("label", label))[:12],
                "text": str(source.get("text", text))[:500],
            }
    beacon = config.get("beacon")
    if isinstance(beacon, dict):
        cfg["beacon"]["text"] = str(beacon.get("text", cfg["beacon"]["text"]))[:500]
        try:
            cfg["beacon"]["interval"] = max(5, min(3600, int(beacon.get("interval", 60))))
        except (TypeError, ValueError):
            pass
        try:
            cfg["beacon"]["repeat"] = max(0, min(9999, int(beacon.get("repeat", 0))))
        except (TypeError, ValueError):
            pass
    monitor = config.get("monitor")
    if isinstance(monitor, dict):
        cfg["monitor"]["on"] = bool(monitor.get("on", True))
        try:
            cfg["monitor"]["pitch"] = max(300, min(1200, int(monitor.get("pitch", 650))))
        except (TypeError, ValueError):
            pass
        try:
            cfg["monitor"]["vol"] = max(0, min(100, int(monitor.get("vol", 40))))
        except (TypeError, ValueError):
            pass
    return cfg


def expand(text, station, cut=False):
    text = str(text)
    replacements = {
        "{MYCALL}": str(station.get("mycall", "")),
        "{CALL}": str(station.get("call", "")),
        "{RST}": str(station.get("rst", "599")),
        "{NR}": str(station.get("nr", 1)),
        "{LOC}": str(station.get("loc", "")),
    }
    for key, value in replacements.items():
        text = text.replace(key, value)
    text = text.upper()
    if cut:
        text = text.replace("9", "N").replace("0", "T")
    return text


def _tokenize(text):
    out = []
    upper = text.upper()
    index = 0
    while index < len(upper):
        if upper[index] == "<":
            end = upper.find(">", index)
            if end != -1:
                token = upper[index:end + 1]
                if token in PROSIGNS:
                    out.append(PROSIGNS[token])
                    index = end + 1
                    continue
        char = upper[index]
        if char in MORSE:
            out.append(MORSE[char])
        index += 1
    return out


def marks_for(text, config, station=None):
    params = sanitize(config)["params"] if station is None else config["params"]
    return build_marks(text, params, station or config.get("station", {}))


def build_marks(text, params, station):
    wpm = max(5.0, float(params.get("wpm", 22)))
    unit = 1200.0 / wpm
    farnsworth = max(0.0, min(float(params.get("farnsworth", 0)), wpm - 1))
    char_gap_unit = 1200.0 / farnsworth if farnsworth > 0 else unit
    ratio = float(params.get("ratio", 3.0))
    weight = float(params.get("weight", 50)) / 50.0
    comp = float(params.get("comp_ms", 0))
    expanded = expand(text, station, bool(params.get("cut")))
    words = expanded.split()
    marks = []

    def add(on, ms):
        ms = max(1, int(round(ms)))
        if marks and marks[-1]["on"] == on:
            marks[-1]["ms"] += ms
        else:
            marks.append({"on": on, "ms": ms})

    for wi, word in enumerate(words):
        if wi:
            add(False, 7 * char_gap_unit)
        symbols = _tokenize(word)
        for si, symbol in enumerate(symbols):
            if si:
                add(False, unit)
            for ci, element in enumerate(symbol):
                if ci:
                    add(False, unit)
                nominal = unit if element == "." else unit * ratio
                add(True, max(1.0, nominal * weight - comp))
        if wi < len(words) - 1:
            pass
    if marks and not marks[-1]["on"]:
        marks.pop()
    return marks, expanded


class Keyer:
    def __init__(self, rig):
        self.rig = rig
        self.config = default_config()
        self.lock = threading.Lock()
        self.thread = None
        self.abort = threading.Event()
        self.job = 0
        self.pending = []
        self.live = False
        self.beacon_thread = None
        self.beacon_conf = None
        self.key_port = None

    def configure(self, config):
        self.config = sanitize(config)
        return self.config

    def _state(self, **values):
        current = dict(getattr(self.rig, "state", {}).get("cw") or {})
        current.update(values)
        current.setdefault("busy", False)
        current.setdefault("text", "")
        current.setdefault("pos", 0)
        current.setdefault("marks", [])
        current.setdefault("job", 0)
        current.setdefault("beacon", None)
        current.setdefault("error", "")
        current.setdefault("line", "")
        current.setdefault("wpm", int(self.config["params"]["wpm"]))
        self.rig._set(cw=current)

    def _open_key_port(self):
        port = self.config.get("port", "")
        if port and (self.key_port is None or getattr(self.key_port, "port_name", port) != port):
            self._close_key_port()
            self.key_port = backends.KeyPort(port)
            self.key_port.port_name = port
        return self.key_port

    def _close_key_port(self):
        if self.key_port is not None:
            try:
                self.key_port.close()
            finally:
                self.key_port = None

    def set_line(self, on):
        line = self.config.get("line", "dtr")
        port = self._open_key_port()
        if port is not None:
            port.set_line(line, on)
        elif self.rig.tr is not None:
            self.rig.tr.set_line(line, on)

    def send(self, text, live=False):
        text = str(text or "").strip()
        if not text:
            return {"sent": 0}
        with self.lock:
            self.job += 1
            job_id = self.job
            if self.thread and self.thread.is_alive():
                if live:
                    self.pending.append(text)
                    return {"queued": len(self.pending), "job": job_id}
                self.abort.set()
                self.thread.join(2)
            self.abort.clear()
            self.pending = []
            self.live = bool(live)
            self.thread = threading.Thread(target=self._run, args=(text, job_id), daemon=True)
            self.thread.start()
        return {"job": job_id}

    def _run(self, text, job_id):
        try:
            self._transmit(text, job_id)
            while self.pending and not self.abort.is_set():
                extra = self.pending.pop(0)
                self._transmit(extra, job_id)
            self._state(busy=False, pos=0, beacon=None, line="")
        except Exception as exc:
            self._state(busy=False, pos=0, error=str(exc), line="")
        finally:
            try:
                self.set_line(False)
            except Exception:
                pass

    def _transmit(self, text, job_id):
        cfg = self.config
        station = dict(cfg["station"])
        expanded = expand(text, station, bool(cfg["params"].get("cut")))
        if "{NR}" in str(text).upper():
            station["nr"] = int(station.get("nr", 1)) + 1
            cfg["station"]["nr"] = station["nr"]
            callback = getattr(self.rig, "cw_nr_changed", None)
            if callback:
                callback(station["nr"])
        marks, expanded = build_marks(text, cfg["params"], station)
        if not marks:
            self._state(busy=False, text="", pos=0, marks=[], job=job_id, error="empty text")
            return
        ptt_mode = cfg.get("ptt", "auto")
        use_cat_ptt = ptt_mode == "always" or (
            ptt_mode == "auto" and self.rig.cfg.get("ptt") == "cat" and self.rig.state.get("ee", {}).get("bk") == "OFF"
        )
        line = cfg.get("line", "dtr")
        if use_cat_ptt:
            self.rig.cw_ptt(True)
            time.sleep(cfg.get("lead_ms", 60) / 1000.0)
        total = sum(mark["ms"] for mark in marks)
        self._state(
            busy=True, text=expanded, pos=0, marks=marks, job=job_id,
            beacon=self._beacon_status(), line=line, error="", total_ms=total, wpm=int(cfg["params"]["wpm"]),
        )
        try:
            for index, mark in enumerate(marks):
                if self.abort.is_set():
                    break
                self.rig.cw_keepalive()
                self.set_line(bool(mark["on"]))
                self._state(pos=index + 1)
                end = time.monotonic() + mark["ms"] / 1000.0
                while True:
                    remaining = end - time.monotonic()
                    if remaining <= 0:
                        break
                    if self.abort.wait(min(remaining, 0.05)):
                        break
        finally:
            try:
                self.set_line(False)
            except Exception:
                pass
            if use_cat_ptt:
                time.sleep(cfg.get("tail_ms", 250) / 1000.0)
                self.rig.cw_ptt(False)

    def _beacon_status(self):
        if self.beacon_conf is None:
            return None
        return dict(self.beacon_conf)

    def stop(self):
        self.abort.set()
        if self.beacon_thread and self.beacon_thread.is_alive():
            self.beacon_thread.join(2)
        if self.thread and self.thread.is_alive():
            self.thread.join(2)
        try:
            self.set_line(False)
        except Exception:
            pass
        try:
            self.rig.cw_ptt(False)
        except Exception:
            pass
        self._close_key_port()
        self.beacon_conf = None
        self._state(busy=False, pos=0, beacon=None, line="")

    def beacon(self, on, text="", interval=60, repeat=0):
        if not on:
            self.beacon_conf = None
            self.stop()
            return {"beacon": None}
        cfg = self.config
        cfg["beacon"] = {"text": str(text or cfg["beacon"]["text"]), "interval": int(interval), "repeat": int(repeat)}
        self.beacon_conf = dict(cfg["beacon"])
        self._state(beacon=self._beacon_status())
        if self.beacon_thread and self.beacon_thread.is_alive():
            self.abort.set()
            self.beacon_thread.join(2)
        self.abort.clear()
        self.beacon_thread = threading.Thread(target=self._beacon_run, daemon=True)
        self.beacon_thread.start()
        return {"beacon": self._beacon_status()}

    def _beacon_run(self):
        conf = dict(self.beacon_conf or self.config["beacon"])
        interval = max(5, int(conf.get("interval", 60)))
        repeat = int(conf.get("repeat", 0))
        count = 0
        while not self.abort.is_set():
            self.send(conf.get("text", ""), live=False)
            if self.thread:
                self.thread.join()
            count += 1
            if repeat and count >= repeat:
                break
            if self.abort.wait(interval):
                break
        self.beacon_conf = None
        self._state(beacon=None)
