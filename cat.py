"""CAT protocol primitives for the Yaesu FT-817 / FT-817ND / FT-818ND.

Pure encoding and decoding only: no serial I/O and no global side effects.
A CAT block is five bytes, P1 P2 P3 P4 OPCODE. Frequencies are big-endian
BCD in 10 Hz units. This module is a clean-room implementation based on the
public Yaesu CAT documentation, the Hamlib FT-817 driver and the CHIRP
FT-817/FT-818 memory layout descriptions.
"""

from __future__ import annotations

CMD_LEN = 5

OP_LOCK_ON = 0x00
OP_LOCK_OFF = 0x80
OP_PTT_ON = 0x08
OP_PTT_OFF = 0x88
OP_SET_FREQ = 0x01
OP_GET_FREQ = 0x03
OP_SET_MODE = 0x07
OP_CLAR_ON = 0x05
OP_CLAR_OFF = 0x85
OP_CLAR_FREQ = 0xF5
OP_VFO_AB = 0x81
OP_SPLIT_ON = 0x02
OP_SPLIT_OFF = 0x82
OP_RPT_SHIFT = 0x09
OP_RPT_OFFSET = 0xF9
OP_TONE_MODE = 0x0A
OP_CTCSS_FREQ = 0x0B
OP_DCS_CODE = 0x0C
OP_RX_STATUS = 0xE7
OP_TX_STATUS = 0xF7
OP_PWR_ON = 0x0F
OP_PWR_OFF = 0x8F
OP_EE_READ = 0xBB
OP_EE_WRITE = 0xBC
OP_TX_METER = 0xBD
OP_RESET = 0xBE

REPLY_LEN = {
    OP_TX_METER: 2,
    OP_EE_READ: 2,
    OP_TX_STATUS: 1,
    OP_RX_STATUS: 1,
    OP_GET_FREQ: 5,
}

SWR_CAL = [1.0, 1.4, 1.8, 2.13, 2.25, 3.7, 6.0, 7.0, 8.0, 9.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0]

SET_MODES = {
    "LSB": 0,
    "USB": 1,
    "CW": 2,
    "CWR": 3,
    "AM": 4,
    "FM": 8,
    "DIG": 10,
    "PKT": 12,
}
MODE_ALIASES = {"FM-N": "FM"}
READ_MODES = {0: "LSB", 1: "USB", 2: "CW", 3: "CWR", 4: "AM", 6: "WFM", 8: "FM", 10: "DIG", 12: "PKT"}
DIG_MODES = ["RTTY", "PSK31-L", "PSK31-U", "USER-L", "USER-U"]
RPT_SHIFTS = {"-": 0x09, "+": 0x49, "S": 0x89}
TONE_MODES = {"OFF": 0x8A, "CTCSS": 0x2A, "CTCSS-ENC": 0x4A, "DCS": 0x0A}
POWER_LEVELS = ["HI", "L3", "L2", "L1"]

CTCSS_TONES = [
    67.0, 69.3, 71.9, 74.4, 77.0, 79.7, 82.5, 85.4, 88.5, 91.5, 94.8, 97.4,
    100.0, 103.5, 107.2, 110.9, 114.8, 118.8, 123.0, 127.3, 131.8, 136.5,
    141.3, 146.2, 151.4, 156.7, 159.8, 162.2, 165.5, 167.9, 171.3, 173.8,
    177.3, 179.9, 183.5, 186.2, 189.9, 192.8, 196.6, 199.5, 203.5, 206.5,
    210.7, 218.1, 225.7, 229.1, 233.6, 241.8, 250.3, 254.1,
]

DCS_CODES = [
    23, 25, 26, 31, 32, 36, 43, 47, 51, 53, 54, 65, 71, 72, 73, 74, 114, 115,
    116, 122, 125, 131, 132, 134, 143, 145, 152, 155, 156, 162, 165, 172, 174,
    205, 212, 223, 225, 226, 243, 244, 245, 246, 251, 252, 255, 261, 263, 265,
    266, 271, 274, 306, 311, 315, 325, 331, 332, 343, 346, 351, 356, 364, 365,
    371, 411, 412, 413, 423, 431, 432, 445, 446, 452, 454, 455, 462, 464, 465,
    466, 503, 506, 516, 523, 526, 532, 546, 565, 606, 612, 624, 627, 631, 632,
    654, 662, 664, 703, 712, 723, 731, 732, 734, 743, 754,
]

RX_RANGES = [(100_000, 56_000_000), (76_000_000, 154_000_000), (420_000_000, 470_000_000)]
CLAR_MAX = 9990

