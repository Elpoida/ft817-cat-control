"""Serial transport and a CAT-speaking FT-817/818 simulator."""

from __future__ import annotations

import math
import random
import threading
import time

import cat


class BackendError(Exception):
    pass


def have_pyserial():
    try:
        import serial  # noqa: F401
        return True
    except Exception:
        return False


def list_ports():
    try:
        from serial.tools import list_ports as lp
        return [{"device": p.device, "description": p.description or p.device} for p in lp.comports()]
    except Exception:
        return []


class SerialTransport:
    def __init__(self, port, baud, stopbits=2, dtr=False, rts=False):
        try:
            import serial
        except Exception as exc:
            raise BackendError("pyserial is not installed (pip install pyserial)") from exc
        try:
            s = serial.Serial()
            s.port = port
            s.baudrate = int(baud)
            s.bytesize = serial.EIGHTBITS
            s.parity = serial.PARITY_NONE
            s.stopbits = serial.STOPBITS_TWO if int(stopbits) == 2 else serial.STOPBITS_ONE
            s.timeout = 0.2
            s.write_timeout = 1
            s.rtscts = False
            s.dsrdtr = False
            s.dtr = bool(dtr)
            s.rts = bool(rts)
            s.open()
            self.s = s
            self.description = f"{port} {baud} 8N{stopbits}"
        except Exception as exc:
            raise BackendError(f"cannot open {port}: {exc}") from exc

    def write(self, data):
        self.s.write(data)
        self.s.flush()

    def read(self, n, timeout=0.3):
        self.s.timeout = timeout
        return self.s.read(n)

    def reset_input(self):
        self.s.reset_input_buffer()

    def set_line(self, name, on):
        if name == "rts":
            self.s.rts = bool(on)
        elif name == "dtr":
            self.s.dtr = bool(on)

    def close(self):
        try:
            self.s.close()
        except Exception:
            pass


class KeyPort:
    def __init__(self, port):
        try:
            import serial
        except Exception as exc:
            raise BackendError("pyserial is not installed (pip install pyserial)") from exc
        try:
            s = serial.Serial()
            s.port = port
            s.baudrate = 9600
            s.timeout = 0
            s.rtscts = False
            s.dsrdtr = False
            s.dtr = False
            s.rts = False
            s.open()
            self.s = s
        except Exception as exc:
            raise BackendError(f"cannot open {port}: {exc}") from exc

    def set_line(self, name, on):
        if name == "rts":
            self.s.rts = bool(on)
        else:
            self.s.dtr = bool(on)

    def close(self):
        try:
            self.s.dtr = False
            self.s.rts = False
            self.s.close()
        except Exception:
            pass


SIM_SIGNALS = [
    (1_840_000, 5, "dig"),
    (3_573_000, 7, "dig"),
    (3_650_000, 8, "ssb"),
    (3_712_000, 6, "ssb"),
    (5_357_000, 4, "dig"),
    (7_040_000, 5, "cw"),
    (7_074_000, 10, "dig"),
    (7_090_000, 9, "ssb"),
    (7_155_000, 12, "ssb"),
    (10_120_000, 4, "cw"),
    (10_136_000, 8, "dig"),
    (14_025_000, 6, "cw"),
    (14_074_000, 11, "dig"),
    (14_100_000, 7, "beacon"),
    (14_195_000, 9, "ssb"),
    (14_230_000, 7, "ssb"),
    (18_100_000, 6, "dig"),
    (18_130_000, 8, "ssb"),
    (21_074_000, 9, "dig"),
    (21_250_000, 6, "ssb"),
    (24_915_000, 5, "dig"),
    (28_074_000, 7, "dig"),
    (28_480_000, 6, "ssb"),
    (50_313_000, 6, "dig"),
    (98_300_000, 15, "wfm"),
    (101_500_000, 13, "wfm"),
    (118_700_000, 7, "am"),
    (145_500_000, 9, "fm"),
    (145_612_500, 14, "fm"),
    (145_775_000, 9, "fm"),
    (433_500_000, 8, "fm"),
    (431_525_000, 12, "fm"),
    (439_100_000, 9, "fm"),
]

SIM_ANTENNA = {
    "160": (1_855_000, 18_000),
    "80": (3_640_000, 70_000),
    "60": (5_357_000, 40_000),
    "40": (7_085_000, 110_000),
    "30": (10_125_000, 90_000),
    "20": (14_180_000, 240_000),
    "17": (18_110_000, 160_000),
    "15": (21_230_000, 300_000),
    "12": (24_940_000, 200_000),
    "10": (28_550_000, 650_000),
    "6": (50_350_000, 900_000),
    "2": (145_200_000, 3_000_000),
    "70": (433_800_000, 9_000_000),
}

PASSBAND = {"LSB": 2400, "USB": 2400, "CW": 600, "CWR": 600, "AM": 6000, "FM": 12000, "WFM": 150000, "DIG": 2400, "PKT": 12000}


def sim_swr(hz):
    band = cat.band_of(hz)
    if not band or band[0] not in SIM_ANTENNA:
        return 9.0
    center, width = SIM_ANTENNA[band[0]]
    x = (hz - center) / width
    return min(9.5, 1.08 + 2.1 * x * x)


