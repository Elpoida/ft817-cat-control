"""Radio owner thread: command queue, polling, PTT safety, memories and sweeps."""

from __future__ import annotations

import collections
import json
import threading
import time

import backends
import cat
from keyer import Keyer

DEFAULTS = {
    "sim": False,
    "port": "",
    "baud": 4800,
    "stopbits": 2,
    "dtr": False,
    "rts": False,
    "ptt": "cat",
    "poll_ms": 100,
    "timeout_ms": 300,
    "tot_s": 180,
    "ee_write": False,
    "model": "auto",
    "auto": True,
}
MODEL_CHOICES = ("auto", "817", "818")
BAUDS = (4800, 9600, 38400)
HEARTBEAT_S = 2.0
FAIL_LIMIT = 3
TUNE_LEVEL = "L2"
TUNE_MAX_S = 60
SWEEP_MAX_POINTS = 41
EE_ADDRESSES = (84, 86, 88, 100, 120, 122)


class CatTimeout(cat.CatError):
    pass


class Job:
    def __init__(self, op, args):
        self.op = op
        self.args = args
        self.done = threading.Event()
        self.result = None
        self.error = None
        self.started = False
        self.followers = []

    def finish(self, result=None, error=None):
        for job in [self] + self.followers:
            job.result = result
            job.error = error
            job.done.set()


def mode_for_set(mode, narrow):
    if mode in cat.SET_MODES:
        return mode
    if mode == "FM-N":
        return "FM"
    return None


