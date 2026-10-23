import json
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import server


def request(base, path, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(base + path, data=data, method="POST" if body is not None else "GET")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        return json.loads(exc.read().decode())


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server.QUIT.clear()
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.httpd.daemon_threads = True
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        server.RIG.disconnect()
        server.QUIT.clear()

    def test_info(self):
        data = request(self.base, "/api/info")
        self.assertTrue(data["ok"])
        self.assertEqual(data["product"], "ft817-cleanroom")
        self.assertIn("817", data["models"])
        self.assertIn("agc", data["ee_fields"])

    def test_connect_and_command(self):
        data = request(self.base, "/api/connect", {"sim": True, "model": "818", "poll_ms": 40})
        self.assertTrue(data["ok"])
        end = time.monotonic() + 3
        while time.monotonic() < end:
            if request(self.base, "/api/state")["state"]["freq"]:
                break
            time.sleep(0.03)
        self.assertEqual(request(self.base, "/api/cmd", {"op": "freq", "hz": 7_100_000})["freq"], 7_100_000)
        self.assertTrue(request(self.base, "/api/cmd", {"op": "mode", "mode": "USB"})["ok"])
        state = request(self.base, "/api/state")["state"]
        self.assertEqual(state["model"], "818")
        self.assertEqual(state["band"], "40")

    def test_memories_roundtrip(self):
        data = request(self.base, "/api/memories", {"memories": [
            {"name": "TEST", "f": 14_060_000, "m": "CW"},
            {"name": "FM", "f": 145_500_000, "m": "FM"},
        ]})
        self.assertEqual(data["count"], 2)
        memories = request(self.base, "/api/memories")["memories"]
        self.assertEqual(len(memories), 2)
        self.assertEqual(memories[0]["name"], "TEST")
        request(self.base, "/api/memories", {"memories": []})

    def test_cw_config(self):
        config = request(self.base, "/api/cw")["config"]
        config["params"]["wpm"] = 25
        saved = request(self.base, "/api/cw", {"config": config})["config"]
        self.assertEqual(saved["params"]["wpm"], 25)
        config["params"]["wpm"] = 22
        request(self.base, "/api/cw", {"config": config})

    def test_unknown_endpoint(self):
        data = request(self.base, "/api/nope")
        self.assertFalse(data["ok"])


if __name__ == "__main__":
    unittest.main()

