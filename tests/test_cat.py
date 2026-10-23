import unittest

import cat


class CatTests(unittest.TestCase):
    def test_bcd_roundtrip(self):
        self.assertEqual(cat.bcd(1406000, 8), bytes.fromhex("01406000"))
        self.assertEqual(cat.from_bcd(bytes.fromhex("01406000")), 1406000)
        self.assertRaises(cat.CatError, cat.bcd, 12345, 2 * 2)

    def test_set_freq(self):
        self.assertEqual(cat.set_freq(14_060_000), bytes.fromhex("0140600001"))
        self.assertRaises(cat.CatError, cat.set_freq, 1_000)

    def test_modes(self):
        self.assertEqual(cat.set_mode("USB"), bytes.fromhex("0100000007"))
        self.assertEqual(cat.set_mode("FM-N"), bytes.fromhex("0800000007"))
        self.assertEqual(cat.parse_freq_mode(bytes.fromhex("0140600002")), (14_060_000, "CW", False))
        self.assertEqual(cat.parse_freq_mode(bytes.fromhex("0140600082")), (14_060_000, "CW", True))

    def test_band(self):
        self.assertEqual(cat.band_of(7_100_000, "817")[0], "40")
        self.assertEqual(cat.band_record(7_100_000, "817", "A"), 177)
        self.assertEqual(cat.band_record(7_100_000, "817", "B"), 567)
        self.assertIsNone(cat.band_of(5_357_000, "817"))
        self.assertEqual(cat.band_of(5_357_000, "818")[0], "60")
        self.assertEqual(cat.detect_model(7_100_000, 2), "817")
        self.assertEqual(cat.detect_model(7_100_000, 3), "818")
        self.assertIsNone(cat.detect_model(1_900_000, 0))

    def test_memory_roundtrip(self):
        record = cat.encode_memory(145_612_500, "FM", "RPT", "-", 600_000, "CTCSS-ENC", 88.5, 23)
        decoded = cat.decode_memory(record, 2)
        self.assertEqual(decoded["f"], 145_612_500)
        self.assertEqual(decoded["m"], "FM")
        self.assertEqual(decoded["rpt"], "-")
        self.assertEqual(decoded["off"], 600_000)
        self.assertEqual(decoded["tone"], "CTCSS-ENC")
        self.assertEqual(decoded["ctcss"], 88.5)
        self.assertEqual(decoded["name"], "RPT")
        self.assertTrue(decoded["tag"])

    def test_memory_layout(self):
        self.assertEqual(cat.mem_layout("817"), {"visible": 1104, "filled": 1130, "base": 1156})
        self.assertEqual(cat.mem_addr(1, "817"), 1156)
        self.assertEqual(cat.mem_addr(200, "817"), 1156 + 199 * 26)
        self.assertEqual(cat.mem_layout("818")["base"], 1208)
        self.assertTrue(cat.mem_used(bytes([1]), 1))
        self.assertFalse(cat.mem_used(bytes([1]), 2))

    def test_ee_fields(self):
        spec = cat.EE_FIELDS["agc"]
        self.assertEqual(cat.ee_value(0b10, spec), "SLOW")
        self.assertEqual(cat.ee_raw("SLOW", spec), 2)
        self.assertEqual(cat.field_set(0, 5, 1, 1), 0b100000)
        self.assertEqual(cat.field_get(0b100000, 5, 1), 1)

    def test_meters(self):
        self.assertEqual(cat.parse_tx_status(0xFF)["tx"], None)
        self.assertEqual(cat.parse_tx_status(0x02)["bars"], 2)
        meter = cat.parse_tx_meter(bytes([0xF0, 0x2A]))
        self.assertEqual((meter["pwr"], meter["alc"], meter["swr"], meter["mod"]), (15, 0, 2, 10))
        self.assertEqual(cat.s_text(10), "S9+10")


if __name__ == "__main__":
    unittest.main()

