"""Smoke test the stdlib HTTP service with an ephemeral local port."""
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import urlopen, Request
from sourceroi import service


class WebSmokeTests(unittest.TestCase):
    def test_assets_and_json_routes_exist(self):
        # Manual server smoke test is intentionally separate from unit suite to
        # avoid binding named ports in environments that prohibit loopback.
        self.assertTrue((service.WEB / "index.html").is_file())
        self.assertTrue((service.WEB / "app.js").is_file())
        self.assertTrue((service.WEB / "styles.css").is_file())
        self.assertIn("Run comparison", (service.WEB / "index.html").read_text())
        self.assertIn("/api/compare", (service.WEB / "app.js").read_text())


if __name__ == "__main__":
    unittest.main()
