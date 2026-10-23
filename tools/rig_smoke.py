import time

import cat
import rig

r = rig.Rig()
print("connect", r.connect({"sim": True, "model": "817", "ee_write": True, "poll_ms": 50}))
time.sleep(0.5)
print("state", r.state["freq"], r.state["mode"], r.state["band"], r.state["model"], r.state["ee"])
print("freq", r.submit("freq", {"hz": 7100000}))
time.sleep(0.2)
print("state", r.state["freq"], r.state["mode"], r.state["band"])
print("mode", r.submit("mode", {"mode": "USB"}))
time.sleep(0.2)
print("ee", r.submit("ee_set", {"name": "agc", "value": "FAST"}))
print("ee", r.state["ee"].get("agc"))
print("scope", r.submit("scope", {"span": 10000, "points": 11, "dwell_ms": 1}))
print("scope n", len(r.state["scope"]["values"]))
print("mem", r.submit("read_memories", {}))
print("mems", [(m["ch"], m["f"], m["m"], m.get("name")) for m in r.radio_memories()])
print("ptt on", r.ptt(True))
time.sleep(0.4)
print("tx", r.state["tx"], r.state["tm"], r.state["ptt_cat"])
print("ptt off", r.ptt(False))
time.sleep(0.3)
print("tx", r.state["tx"], r.state["ptt_cat"])
r.disconnect()
print("done")
