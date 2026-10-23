import time
import unittest

import rig


def wait_for(predicate, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(0.02)
    return False


class RigTests(unittest.TestCase):
    def setUp(self):
        self.rig = rig.Rig()
        self.rig.connect({"sim": True, "model": "817", "ee_write": True, "poll_ms": 40})
        self.assertTrue(wait_for(lambda: self.rig.state["freq"] == 14_060_000))

    def tearDown(self):
        self.rig.disconnect()

    def test_frequency_and_mode(self):
        self.rig.submit("freq", {"hz": 7_100_000})
        self.assertTrue(wait_for(lambda: self.rig.state["freq"] == 7_100_000))
        self.assertEqual(self.rig.state["band"], "40")
        self.rig.submit("mode", {"mode": "USB"})
        self.assertTrue(wait_for(lambda: self.rig.state["mode"] == "USB"))

    def test_eeprom_write_readback(self):
        self.rig.submit("ee_set", {"name": "agc", "value": "FAST"})
        self.assertTrue(wait_for(lambda: self.rig.state["ee"].get("agc") == "FAST"))
        self.assertEqual(self.rig.submit("ee_read", {"addr": "0x57"})["data"], "00 01")

    def test_ptt_and_meter(self):
        self.rig.ptt(True)
        self.assertTrue(wait_for(lambda: self.rig.state["tx"] is True))
        self.assertTrue(wait_for(lambda: self.rig.state["tm"] is not None))
        self.rig.ptt(False)
        self.assertTrue(wait_for(lambda: self.rig.state["tx"] is False))

    def test_scope(self):
        result = self.rig.submit("scope", {"span": 10_000, "points": 11, "dwell_ms": 1})
        self.assertFalse(result["aborted"])
        self.assertEqual(len(self.rig.state["scope"]["values"]), 11)

    def test_cw_keeps_ptt_alive(self):
        self.rig.cw_send("PARIS PARIS", False)
        self.assertTrue(wait_for(lambda: self.rig.state["cw"].get("busy"), 2.0))
        self.assertTrue(wait_for(lambda: not self.rig.state["cw"].get("busy"), 10.0))
        self.assertEqual(self.rig.state.get("ptt_alarm"), "")
        self.assertGreaterEqual(len(self.rig.tr.key_log), 4)

    def test_full_band_swr(self):
        self.rig.submit("freq", {"hz": 7_100_000})
        self.assertTrue(wait_for(lambda: self.rig.state["freq"] == 7_100_000))
        result = self.rig.submit("swr_sweep", {
            "whole_band": True, "lo": 7_000_000, "hi": 7_300_000,
            "points": 11, "settle_ms": 100,
        })
        self.assertEqual(result["error"], "")
        values = self.rig.state["swr"]["values"]
        self.assertEqual(len(values), 11)
        self.assertLess(abs(values[0]["hz"] - 7_000_000), 20_000)
        self.assertLess(abs(values[-1]["hz"] - 7_300_000), 20_000)
        self.assertTrue(self.rig.state["swr"]["whole"])

    def test_read_memories(self):
        result = self.rig.submit("read_memories", {})
        self.assertEqual(result["found"], 10)
        memories = self.rig.radio_memories()
        self.assertTrue(any(m.get("name") == "CALL" for m in memories))
        self.assertTrue(all(100_000 <= m["f"] <= 470_000_000 for m in memories))


if __name__ == "__main__":
    unittest.main()