def _initial_memories(model):
    rows = [
        (1, 145_500_000, "FM", "CALL"),
        (2, 145_612_500, "FM", "RPT-1", "-", 600_000, "CTCSS-ENC", 88.5, 23),
        (3, 433_500_000, "FM", "UHF"),
        (5, 145_500_000, "FM-N", "NARROW"),
        (7, 433_500_000, "FM", "DCS", "", 0, "DCS", 88.5, 754),
        (10, 7_030_000, "CW", "QRP 40"),
        (11, 14_060_000, "CW", "QRP 20"),
        (12, 14_285_000, "USB", "QRP SSB"),
        (20, 10_116_000, "CW", "QRP 30"),
        (150, 28_360_000, "USB", "10M"),
    ]
    out = []
    for row in rows:
        n, hz, mode, name = row[:4]
        rpt = row[4] if len(row) > 4 else ""
        off = row[5] if len(row) > 5 else 0
        tone = row[6] if len(row) > 6 else "OFF"
        ctcss = row[7] if len(row) > 7 else 88.5
        dcs = row[8] if len(row) > 8 else 23
        out.append((n, cat.encode_memory(hz, mode, name, rpt, off, tone, ctcss, dcs)))
    return out


class SimulatedFT817:
    def __init__(self, model="817"):
        self.model = model
        self.description = f"{cat.MODELS[model]['name']} simulator"
        self.lock = threading.RLock()
        self.rx = bytearray()
        self.inbuf = bytearray()
        self.t0 = time.monotonic()
        self.powered = True
        self.hung = False
        self.lines = {"dtr": False, "rts": False}
        self.key_log = []
        self.vfo = [{"hz": 14_060_000, "mode": 2}, {"hz": 145_500_000, "mode": 8}]
        self.clar_on = False
        self.clar = 0
        self.ptt = False
        self.rpt = "S"
        self.rpt_offset = 600_000
        self.tone_mode = "OFF"
        self.ctcss = (88.5, 88.5)
        self.dcs = (23, 23)
        self.ee = bytearray(7168)
        self.ee[85] = 0
        self.ee[87] = 0
        self.ee[88] = 0
        self.ee[101] = 64
        self.ee[121] = 0
        self.ee[122] = 0x30
        self._set_band_nibble(0)
        self._set_band_nibble(1)
        layout = cat.mem_layout(model)
        for n, rec in _initial_memories(model):
            addr = cat.mem_addr(n, model)
            self.ee[addr:addr + cat.MEM_SIZE] = rec
            self.ee[layout["visible"] + (n - 1) // 8] |= 1 << ((n - 1) % 8)

    @property
    def sel(self):
        return self.ee[85] & 1

    @property
    def cur(self):
        return self.vfo[self.sel]

    def _mode_name(self):
        return cat.READ_MODES.get(self.cur["mode"] & 0x7F, "USB")

    def _set_band_nibble(self, index):
        band = cat.band_of(self.vfo[index]["hz"], self.model)
        if band is None:
            return
        value = cat.band_index(band, self.model)
        if index:
            self.ee[89] = (self.ee[89] & 0x0F) | ((value & 0x0F) << 4)
        else:
            self.ee[89] = (self.ee[89] & 0xF0) | (value & 0x0F)

    def _ack(self):
        self.rx.append(0)

    def write(self, data):
        with self.lock:
            self.inbuf += data
            while len(self.inbuf) >= cat.CMD_LEN:
                block = bytes(self.inbuf[:cat.CMD_LEN])
                del self.inbuf[:cat.CMD_LEN]
                self._command(block)

    def read(self, n, timeout=0.3):
        time.sleep(0.003)
        with self.lock:
            out = bytes(self.rx[:n])
            del self.rx[:n]
            return out

    def reset_input(self):
        with self.lock:
            self.rx.clear()

    def set_line(self, name, on):
        on = bool(on)
        with self.lock:
            if self.lines.get(name) != on:
                self.lines[name] = on
                self.key_log.append((time.perf_counter(), name, on))
                del self.key_log[:-4000]

    def close(self):
        pass

    def _command(self, block):
        p = block[:4]
        op = block[4]
        if self.hung:
            return
        if not self.powered:
            if op == cat.OP_PWR_ON:
                self.powered = True
            return
        if op == cat.OP_LOCK_ON or op == cat.OP_LOCK_OFF:
            self._ack()
        elif op == cat.OP_PTT_ON:
            self.ptt = True
            self._ack()
        elif op == cat.OP_PTT_OFF:
            self.ptt = False
            self._ack()
        elif op == cat.OP_SET_FREQ:
            hz = cat.from_bcd(p) * 10
            if cat.in_rx_range(hz):
                self.cur["hz"] = hz
                self._set_band_nibble(self.sel)
            self._ack()
        elif op == cat.OP_GET_FREQ:
            hz = self.cur["hz"]
            raw = self.cur["mode"] & 0x7F
            if self.cur["mode"] & 0x80:
                raw |= 0x80
            self.rx += cat.bcd(hz // 10, 8) + bytes([raw])
        elif op == cat.OP_SET_MODE:
            code = p[0]
            if code in cat.SET_MODES.values():
                self.cur["mode"] = code
            self._ack()
        elif op == cat.OP_CLAR_ON:
            self.clar_on = True
            self._ack()
        elif op == cat.OP_CLAR_OFF:
            self.clar_on = False
            self._ack()
        elif op == cat.OP_CLAR_FREQ:
            sign = -1 if p[0] == 0xFF else 1
            self.clar = sign * cat.from_bcd(p[2:4]) * 10
            self._ack()
        elif op == cat.OP_VFO_AB:
            self.ee[85] = self.ee[85] ^ 1
            self._ack()
        elif op == cat.OP_SPLIT_ON:
            self.ee[122] |= 0x80
            self._ack()
        elif op == cat.OP_SPLIT_OFF:
            self.ee[122] &= 0x7F
            self._ack()
        elif op == cat.OP_RPT_SHIFT:
            self.rpt = {0x09: "-", 0x49: "+", 0x89: "S"}.get(p[0], "S")
            self._ack()
        elif op == cat.OP_RPT_OFFSET:
            self.rpt_offset = cat.from_bcd(p) * 10
            self._ack()
        elif op == cat.OP_TONE_MODE:
            self.tone_mode = {0x8A: "OFF", 0x2A: "CTCSS", 0x4A: "CTCSS-ENC", 0x0A: "DCS"}.get(p[0], "OFF")
            self._ack()
        elif op == cat.OP_CTCSS_FREQ:
            self.ctcss = (cat.from_bcd(p[0:2]) / 10.0, cat.from_bcd(p[2:4]) / 10.0)
            self._ack()
        elif op == cat.OP_DCS_CODE:
            self.dcs = (cat.from_bcd(p[0:2]), cat.from_bcd(p[2:4]))
            self._ack()
        elif op == cat.OP_RX_STATUS:
            self.rx.append(self._rx_status())
        elif op == cat.OP_TX_STATUS:
            self.rx.append(self._tx_status())
        elif op == cat.OP_PWR_ON:
            self.powered = True
            self._ack()
        elif op == cat.OP_PWR_OFF:
            self.powered = False
            self.ptt = False
        elif op == cat.OP_EE_READ:
            addr = (p[0] << 8) | p[1]
            self.rx += self.ee[addr:addr + 2]
        elif op == cat.OP_EE_WRITE:
            addr = (p[0] << 8) | p[1]
            self.ee[addr] = p[2]
            self.ee[addr + 1] = p[3]
            self._ack()
        elif op == cat.OP_TX_METER:
            if self.ptt:
                self.rx += self._tx_meter()
            else:
                self.rx += b"\x00\x00"
        else:
            self._ack()

    def _signal_strength(self, hz):
        t = time.monotonic() - self.t0
        level = 1 + int((math.sin(t * 1.7) + 1.0))
        for freq, strength, kind in SIM_SIGNALS:
            width = 2_500 if kind == "cw" else 3_000 if kind == "ssb" else 15_000
            if abs(hz - freq) <= width:
                level = max(level, strength + int(round(math.sin(t * 0.9) * 1.2)))
        return max(0, min(15, level))

    def _rx_status(self):
        hz = self.cur["hz"] + (self.clar if self.clar_on else 0)
        level = self._signal_strength(hz)
        byte = level & 0x0F
        if level <= 1:
            byte |= 0x80
        return byte

    def _tx_meter(self):
        hz = self.cur["hz"]
        watts = cat.MODELS[self.model]["watts"]
        level = cat.POWER_LEVELS[self.ee[121] & 3]
        k = watts[level] / watts["HI"]
        mode = self._mode_name()
        if mode in ("LSB", "USB"):
            k *= random.uniform(0.2, 1.0)
        elif mode == "AM":
            k *= 0.25
        ratio = sim_swr(hz)
        return bytes([(int(k * 15) << 4) | 15, (cat.swr_raw(ratio) << 4) | random.randint(3, 9)])

    def _tx_status(self):
        if not self.ptt:
            return 0xFF
        hz = self.cur["hz"]
        watts = cat.MODELS[self.model]["watts"]
        level = cat.POWER_LEVELS[self.ee[121] & 3]
        k = watts[level] / watts["HI"]
        mode = self._mode_name()
        if mode in ("LSB", "USB"):
            k *= random.uniform(0.2, 1.0)
        elif mode == "AM":
            k *= 0.25
        ratio = sim_swr(hz)
        hi_swr = ratio > 3.0
        mtr = self.ee[88] & 3
        if mtr == 2:
            bars = cat.swr_raw(ratio)
        elif mtr == 1:
            bars = int(k * 6)
        elif mtr == 3:
            bars = random.randint(3, 9) if mode in ("LSB", "USB", "AM", "FM") else 0
        else:
            bars = int(round(k * 10))
        split = 0x20 if self.ee[122] & 0x80 else 0
        return (0x40 if hi_swr else 0) | split | (bars & 0x0F)