MODELS = {
    "817": {"name": "FT-817ND", "vfo_bands": 15, "watts": {"HI": 5.0, "L3": 2.5, "L2": 1.0, "L1": 0.5}},
    "818": {"name": "FT-818ND", "vfo_bands": 16, "watts": {"HI": 6.0, "L3": 5.0, "L2": 2.5, "L1": 1.0}},
}

BANDS = [
    ("160", 1_800_000, 2_000_000, 0, 0, True),
    ("80", 3_500_000, 4_000_000, 1, 1, True),
    ("60", 5_250_000, 5_450_000, None, 2, True),
    ("40", 7_000_000, 7_300_000, 2, 3, True),
    ("30", 10_100_000, 10_150_000, 3, 4, True),
    ("20", 14_000_000, 14_350_000, 4, 5, True),
    ("17", 18_068_000, 18_168_000, 5, 6, True),
    ("15", 21_000_000, 21_450_000, 6, 7, True),
    ("12", 24_890_000, 24_990_000, 7, 8, True),
    ("10", 28_000_000, 29_700_000, 8, 9, True),
    ("6", 50_000_000, 54_000_000, 9, 10, True),
    ("2", 144_000_000, 148_000_000, 12, 13, False),
    ("70", 430_000_000, 450_000_000, 13, 14, False),
]

VFO_BASE = 125
REC_SIZE = 26
MEM_COUNT = 200
MEM_SIZE = 26
MEM_MODES = ["LSB", "USB", "CW", "CWR", "AM", "FM", "DIG", "PKT"]
MEM_TMODES = {0: "OFF", 1: "CTCSS-ENC", 2: "CTCSS", 3: "DCS"}
_MEM_SHIFT = {"817": 0, "818": 52}

EE_FIELDS = {
    "vfo": (85, 0, 1, ["A", "B"], False),
    "nb": (87, 5, 1, ["OFF", "ON"], True),
    "agc": (87, 0, 2, ["AUTO", "FAST", "SLOW", "OFF"], True),
    "mtr": (88, 0, 2, ["PWR", "ALC", "SWR", "MOD"], True),
    "kyr": (88, 4, 1, ["OFF", "ON"], True),
    "bk": (88, 5, 1, ["OFF", "ON"], True),
    "vox": (88, 7, 1, ["OFF", "ON"], False),
    "dig": (101, 5, 3, DIG_MODES, True),
    "pri": (121, 3, 1, ["OFF", "ON"], False),
    "dw": (121, 4, 1, ["OFF", "ON"], False),
    "arts": (121, 7, 1, ["OFF", "ON"], False),
    "pwr": (121, 0, 2, POWER_LEVELS, True),
    "split": (122, 7, 1, ["OFF", "ON"], False),
}
ANT_ADDR = 122
ANT_GROUPS = [
    ("HF", 100_000, 50_000_000, 0),
    ("50", 50_000_000, 76_000_000, 1),
    ("BC", 76_000_000, 108_000_000, 2),
    ("AIR", 108_000_000, 144_000_000, 3),
    ("VHF", 144_000_000, 420_000_000, 4),
    ("UHF", 420_000_000, 470_000_001, 5),
]
ANT_VALUES = ["FRONT", "REAR"]
BAND_FIELDS = {"ipo": 5, "att": 4}


class CatError(Exception):
    pass


def band_index(band, model):
    return band[4] if model == "818" else band[3]


def band_of(hz, model=None):
    for band in BANDS:
        if band[1] <= hz < band[2] and band_index(band, model) is not None:
            return band
    return None


def band_record(hz, model, vfo=None):
    band = band_of(hz, model)
    if band is None:
        return None
    base = VFO_BASE + (MODELS[model]["vfo_bands"] * REC_SIZE if vfo == "B" else 0)
    return base + band_index(band, model) * REC_SIZE


def detect_model(hz, band_nibble):
    for band in BANDS:
        if not (band[1] <= hz < band[2]):
            continue
        if band[3] is None or band[3] == band[4]:
            continue
        if band_nibble == band[3]:
            return "817"
        if band_nibble == band[4]:
            return "818"
    return None


def bcd(value, digits):
    s = f"{int(value):0{digits}d}"
    if len(s) != digits:
        raise CatError(f"value {value} does not fit in {digits} BCD digits")
    return bytes((int(s[i]) << 4) | int(s[i + 1]) for i in range(0, digits, 2))


