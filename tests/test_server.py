"""HTTP server and REST API tests for Story Universe Architect runtime.
Standard library unittest with real local loopback HTTP server. Zero cloud dependencies.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from story_universe_architect import model, server, store


class ServerIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp_data = tempfile.TemporaryDirectory()
        cls.store = store.WorkspaceStore(cls.tmp_data.name)

        # Pre-seed with restaurant universe
        cls.restaurant = model.load_json(ROOT / "examples" / "restaurant.universe.json")
        cls.store.save_workspace("test-restaurant", cls.restaurant)

        # Configure and start server on loopback with port 0
        cls.httpd = server.create_server(
            host="127.0.0.1",
            port=0,
            store_instance=cls.store
        )
        cls.port = cls.httpd.server_port
        cls.base_url = f"http://127.0.0.1:{cls.port}"

        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.05)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.httpd.shutdown()
            cls.httpd.server_close()
        except Exception:
            pass
        cls.tmp_data.cleanup()

    def fetch(self, path: str, method: str = "GET", body: any = None, headers: dict = None):
        url = self.base_url + path
        h = {"Host": f"127.0.0.1:{self.port}"}
        if headers:
            h.update(headers)

        data = None
        if body is not None:
            if isinstance(body, (dict, list)):
                data = json.dumps(body).encode("utf-8")
                h.setdefault("Content-Type", "application/json; charset=utf-8")
            elif isinstance(body, str):
                data = body.encode("utf-8")
            elif isinstance(body, bytes):
                data = body

        req = urllib.request.Request(url, data=data, headers=h, method=method)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                raw = resp.read()
                return resp.status, resp.headers, raw
        except urllib.error.HTTPError as e:
            return e.code, e.headers, e.read()

    def test_01_health_endpoint(self):
        status, headers, raw = self.fetch("/api/health")
        self.assertEqual(status, 200)
        data = json.loads(raw.decode("utf-8"))
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["version"], "1.1.0")

    def test_02_status_endpoint_no_secrets(self):
        status, headers, raw = self.fetch("/api/status")
        self.assertEqual(status, 200)
        data = json.loads(raw.decode("utf-8"))
        self.assertIn("version", data)
        self.assertIn("workspaces_count", data)
        self.assertGreaterEqual(data["workspaces_count"], 1)

    def test_03_validate_endpoint_valid(self):
        status, headers, raw = self.fetch(
            "/api/validate",
            method="POST",
            body={"universe": self.restaurant}
        )
        self.assertEqual(status, 200)
        data = json.loads(raw.decode("utf-8"))
        self.assertTrue(data["ok"])
        self.assertEqual(len(data["errors"]), 0)

    def test_04_validate_endpoint_invalid(self):
        bad_u = dict(self.restaurant)
        bad_u["characters"] = []
        status, headers, raw = self.fetch(
            "/api/validate",
            method="POST",
            body={"universe": bad_u}
        )
        self.assertEqual(status, 422)
        data = json.loads(raw.decode("utf-8"))
        self.assertFalse(data["ok"])
        self.assertGreater(len(data["errors"]), 0)

    def test_05_workspaces_crud(self):
        # 1. List
        status, headers, raw = self.fetch("/api/workspaces")
        self.assertEqual(status, 200)
        ws_data = json.loads(raw.decode("utf-8"))
        ws_list = ws_data.get("workspaces", ws_data)
        self.assertTrue(any(w["id"] == "test-restaurant" for w in ws_list))

        # 2. Create new workspace
        cp = model.load_json(ROOT / "examples" / "cyberpunk.universe.json")
        status, headers, raw = self.fetch(
            "/api/workspaces",
            method="POST",
            body={"id": "cyber-city", "universe": cp}
        )
        self.assertEqual(status, 201)

        # 3. Get created workspace
        status, headers, raw = self.fetch("/api/workspaces/cyber-city")
        self.assertEqual(status, 200)
        ws_data = json.loads(raw.decode("utf-8"))
        self.assertEqual(ws_data["id"], "cyber-city")
        self.assertEqual(ws_data["universe"]["title"], cp["title"])

        # 4. Get workspace universe
        status, headers, raw = self.fetch("/api/workspaces/cyber-city/universe")
        self.assertEqual(status, 200)
        uni_data = json.loads(raw.decode("utf-8"))
        self.assertEqual(uni_data["id"], cp["id"])

        # 5. Patch universe
        status, headers, raw = self.fetch(
            "/api/workspaces/cyber-city/universe",
            method="PATCH",
            body={"tone": "Grittier, rain-drenched neon noir"}
        )
        self.assertEqual(status, 200)
        patched = json.loads(raw.decode("utf-8"))
        self.assertEqual(patched["tone"], "Grittier, rain-drenched neon noir")

        # 6. Delete workspace
        status, headers, raw = self.fetch("/api/workspaces/cyber-city", method="DELETE")
        self.assertEqual(status, 200)
        status, headers, raw = self.fetch("/api/workspaces/cyber-city")
        self.assertEqual(status, 404)

    def test_06_workspace_exports(self):
        formats = ["json", "bible", "prompts", "seeds", "svg", "zip"]
        for fmt in formats:
            status, headers, raw = self.fetch(f"/api/workspaces/test-restaurant/export/{fmt}")
            self.assertEqual(status, 200, f"Export {fmt} failed")
            self.assertGreater(len(raw), 0)

    def test_07_serves_html_and_assets(self):
        status, headers, raw = self.fetch("/")
        self.assertEqual(status, 200)
        content = raw.decode("utf-8")
        self.assertIn("Story Universe Architect", content)
        # Security headers
        self.assertEqual(headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")

    def test_08_security_rejects_untrusted_origin(self):
        status, headers, raw = self.fetch(
            "/api/status",
            headers={"Origin": "https://attacker.example.com"}
        )
        self.assertEqual(status, 403)

    def test_09_security_rejects_untrusted_host(self):
        status, headers, raw = self.fetch(
            "/api/status",
            headers={"Host": "attacker.example.com"}
        )
        self.assertEqual(status, 403)

    def test_10_security_rejects_path_traversal(self):
        traversals = ["/.env", "/../../etc/passwd", "/..%2f.env", "/secrets.json"]
        for path in traversals:
            status, headers, raw = self.fetch(path)
            self.assertIn(status, [403, 404])


if __name__ == "__main__":
    unittest.main(verbosity=2)
