import unittest

import keyer


class KeyerTests(unittest.TestCase):
    def test_sanitize(self):
        config = keyer.sanitize({"params": {"wpm": 999}, "memories": [{"label": "X" * 30}]})
        self.assertEqual(config["params"]["wpm"], 60)
        self.assertEqual(len(config["memories"]), 8)
        self.assertEqual(len(config["memories"][0]["label"]), 12)

    def test_expand(self):
        station = {"mycall": "N0CALL", "call": "K1ABC", "rst": "579", "nr": 12, "loc": "JO20"}
        text = keyer.expand("{CALL} DE {MYCALL} RST {RST} NR {NR} {LOC}", station)
        self.assertEqual(text, "K1ABC DE N0CALL RST 579 NR 12 JO20")

    def test_marks(self):
        marks, text = keyer.build_marks("E", {"wpm": 20, "ratio": 3, "weight": 50, "comp_ms": 0, "cut": False}, {})
        self.assertEqual(text, "E")
        self.assertEqual(len(marks), 1)
        self.assertTrue(marks[0]["on"])
        self.assertAlmostEqual(marks[0]["ms"], 60, delta=2)

    def test_prosign(self):
        marks, text = keyer.build_marks("<AR>", {"wpm": 20, "ratio": 3, "weight": 50, "comp_ms": 0, "cut": False}, {})
        self.assertEqual(text, "<AR>")
        self.assertEqual(sum(1 for mark in marks if mark["on"]), 5)

    def test_cut_numbers(self):
        self.assertEqual(keyer.expand("90", {}, cut=True), "NT")


if __name__ == "__main__":
    unittest.main()