def from_bcd(data):
    value = 0
    for byte in data:
        lo = byte & 0x0F
        hi = byte >> 4
        if hi > 9 or lo > 9:
            raise CatError(f"invalid BCD: {data.hex(' ')}")
        value = value * 100 + hi * 10 + lo
    return value


def frame(op, p=b"\x00\x00\x00\x00"):
    p = bytes(p)
    if len(p) != 4:
        raise CatError("exactly four parameter bytes are required")
    return p + bytes([op])


def hexs(data):
    return data.hex(" ").upper()


def in_rx_range(hz):
    return any(lo <= hz <= hi for lo, hi in RX_RANGES)


def set_freq(hz):
    hz = int(round(hz / 10.0)) * 10
    if not in_rx_range(hz):
        raise CatError(f"{hz / 1e6:.5f} MHz is outside the FT-817/818 coverage")
    return frame(OP_SET_FREQ, bcd(hz // 10, 8))


def set_mode(name):
    name = MODE_ALIASES.get(name, name)
    if name not in SET_MODES:
        raise CatError(f"unknown mode: {name}")
    return frame(OP_SET_MODE, bytes([SET_MODES[name], 0, 0, 0]))


def clar_freq(hz):
    hz = int(round(hz / 10.0)) * 10
    if abs(hz) > CLAR_MAX:
        raise CatError("clarifier range is +/-9.99 kHz")
    return frame(OP_CLAR_FREQ, bytes([0xFF if hz < 0 else 0, 0]) + bcd(abs(hz) // 10, 4))


def rpt_shift(direction):
    if direction not in RPT_SHIFTS:
        raise CatError("shift must be '-', '+' or 'S'")
    return frame(OP_RPT_SHIFT, bytes([RPT_SHIFTS[direction], 0, 0, 0]))


def rpt_offset(hz):
    hz = int(round(hz / 10.0)) * 10
    if not 0 <= hz <= 99_999_990:
        raise CatError("repeater offset out of range")
    return frame(OP_RPT_OFFSET, bcd(hz // 10, 8))


def tone_mode(name):
    if name not in TONE_MODES:
        raise CatError(f"unknown tone mode: {name}")
    return frame(OP_TONE_MODE, bytes([TONE_MODES[name], 0, 0, 0]))


def ctcss(tx, rx=None):
    rx = tx if rx is None else rx
    for tone in (tx, rx):
        if tone not in CTCSS_TONES:
            raise CatError(f"unsupported CTCSS tone: {tone}")
    return frame(OP_CTCSS_FREQ, bcd(round(tx * 10), 4) + bcd(round(rx * 10), 4))


def dcs(tx, rx=None):
    rx = tx if rx is None else rx
    for code in (tx, rx):
        if code not in DCS_CODES:
            raise CatError(f"unsupported DCS code: {code:03d}")
    return frame(OP_DCS_CODE, bcd(tx, 4) + bcd(rx, 4))


def ee_read(addr):
    return frame(OP_EE_READ, bytes([(addr >> 8) & 0xFF, addr & 0xFE, 0, 0]))


def ee_write(addr, b0, b1):
    return frame(OP_EE_WRITE, bytes([(addr >> 8) & 0xFF, addr & 0xFE, b0 & 0xFF, b1 & 0xFF]))


def parse_freq_mode(data):
    if len(data) != 5:
        raise CatError("incomplete frequency/mode reply")
    hz = from_bcd(data[:4]) * 10
    raw = data[4]
    mode = READ_MODES.get(raw & 0x7F)
    if mode is None:
        raise CatError(f"unknown mode code: {raw & 0x7F:02X}")
    return hz, mode, bool(raw & 0x80)


def parse_rx_status(byte):
    return {
        "s": byte & 0x0F,
        "squelched": bool(byte & 0x80),
        "code_mismatch": bool(byte & 0x40),
        "disc_off": bool(byte & 0x20),
    }


def parse_tx_status(byte):
    tx = not bool(byte & 0x80)
    if tx:
        return {"tx": True, "hi_swr": bool(byte & 0x40), "bars": byte & 0x0F}
    return {"tx": None, "hi_swr": False, "bars": 0}


def parse_tx_meter(data):
    if len(data) != 2:
        raise CatError("incomplete TX meter reply")
    swr = data[1] >> 4
    return {
        "pwr": data[0] >> 4,
        "alc": data[0] & 0x0F,
        "swr": swr,
        "mod": data[1] & 0x0F,
        "ratio": SWR_CAL[swr],
    }


def swr_raw(ratio):
    raw = 0
    for index, value in enumerate(SWR_CAL):
        if ratio >= value:
            raw = index
    return raw


def s_text(n):
    return f"S{n}" if n <= 9 else f"S9+{(n - 9) * 10}"


def nar_bit(mode):
    if mode in ("FM", "PKT"):
        return 3
    if mode in ("CW", "CWR", "DIG"):
        return 4
    return None


def ant_group(hz):
    for group in ANT_GROUPS:
        if group[1] <= hz < group[2]:
            return group
    return None


def field_get(byte, lsb, width):
    return (byte >> lsb) & ((1 << width) - 1)


def field_set(byte, lsb, width, value):
    mask = ((1 << width) - 1) << lsb
    return (byte & ~mask) | ((value << lsb) & mask)


def ee_value(byte, spec):
    _addr, lsb, width, values, _writable = spec
    raw = field_get(byte, lsb, width)
    return values[raw] if raw < len(values) else f"?{raw}"


def ee_raw(value, spec):
    _addr, _lsb, _width, values, _writable = spec
    if value not in values or str(value).startswith("?"):
        raise CatError(f"value not allowed: {value}")
    return values.index(value)


def watts(model, level):
    return MODELS[model]["watts"].get(level)


def mem_layout(model):
    shift = _MEM_SHIFT[model]
    return {"visible": 1104 + shift, "filled": 1130 + shift, "base": 1156 + shift}


def mem_addr(n, model):
    return mem_layout(model)["base"] + (n - 1) * MEM_SIZE


def mem_used(bitmap, n):
    return bool((bitmap[(n - 1) // 8] >> ((n - 1) % 8)) & 1)


def decode_memory(rec, n):
    if len(rec) != MEM_SIZE:
        raise CatError("memory record is incomplete")
    mode = MEM_MODES[rec[0] & 7]
    narrow_fm = bool(rec[1] & 8)
    narrow_cw = bool(rec[1] & 16)
    if mode == "FM" and narrow_fm:
        mode = "FM-N"
    hz = int.from_bytes(rec[10:14], "big") * 10
    if not in_rx_range(hz):
        raise CatError(f"invalid frequency in memory {n}")
    out = {"ch": n, "f": hz, "m": mode}
    if narrow_cw and mode in ("CW", "CWR", "DIG"):
        out["narrow"] = True
    duplex = rec[1] >> 6
    offset = int.from_bytes(rec[14:18], "big") * 10
    if duplex in (1, 2):
        out["rpt"] = "-" if duplex == 1 else "+"
        out["off"] = offset
    elif duplex == 3 and in_rx_range(offset):
        out["tx"] = offset
    tone = MEM_TMODES[rec[4] & 3]
    if tone != "OFF":
        out["tone"] = tone
        if tone.startswith("CTCSS"):
            index = rec[6] & 0x3F
            out["ctcss"] = CTCSS_TONES[index] if index < len(CTCSS_TONES) else 88.5
        else:
            index = rec[7] & 0x7F
            out["dcs"] = DCS_CODES[index] if index < len(DCS_CODES) else 23
    name = ""
    for byte in rec[18:26]:
        if byte in (0, 255):
            break
        name += chr(byte) if 32 <= byte < 127 else "*"
    name = name.rstrip().strip("*")
    if name:
        out["name"] = name
    out["tag"] = bool(rec[0] & 0x80)
    return out


def encode_memory(hz, mode, name="", rpt="", off=0, tone_mode="OFF", ctcss=88.5, dcs=23):
    rec = bytearray(MEM_SIZE)
    base = "FM" if mode == "FM-N" else mode
    rec[0] = MEM_MODES.index(base) | (0x80 if name else 0)
    shift_code = {"-": 1, "+": 2}.get(rpt, 0)
    rec[1] = (shift_code << 6) | (0x20 if rpt in "-+" else 0) | (8 if mode == "FM-N" else 0)
    rec[4] = {value: key for key, value in MEM_TMODES.items()}.get(tone_mode, 0)
    rec[6] = CTCSS_TONES.index(ctcss) if ctcss in CTCSS_TONES else CTCSS_TONES.index(88.5)
    rec[7] = DCS_CODES.index(dcs) if dcs in DCS_CODES else DCS_CODES.index(23)
    rec[10:14] = int(hz // 10).to_bytes(4, "big")
    rec[14:18] = int(off // 10).to_bytes(4, "big")
    rec[18:26] = name.ljust(8)[:8].encode("ascii", "replace")
    return bytes(rec)