class Rig:
    def __init__(self):
        self.cond = threading.Condition()
        self.queue = collections.deque()
        self.tr = None
        self.thread = None
        self.running = False
        self.cfg = dict(DEFAULTS)
        self.trace = collections.deque(maxlen=400)
        self.trace_seq = 0
        self.version = 0
        self._json = (None, "")
        self.ee = {}
        self.ee_turn = 0
        self.fails = 0
        self.ee_fails = 0
        self.ack_mode = True
        self.ack_miss = 0
        self.ptt_req = False
        self.ptt_cat = False
        self.ptt_beat = 0.0
        self.ptt_start = 0.0
        self.abort_scope = False
        self.abort_sweep = False
        self.abort_memread = False
        self.tune_want = False
        self.tune_saved = None
        self.tm_fails = 0
        self.mem_items = []
        self.model = "817"
        self.model_sure = False
        self.poll_count = 0
        self.poll_rate = 0.0
        self.poll_mark = time.monotonic()
        self.cw_config_callback = None
        self.keyer = Keyer(self)
        self.state = self._blank()

    def _blank(self):
        return {
            "connected": False,
            "description": "",
            "radio": False,
            "error": "",
            "freq": 0,
            "mode": "",
            "narrow": False,
            "band": None,
            "tx": False,
            "s": 0,
            "squelched": False,
            "code_mismatch": False,
            "disc_off": False,
            "tx_bars": 0,
            "hi_swr": False,
            "ee": {},
            "ee_ok": None,
            "written": {
                "lock": None, "split": None, "clar_on": None, "clar": None,
                "rpt": None, "rpt_offset": None, "tone_mode": None,
                "ctcss": None, "dcs": None,
            },
            "ptt_cat": False,
            "ptt_left": None,
            "ptt_alarm": "",
            "scope": None,
            "tune_seq": 0,
            "ack": "ack",
            "tm": None,
            "tm_ok": None,
            "tune": None,
            "swr": None,
            "memread": None,
            "stats": {"rate": 0.0, "timeouts": 0, "errors": 0},
            "cfg": dict(DEFAULTS),
            "model": "817",
            "model_sure": False,
            "cw": {
                "busy": False, "text": "", "pos": 0, "marks": [], "job": 0,
                "beacon": None, "error": "", "line": "", "wpm": 22,
            },
        }

    def _set(self, **values):
        with self.cond:
            changed = False
            for key, value in values.items():
                if self.state.get(key) != value:
                    self.state[key] = value
                    changed = True
            if changed:
                self.version += 1
                self.cond.notify_all()

    def _set_written(self, **values):
        written = dict(self.state.get("written") or {})
        written.update(values)
        self._set(written=written)

    def snapshot(self, since=0, timeout=15.0):
        with self.cond:
            if self.version == since:
                self.cond.wait(timeout)
            if self._json[0] != self.version:
                self._json = (self.version, json.dumps(self.state))
            return self.version, self._json[1]

    def _log(self, tx, rx, poll=False, note=""):
        self.trace_seq += 1
        self.trace.append({
            "n": self.trace_seq,
            "t": time.time(),
            "tx": cat.hexs(tx) if tx else "",
            "rx": cat.hexs(rx) if rx else "",
            "poll": bool(poll),
            "note": note,
        })

    def get_trace(self, since=0):
        with self.cond:
            return [row for row in self.trace if row["n"] > since]

    def connect(self, cfg):
        self.disconnect()
        merged = dict(DEFAULTS)
        for key in DEFAULTS:
            if key in cfg:
                merged[key] = cfg[key]
        try:
            merged["baud"] = int(merged["baud"])
            merged["stopbits"] = 2 if int(merged["stopbits"]) == 2 else 1
            merged["poll_ms"] = max(20, min(2000, int(merged["poll_ms"])))
            merged["timeout_ms"] = max(50, min(3000, int(merged["timeout_ms"])))
            merged["tot_s"] = max(1, min(600, int(merged["tot_s"])))
        except (TypeError, ValueError) as exc:
            raise cat.CatError(f"invalid connection parameter: {exc}") from exc
        if merged["model"] not in MODEL_CHOICES:
            merged["model"] = "auto"
        if merged["baud"] not in BAUDS:
            merged["baud"] = 4800
        model = merged["model"] if merged["model"] in ("817", "818") else "817"
        if merged.get("sim"):
            transport = backends.SimulatedFT817(model)
        else:
            if not merged.get("port"):
                raise cat.CatError("no serial port selected")
            transport = backends.SerialTransport(
                merged["port"], merged["baud"], merged["stopbits"], merged.get("dtr", False), merged.get("rts", False)
            )
        self.tr = transport
        self.cfg = merged
        self.model = model
        self.model_sure = merged["model"] != "auto"
        self.ee = {}
        self.ee_turn = 0
        self.fails = 0
        self.ee_fails = 0
        self.ack_mode = True
        self.ack_miss = 0
        self.ptt_req = False
        self.ptt_cat = False
        self.tune_saved = None
        self.mem_items = []
        self.queue.clear()
        self.trace.clear()
        self.trace_seq = 0
        self.state = self._blank()
        state_cfg = {key: merged[key] for key in ("sim", "port", "baud", "stopbits", "ptt", "poll_ms", "tot_s", "ee_write", "model", "auto")}
        self._set(
            connected=True,
            description=getattr(transport, "description", ""),
            radio=True,
            cfg=state_cfg,
            model=model,
            model_sure=self.model_sure,
        )
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        return {"description": getattr(transport, "description", ""), "radio": True}

    def disconnect(self):
        self.keyer.stop()
        if self.thread:
            self.running = False
            with self.cond:
                self.cond.notify_all()
            self.thread.join(5)
            self.thread = None
        if self.tr:
            try:
                if self.ptt_cat:
                    self._key(False)
                if self.tune_saved:
                    self._tune_restore()
                self.tr.close()
            except Exception:
                pass
            self.tr = None
        for job in list(self.queue):
            job.finish(error="disconnected")
        self.queue.clear()
        with self.cond:
            self.state = self._blank()
            self.version += 1
            self.cond.notify_all()
        return {}

    def submit(self, op, args, wait=True, timeout=10.0):
        if not self.running:
            raise cat.CatError("not connected")
        args = dict(args or {})
        if op not in ("scope", "swr_sweep", "read_memories", "ptt_keepalive", "cw_ptt"):
            self.abort_scope = True
            self.abort_sweep = True
            self.abort_memread = True
        job = None
        with self.cond:
            if op == "freq":
                last = self.queue[-1] if self.queue else None
                if last is not None and last.op == "freq" and not last.started:
                    last.args = args
                    job = last
            if job is None:
                job = Job(op, args)
                if op in ("ptt_sync", "tune_on") or op == "ptt":
                    self.queue.appendleft(job)
                else:
                    self.queue.append(job)
            self.cond.notify_all()
        if not wait:
            return {}
        if not job.done.wait(timeout):
            raise cat.CatError("command timeout")
        if job.error:
            raise cat.CatError(job.error)
        return job.result or {}

    def ptt(self, on):
        if not self.running:
            raise cat.CatError("not connected")
        with self.cond:
            self.ptt_req = bool(on)
            if on:
                self.ptt_beat = time.monotonic()
                self.abort_scope = True
                self.abort_sweep = True
            self.queue.appendleft(Job("ptt_sync", {}))
            self.cond.notify_all()
        return {}

    def ptt_keepalive(self):
        self.ptt_beat = time.monotonic()
        return {"ptt_cat": self.ptt_cat}

    def tune(self, on):
        if not self.running:
            raise cat.CatError("not connected")
        with self.cond:
            self.tune_want = bool(on)
            if on:
                self._set(ptt_alarm="")
                self.ptt_beat = time.monotonic()
                self.abort_scope = True
                self.abort_sweep = True
                self.queue.appendleft(Job("tune_on", {}))
            else:
                self.ptt_req = False
                self.queue.appendleft(Job("ptt_sync", {}))
            self.cond.notify_all()
        return {}

    def sweep_stop(self):
        self.abort_sweep = True
        return {}

    def memread_stop(self):
        self.abort_memread = True
        return {}

    def _query(self, frame, n, poll=False):
        port = self.tr
        port.reset_input()
        port.write(frame)
        data = port.read(n, self.cfg["timeout_ms"] / 1000.0)
        self._log(frame, data, poll)
        if len(data) != n:
            self._stats_timeout()
            raise CatTimeout(f"no reply to {cat.hexs(frame)}")
        return data

    def _send(self, frame):
        port = self.tr
        port.reset_input()
        port.write(frame)
        if self.ack_mode:
            reply = port.read(1, min(0.25, self.cfg["timeout_ms"] / 1000.0))
            self._log(frame, reply)
            if reply:
                self.ack_miss = 0
                return reply[0]
            if self.state.get("radio") and self.ack_miss >= FAIL_LIMIT - 1:
                self.ack_miss += 1
                self._set(ack="delay")
                self._log(b"", b"", note="no ACK from radio: using a 60 ms delay")
            else:
                self.ack_miss += 1
            return None
        self._log(frame, b"")
        time.sleep(0.06)
        return None

    def _stats_timeout(self):
        stats = dict(self.state.get("stats") or {})
        stats["timeouts"] = int(stats.get("timeouts", 0)) + 1
        self._set(stats=stats)

    def _read_fm(self, poll=False):
        hz, mode, narrow = cat.parse_freq_mode(self._query(cat.frame(cat.OP_GET_FREQ), 5, poll))
        band = cat.band_of(hz, self.model)
        self._set(freq=hz, mode=mode, narrow=narrow, band=band[0] if band else None)
        self._publish_ee()
        return hz, mode, narrow

    def _read_tx(self, poll=False):
        data = cat.parse_tx_status(self._query(cat.frame(cat.OP_TX_STATUS), 1, poll)[0])
        self._set(tx=bool(data["tx"]), tx_bars=data["bars"], hi_swr=data["hi_swr"])
        return data

    def _read_rx(self, poll=False):
        data = cat.parse_rx_status(self._query(cat.frame(cat.OP_RX_STATUS), 1, poll)[0])
        self._set(**data)
        return data

    def _read_tm(self, poll=False):
        try:
            meter = cat.parse_tx_meter(self._query(cat.frame(cat.OP_TX_METER), 2, poll))
            self.tm_fails = 0
            self._set(tm=meter, tm_ok=True)
            return meter
        except cat.CatError:
            self.tm_fails += 1
            if self.tm_fails >= FAIL_LIMIT:
                self._set(tm_ok=False)
            raise

    def _ee_word(self, addr, poll=False):
        even = addr & -2
        data = self._query(cat.ee_read(even), 2, poll)
        self.ee[even] = data[0]
        self.ee[even + 1] = data[1]
        return data

    def _ee_bytes(self, addr, n):
        start = addr & -2
        out = bytearray()
        a = start
        while a < addr + n:
            out += self._ee_word(a)
            a += 2
        return bytes(out[addr - start:addr - start + n])

    def _band_addrs(self):
        hz = self.state.get("freq") or 0
        vfo = cat.ee_value(self.ee[85], cat.EE_FIELDS["vfo"]) if 85 in self.ee else "A"
        record = cat.band_record(hz, self.model, vfo)
        if record is None:
            return None, None
        band = cat.band_of(hz, self.model)
        return record + 1, (record + 2 if band[5] else None)

    def _publish_ee(self):
        if not self.ee:
            return
        out = {}
        for name, spec in cat.EE_FIELDS.items():
            if spec[0] in self.ee:
                out[name] = cat.ee_value(self.ee[spec[0]], spec)
        ipo, nar = self._band_addrs()
        if ipo is not None and ipo in self.ee:
            for name, bit in cat.BAND_FIELDS.items():
                out[name] = "ON" if (self.ee[ipo] >> bit) & 1 else "OFF"
        bit = cat.nar_bit(self.state.get("mode"))
        if nar is not None and nar in self.ee and bit is not None:
            out["nar"] = "ON" if (self.ee[nar] >> bit) & 1 else "OFF"
        group = cat.ant_group(self.state.get("freq") or 0)
        if group and cat.ANT_ADDR in self.ee:
            out["ant"] = "REAR" if (self.ee[cat.ANT_ADDR] >> group[3]) & 1 else "FRONT"
            out["ant_group"] = group[0]
        if "pwr" in out:
            out["pwr_w"] = cat.watts(self.model, out["pwr"])
        self._set(ee=out)

    def _detect_model(self):
        if self.model_sure or self.state.get("ee_ok") is False:
            return
        try:
            if 85 not in self.ee:
                self._ee_word(84)
            if 89 not in self.ee:
                self._ee_word(88)
            self._try_detect()
        except cat.CatError:
            pass

    def _try_detect(self):
        if self.model_sure or self.cfg.get("model") != "auto" or not self.state.get("freq"):
            return
        if 85 not in self.ee or 89 not in self.ee:
            return
        nibble = (self.ee[89] >> 4) if (self.ee[85] & 1) else (self.ee[89] & 0x0F)
        model = cat.detect_model(self.state["freq"], nibble)
        if model:
            self.model = model
            self.model_sure = True
            band = cat.band_of(self.state["freq"], model)
            self._set(model=model, model_sure=True, band=band[0] if band else None)
            self._log(b"", b"", note=f"model recognised: {cat.MODELS[model]['name']}")

    def _need_model(self):
        if not self.model_sure:
            self._detect_model()
        if not self.model_sure:
            raise cat.CatError(
                "model not recognised yet: put the radio in VFO on a band from 40 m up, or choose FT-817/FT-818"
            )

    def _ee_poll(self):
        if self.state.get("ee_ok") is False:
            return
        addrs = list(EE_ADDRESSES)
        record = cat.band_record(self.state.get("freq") or 0, self.model,
                                 cat.ee_value(self.ee[85], cat.EE_FIELDS["vfo"]) if 85 in self.ee else "A")
        if record is not None:
            addrs.extend([record & -2, (record + 2) & -2])
        addr = addrs[self.ee_turn % len(addrs)]
        self.ee_turn += 1
        try:
            self._ee_word(addr, poll=True)
            self.ee_fails = 0
            if self.state.get("ee_ok") is not True:
                self._set(ee_ok=True)
            self._publish_ee()
            self._try_detect()
        except cat.CatError:
            self.ee_fails += 1
            if self.ee_fails >= FAIL_LIMIT:
                self._set(ee_ok=False)
                raise

    def _band_spec(self, name, value):
        hz = self.state.get("freq") or 0
        if name in cat.BAND_FIELDS:
            self._need_model()
            ipo, _nar = self._band_addrs()
            if ipo is None:
                raise cat.CatError("IPO/ATT do not exist on this band")
            return ipo, cat.BAND_FIELDS[name], 1, ["OFF", "ON"], True
        if name == "nar":
            self._need_model()
            bit = cat.nar_bit(self.state.get("mode"))
            _ipo, nar = self._band_addrs()
            if nar is None or bit is None:
                raise cat.CatError("NAR only in FM, PKT, CW and DIG on an amateur band")
            return nar, bit, 1, ["OFF", "ON"], True
        if name == "ant":
            group = cat.ant_group(hz)
            if not group:
                raise cat.CatError("frequency outside coverage")
            return cat.ANT_ADDR, group[3], 1, cat.ANT_VALUES, True
        spec = cat.EE_FIELDS.get(name)
        if spec is None:
            raise cat.CatError(f"unknown EEPROM field: {name}")
        if not spec[4]:
            raise cat.CatError(f"{name} is read-only")
        return spec

    def _ee_set(self, name, value):
        if not self.cfg.get("ee_write"):
            raise cat.CatError("EEPROM writes are disabled: enable them in the connection dialog")
        if self.state.get("tx"):
            raise cat.CatError("refusing to write EEPROM while transmitting")
        if not self.state.get("freq"):
            raise cat.CatError("frequency unknown")
        spec = self._band_spec(name, value)
        raw = cat.ee_raw(value, spec)
        addr = spec[0]
        even = addr & -2
        word = bytearray(self._ee_word(even))
        old = bytes(word)
        index = addr - even
        word[index] = cat.field_set(word[index], spec[1], spec[2], raw)
        if bytes(word) != old:
            self._send(cat.ee_write(even, word[0], word[1]))
            check = bytearray(self._ee_word(even))
            if bytes(check) != bytes(word):
                raise cat.CatError("EEPROM read-back mismatch")
            self.ee[even] = check[0]
            self.ee[even + 1] = check[1]
        self._publish_ee()
        actual = cat.ee_value(self.ee[addr], spec)
        return {"value": actual}

    def _ee_refresh(self, addr):
        if self.state.get("ee_ok") is False:
            return
        try:
            self._ee_word(addr)
            self._publish_ee()
        except cat.CatError:
            pass

    def _key(self, on):
        if self.cfg.get("ptt") == "cat":
            self._send(cat.frame(cat.OP_PTT_ON if on else cat.OP_PTT_OFF))
        else:
            line = self.cfg.get("ptt")
            self.tr.set_line(line, on)
            self._log(b"", b"", note=f"PTT {'ON' if on else 'OFF'} on {str(line).upper()}")
        self.ptt_cat = bool(on)
        if on:
            self.ptt_start = time.monotonic()
            self._set(ptt_cat=True, ptt_left=self.cfg.get("tot_s"))
        else:
            time.sleep(0.15)
            self._set(ptt_cat=False, ptt_left=None)

    def _ptt_sync(self):
        if self.ptt_req and not self.ptt_cat:
            self._set(ptt_alarm="")
            self._key(True)
        elif not self.ptt_req and self.ptt_cat:
            self._key(False)
        if not self.ptt_req and self.tune_saved:
            self._tune_restore()
        try:
            self._read_tx()
        except cat.CatError:
            pass

    def _watchdog(self):
        if not self.ptt_cat:
            return
        now = time.monotonic()
        alarm = ""
        if now - self.ptt_beat > HEARTBEAT_S:
            alarm = "PTT released: connection with the page lost"
        elif now - self.ptt_start > self.cfg.get("tot_s", 180):
            alarm = f"PTT released: TOT of {self.cfg.get('tot_s', 180)} s exceeded"
        elif self.tune_saved and now - self.ptt_start > TUNE_MAX_S:
            alarm = f"TUNE interrupted after {TUNE_MAX_S} s"
        if alarm:
            self.ptt_req = False
            self.tune_want = False
            self._key(False)
            if self.tune_saved:
                self._tune_restore()
            self._set(ptt_alarm=alarm)
            return
        self._set(ptt_left=max(0, int(self.cfg.get("tot_s", 180) - (now - self.ptt_start))))

    def _plan(self):
        if not self.state.get("radio"):
            return ["fm"]
        steps = ["fm", "tx"]
        if self.state.get("tx") and self.state.get("tm_ok") is not False:
            steps.append("tm")
        if not self.state.get("tx"):
            steps.append("rx")
            if self.state.get("ee_ok") is not False:
                steps.append("ee")
        return steps

    def _poll(self, step):
        if step == "fm":
            self._read_fm(poll=True)
        elif step == "tx":
            self._read_tx(poll=True)
        elif step == "tm":
            self._read_tm(poll=True)
        elif step == "rx":
            self._read_rx(poll=True)
        elif step == "ee":
            self._ee_poll()

    def _run(self):
        next_cycle = 0.0
        while self.running:
            job = None
            with self.cond:
                if not self.queue:
                    self.cond.wait(max(0.01, next_cycle - time.monotonic()))
                if self.queue:
                    job = self.queue.popleft()
                    job.started = True
            if job is not None:
                self._exec(job)
                continue
            now = time.monotonic()
            if now < next_cycle:
                continue
            for step in self._plan():
                try:
                    self._poll(step)
                    self.poll_count += 1
                    self.fails = 0
                except cat.CatError as exc:
                    self.fails += 1
                    if self.fails >= FAIL_LIMIT:
                        self._set(error=str(exc))
                    break
                except Exception as exc:
                    stats = dict(self.state.get("stats") or {})
                    stats["errors"] = int(stats.get("errors", 0)) + 1
                    self._set(stats=stats, error=f"{type(exc).__name__}: {exc}")
                    break
                self._watchdog()
            elapsed = time.monotonic() - self.poll_mark
            if elapsed >= 1.0:
                rate = self.poll_count / elapsed
                self.poll_mark = time.monotonic()
                self.poll_count = 0
                self._set(stats={"rate": round(rate, 1),
                                 "timeouts": (self.state.get("stats") or {}).get("timeouts", 0),
                                 "errors": (self.state.get("stats") or {}).get("errors", 0)})
            next_cycle = time.monotonic() + self.cfg.get("poll_ms", 100) / 1000.0

    def _exec(self, job):
        try:
            result = self._do(job.op, job.args)
            job.finish(result=result or {})
        except cat.CatError as exc:
            job.finish(error=str(exc))
        except Exception as exc:
            job.finish(error=f"{type(exc).__name__}: {exc}")

    def _do(self, op, args):
        if op == "ptt_sync":
            self._ptt_sync()
            return {}
        if op == "tune_on":
            return self._tune_on()
        if op == "cw_ptt":
            on = bool(args.get("on"))
            if on and not self.ptt_cat:
                self._set(ptt_alarm="")
                self.ptt_beat = time.monotonic()
                self._key(True)
            elif not on and self.ptt_cat:
                self._key(False)
            return {}
        if op == "freq":
            self._send(cat.set_freq(int(args["hz"])))
            self._read_fm()
            if "seq" in args:
                self._set(tune_seq=int(args["seq"]))
            return {"freq": self.state.get("freq")}
        if op == "mode":
            self._send(cat.set_mode(args["mode"]))
            self._read_fm()
            return {}
        if op == "vfo_ab":
            self._send(cat.frame(cat.OP_VFO_AB))
            self._read_fm()
            self._ee_refresh(84)
            return {}
        if op == "split":
            self._send(cat.frame(cat.OP_SPLIT_ON if args["on"] else cat.OP_SPLIT_OFF))
            self._set_written(split=bool(args["on"]))
            self._ee_refresh(122)
            return {}
        if op == "lock":
            self._send(cat.frame(cat.OP_LOCK_ON if args["on"] else cat.OP_LOCK_OFF))
            self._set_written(lock=bool(args["on"]))
            return {}
        if op == "clar":
            self._send(cat.frame(cat.OP_CLAR_ON if args["on"] else cat.OP_CLAR_OFF))
            self._set_written(clar_on=bool(args["on"]))
            return {}
        if op == "clar_freq":
            hz = int(args["hz"])
            self._send(cat.clar_freq(hz))
            self._set_written(clar=hz)
            return {}
        if op == "rpt_shift":
            self._send(cat.rpt_shift(args["dir"]))
            self._set_written(rpt=args["dir"])
            return {}
        if op == "rpt_offset":
            self._send(cat.rpt_offset(int(args["hz"])))
            self._set_written(rpt_offset=int(args["hz"]))
            return {}
        if op == "tone_mode":
            self._send(cat.tone_mode(args["mode"]))
            self._set_written(tone_mode=args["mode"])
            return {}
        if op == "ctcss":
            tx = float(args["tx"])
            rx = float(args.get("rx", tx))
            self._send(cat.ctcss(tx, rx))
            self._set_written(ctcss=[tx, rx])
            return {}
        if op == "dcs":
            tx = int(args["tx"])
            rx = int(args.get("rx", tx))
            self._send(cat.dcs(tx, rx))
            self._set_written(dcs=[tx, rx])
            return {}
        if op == "power":
            return self._power(bool(args["on"]))
        if op == "ee_set":
            return self._ee_set(args["name"], args["value"])
        if op == "ee_read":
            addr = int(str(args["addr"]), 0)
            data = self._ee_word(addr)
            self._publish_ee()
            return {"addr": f"{addr & -2:04X}", "data": cat.hexs(data)}
        if op == "raw":
            return self._raw(args["hex"], args.get("n"))
        if op == "a_eq_b":
            return self._a_eq_b()
        if op == "swap":
            return self._swap()
        if op == "scope":
            return self._scope(args)
        if op == "swr_sweep":
            return self._swr_sweep(args)
        if op == "read_memories":
            return self._read_memories()
        if op == "batch":
            for sub in args["ops"]:
                sub = dict(sub)
                self._do(sub.pop("op"), sub)
            return {}
        raise cat.CatError(f"unknown operation: {op}")

    def _power(self, on):
        if on:
            self.tr.write(b"\xff\xff\xff\xff\xff")
            time.sleep(0.1)
            self.tr.write(cat.frame(cat.OP_PWR_ON))
            self._log(cat.frame(cat.OP_PWR_ON), b"", note="power on")
            self.fails = 0
            return {}
        if self.ptt_cat:
            self.ptt_req = False
            self._key(False)
        self._send(cat.frame(cat.OP_PWR_OFF))
        self._set(radio=False, tx=False, s=0, tx_bars=0, error="Radio powered off via CAT.")
        return {}

    def _raw(self, hexstr, n=None):
        data = bytes.fromhex(str(hexstr).replace(" ", "").replace(",", ""))
        if len(data) != cat.CMD_LEN:
            raise cat.CatError("a CAT command is exactly five bytes")
        if data[4] == cat.OP_RESET:
            raise cat.CatError("0xBE (radio reset) is blocked")
        if data[4] == cat.OP_EE_WRITE and not self.cfg.get("ee_write"):
            raise cat.CatError("0xBC (EEPROM write) requires EEPROM commands to be enabled")
        if data[4] == cat.OP_SET_MODE and data[0] not in cat.SET_MODES.values():
            raise cat.CatError(f"mode code {data[0]:02X} blocked: valid modes are {' '.join(f'{v:02X}' for v in cat.SET_MODES.values())}")
        n = int(n) if n not in (None, "") else cat.REPLY_LEN.get(data[4], 1)
        self.tr.reset_input()
        self.tr.write(data)
        reply = self.tr.read(n, self.cfg["timeout_ms"] / 1000.0) if n else b""
        self._log(data, reply, note="console")
        return {"reply": cat.hexs(reply), "n": len(reply)}

    def _a_eq_b(self):
        hz, mode, narrow = self._read_fm()
        target = mode_for_set(mode, narrow)
        self._send(cat.frame(cat.OP_VFO_AB))
        try:
            self._send(cat.set_freq(hz))
            if target:
                self._send(cat.set_mode(target))
            self._send(cat.frame(cat.OP_VFO_AB))
            self._read_fm()
            return {}
        except Exception:
            self._send(cat.frame(cat.OP_VFO_AB))
            raise

    def _swap(self):
        hz1, mode1, narrow1 = self._read_fm()
        self._send(cat.frame(cat.OP_VFO_AB))
        try:
            hz2, mode2, narrow2 = self._read_fm()
            self._send(cat.set_freq(hz1))
            if mode_for_set(mode1, narrow1):
                self._send(cat.set_mode(mode_for_set(mode1, narrow1)))
            self._send(cat.frame(cat.OP_VFO_AB))
            self._send(cat.set_freq(hz2))
            if mode_for_set(mode2, narrow2):
                self._send(cat.set_mode(mode_for_set(mode2, narrow2)))
            self._read_fm()
            return {}
        except Exception:
            self._send(cat.frame(cat.OP_VFO_AB))
            raise

    def _scope(self, args):
        if self.state.get("tx") or self.ptt_cat:
            raise cat.CatError("no panorama while transmitting")
        span = max(1000, min(1_000_000, int(args.get("span", 25_000))))
        points = max(11, min(201, int(args.get("points", 61))))
        dwell = max(0, min(500, int(args.get("dwell_ms", 30)))) / 1000.0
        center, mode, _narrow = self._read_fm()
        step = 2 * span / (points - 1)
        values = []
        self.abort_scope = False
        self._set(scope={
            "center": center, "span": span, "points": points, "mode": mode,
            "values": values, "running": True, "pos": 0, "t": time.time(), "aborted": False,
        })
        aborted = False
        try:
            for index in range(points):
                if self.abort_scope:
                    aborted = True
                    break
                hz = int(round((center - span + index * step) / 10.0)) * 10
                self._send(cat.set_freq(hz))
                if dwell:
                    time.sleep(dwell)
                data = self._read_rx(poll=True)
                values.append(data["s"])
                self._set(scope={
                    "center": center, "span": span, "points": points, "mode": mode,
                    "values": list(values), "running": True, "pos": index + 1,
                    "t": time.time(), "aborted": False,
                })
        finally:
            self._send(cat.set_freq(center))
            self._read_fm()
            self._set(scope={
                "center": center, "span": span, "points": points, "mode": mode,
                "values": list(values), "running": False, "pos": len(values),
                "t": time.time(), "aborted": aborted,
            })
        return {"aborted": aborted}

    def _tune_check(self):
        if self.ptt_cat or self.state.get("tx"):
            raise cat.CatError("the radio is already transmitting")
        if not self.cfg.get("ee_write") or self.state.get("ee_ok") is False:
            raise cat.CatError("TUNE and SWR measurement lower the power by writing EEPROM: enable EEPROM commands")

    def _tune_prepare(self):
        hz, mode, narrow = self._read_fm()
        spec = cat.EE_FIELDS["pwr"]
        word = self._ee_word(spec[0])
        power = cat.ee_value(word[spec[0] & 1], spec)
        self.tune_saved = {"mode": mode_for_set(mode, narrow), "pwr": power, "hz": hz}
        self._set(tune=dict(self.tune_saved, phase="setup"))
        try:
            if mode != "FM" or narrow:
                self._send(cat.set_mode("FM"))
            if power != TUNE_LEVEL:
                self._ee_set("pwr", TUNE_LEVEL)
        except cat.CatError:
            self._tune_restore()
            raise

    def _tune_restore(self):
        saved = self.tune_saved
        if not saved:
            return
        self.tune_saved = None
        errors = []
        if self.ptt_cat:
            self.ptt_req = False
            self._key(False)
        try:
            self._read_tx()
        except cat.CatError:
            pass
        try:
            if saved["pwr"] in cat.POWER_LEVELS and saved["pwr"] != TUNE_LEVEL:
                self._ee_set("pwr", saved["pwr"])
        except cat.CatError as exc:
            errors.append(str(exc))
        try:
            if saved["mode"]:
                self._send(cat.set_mode(saved["mode"]))
            self._read_fm()
        except cat.CatError as exc:
            errors.append(str(exc))
        self._set(tune=None)
        if errors:
            self._set(ptt_alarm="TUNE: settings not restored: " + "; ".join(errors))

    def _tune_on(self):
        if not self.tune_want:
            return {}
        try:
            self._tune_check()
            self._tune_prepare()
            if not self.tune_want:
                self._tune_restore()
                return {}
            self.ptt_req = True
            self.ptt_beat = time.monotonic()
            self._set(ptt_alarm="")
            self._key(True)
            self._set(tune=dict(self.tune_saved, phase="tx"))
            return {}
        except cat.CatError as exc:
            self._set(ptt_alarm=str(exc))
            raise

    def _swr_sweep(self, args):
        self._tune_check()
        center = self.state.get("freq") or 0
        band = cat.band_of(center, self.model)
        if not band:
            raise cat.CatError("frequency is not in an amateur band")
        lo = max(int(args.get("lo", band[1])), band[1])
        hi = min(int(args.get("hi", band[2])), band[2] - 10)
        span = max(1000, int(args.get("span", 50_000)))
        points = max(5, min(SWEEP_MAX_POINTS, int(args.get("points", 21))))
        settle = max(0.1, min(1.0, int(args.get("settle_ms", 300)) / 1000.0))
        whole = bool(args.get("whole_band"))
        if whole:
            f0, f1 = lo, hi
        else:
            f1 = min(hi, center + span)
            f0 = max(lo, center - span)
        if f1 - f0 < 1000:
            raise cat.CatError("measurement interval too narrow")
        self._tune_prepare()
        values = []
        self.abort_sweep = False
        source = "bd"
        self._set(swr={
            "center": center, "lo": f0, "hi": f1, "points": points, "values": [],
            "running": True, "pos": 0, "src": source, "t": time.time(), "error": "",
            "whole": whole,
        })
        try:
            self.ptt_req = True
            self.ptt_beat = time.monotonic()
            self._key(True)
            step = (f1 - f0) / (points - 1)
            for index in range(points):
                if self.abort_sweep:
                    break
                hz = int(round((f0 + index * step) / 10.0)) * 10
                self.ptt_beat = time.monotonic()
                self._send(cat.set_freq(hz))
                self._read_fm()
                time.sleep(settle)
                self.ptt_beat = time.monotonic()
                item = {"hz": hz}
                try:
                    meter = self._read_tm()
                    item.update({"swr": meter["ratio"], "raw": meter["swr"], "pwr": meter["pwr"],
                                 "bars": meter["bars"] if "bars" in meter else 0, "hi": False})
                except cat.CatError:
                    source = "f7"
                    data = self._read_tx()
                    item.update({"swr": None, "raw": None, "pwr": None, "bars": data["bars"], "hi": data["hi_swr"]})
                values.append(item)
                self._set(swr={
                    "center": center, "lo": f0, "hi": f1, "points": points, "values": list(values),
                    "running": True, "pos": index + 1, "src": source, "t": time.time(), "error": "",
                    "whole": whole,
                })
        finally:
            self.ptt_req = False
            try:
                self._key(False)
            except Exception:
                pass
            self._tune_restore()
            self._set(swr={
                "center": center, "lo": f0, "hi": f1, "points": points, "values": list(values),
                "running": False, "pos": len(values), "src": source, "t": time.time(), "error": "",
                "whole": whole,
            })
        return {"error": ""}

    def _read_memories(self):
        if self.state.get("tx") or self.ptt_cat:
            raise cat.CatError("the radio is already transmitting")
        if self.state.get("ee_ok") is False:
            raise cat.CatError("the radio does not answer EEPROM reads")
        self._need_model()
        layout = cat.mem_layout(self.model)
        self.abort_memread = False
        items = []
        progress = {
            "running": True, "pos": 0, "total": cat.MEM_COUNT, "found": 0,
            "bad": 0, "error": "", "t": time.time(),
        }
        self._set(memread=dict(progress))
        try:
            bitmap = self._ee_bytes(layout["visible"], 26)
            for n in range(1, cat.MEM_COUNT + 1):
                if self.abort_memread:
                    break
                progress["pos"] = n
                self._set(memread=dict(progress))
                if not cat.mem_used(bitmap, n):
                    continue
                try:
                    rec = self._ee_bytes(cat.mem_addr(n, self.model), cat.MEM_SIZE)
                    items.append(cat.decode_memory(rec, n))
                    progress["found"] = len(items)
                except cat.CatError:
                    progress["bad"] += 1
            progress["running"] = False
            progress["t"] = time.time()
            self._set(memread=dict(progress))
        except cat.CatError as exc:
            progress["running"] = False
            progress["error"] = str(exc)
            progress["t"] = time.time()
            self._set(memread=dict(progress))
            raise
        finally:
            self.mem_items = items
        return {"found": len(items), "bad": progress["bad"]}

    def radio_memories(self):
        return list(self.mem_items)

    def set_cw_config(self, config):
        return self.keyer.configure(config)

    def cw_send(self, text, live=False):
        return self.keyer.send(text, live)

    def cw_stop(self):
        self.keyer.stop()
        return {}

    def cw_beacon_set(self, on, text="", interval=60, repeat=0):
        return self.keyer.beacon(on, text, interval, repeat)

    def cw_nr_changed(self, nr):
        if self.cw_config_callback:
            try:
                self.cw_config_callback(self.keyer.config)
            except Exception:
                pass

    def cw_ptt(self, on):
        try:
            self.submit("cw_ptt", {"on": bool(on)}, wait=True, timeout=3.0)
        except cat.CatError:
            pass

    def cw_keepalive(self):
        self.ptt_beat = time.monotonic()
