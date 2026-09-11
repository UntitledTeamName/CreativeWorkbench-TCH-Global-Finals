"""WorkBuddy Skill integration, client connector, and protocol tests.
Verifies the 3 acquisition modes, client RPCs, and single-pass generation contracts.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "skills" / "StoryUniverseArchitect" / "scripts"))

from story_universe_architect import model, server, store
import story_universe_connect as connector


class WorkBuddyProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp_data = tempfile.TemporaryDirectory()
        cls.store = store.WorkspaceStore(cls.tmp_data.name)
        cls.restaurant = model.load_json(ROOT / "examples" / "restaurant.universe.json")
        cls.store.save_workspace("proto-restaurant", cls.restaurant)

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

    def test_01_skill_manifest_and_references(self):
        skill_dir = ROOT / "skills" / "StoryUniverseArchitect"
        self.assertTrue((skill_dir / "SKILL.md").is_file())

        ref_dir = skill_dir / "references"
        self.assertTrue((ref_dir / "installation.json").is_file())
        self.assertTrue((ref_dir / "protocol.md").is_file())
        self.assertTrue((ref_dir / "data-contract.md").is_file())
        self.assertTrue((ref_dir / "universe.schema.json").is_file())
        self.assertTrue((ref_dir / "archetypes.json").is_file())
        self.assertTrue((ref_dir / "themes.json").is_file())

        install_cfg = json.loads((ref_dir / "installation.json").read_text(encoding="utf-8"))
        self.assertEqual(install_cfg["version"], "1.1.0")
        self.assertIn("artifact", install_cfg)
        self.assertIn("sha256", install_cfg)

    def test_02_mode_1_local_dev_detection(self):
        source = connector.find_runtime_source()
        self.assertIsNotNone(source)
        self.assertTrue((source / "model.py").is_file())
        self.assertTrue((source / "server.py").is_file())

    def test_03_mode_2_installed_package_detection(self):
        # We have src/ on sys.path in this test run, so find_runtime_installed should resolve
        pkg = connector.find_runtime_installed()
        self.assertIsNotNone(pkg)
        self.assertEqual(pkg, "story_universe_architect")

    def test_04_connector_client_operations(self):
        client = connector.SUAClient(port=self.port)

        # Health
        health = client.health()
        self.assertEqual(health["status"], "ok")
        self.assertEqual(health["version"], "1.1.0")

        # List workspaces
        workspaces = client.list_workspaces()
        self.assertIsInstance(workspaces, list)
        self.assertTrue(any(w["id"] == "proto-restaurant" for w in workspaces))

        # Get workspace
        ws = client.get_workspace("proto-restaurant")
        self.assertEqual(ws["id"], "proto-restaurant")
        self.assertEqual(ws["universe"]["title"], self.restaurant["title"])

        # Patch workspace
        patch_res = client.patch_universe("proto-restaurant", {
            "tone": "Warm, fast-paced, emotionally resonant"
        })
        self.assertIsNotNone(patch_res)
        updated_ws = client.get_workspace("proto-restaurant")
        self.assertEqual(updated_ws["universe"]["tone"], "Warm, fast-paced, emotionally resonant")

        # Export formats
        for fmt in ["json", "prompts", "bible", "seeds", "svg"]:
            exported = client.export_workspace("proto-restaurant", fmt)
            self.assertIsNotNone(exported)
            self.assertGreater(len(exported), 0)

    def test_05_single_pass_generation_format_valid(self):
        sample_generated = copy.deepcopy(self.restaurant)
        sample_generated["id"] = "gen-cyber-detective"
        sample_generated["title"] = "Neon Shadows: Sector 4"
        sample_generated["concept"] = "A disgraced investigator and an rogue android technician track down memory thieves in a drowned megalopolis."
        sample_generated["format"] = "Limited series pilot"
        sample_generated["genre"] = "Cyberpunk Neo-Noir"
        sample_generated["tone"] = "Atmospheric, cynical, melancholic"
        sample_generated["revision"] = 1

        val = model.validate_universe(sample_generated)
        self.assertTrue(val["ok"], f"Generated universe validation errors: {val['errors']}")

        client = connector.SUAClient(port=self.port)
        create_res = client.publish_universe("gen-cyber-detective", sample_generated)
        self.assertEqual(create_res["id"], "gen-cyber-detective")

        retrieved = client.get_workspace("gen-cyber-detective")
        self.assertEqual(retrieved["universe"]["title"], "Neon Shadows: Sector 4")

    def test_06_sha256_verification_logic(self):
        content = b"SUA Wheel Mock Content"
        digest = hashlib.sha256(content).hexdigest()
        self.assertTrue(connector.verify_sha256_bytes(content, digest))
        self.assertFalse(connector.verify_sha256_bytes(content, "0" * 64))


if __name__ == "__main__":
    unittest.main(verbosity=2)
