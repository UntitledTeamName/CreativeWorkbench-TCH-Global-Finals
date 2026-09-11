"""Release artifact packaging, PEP 427 wheel conformance, and manifest synchronization tests.
Standard library unittest; zero cloud dependencies.
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import build_wheel
import build_skill
import runtime_manifest


class ReleasePackagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dist_dir = ROOT / "dist"
        cls.dist_dir.mkdir(exist_ok=True)
        # Build artifacts
        cls.wheel_path = build_wheel.build_wheel()
        cls.skill_path = build_skill.build_skill_zip()
        runtime_manifest.update_manifests(cls.wheel_path, cls.skill_path)

    def test_01_wheel_artifact_exists_and_named(self):
        self.assertTrue(self.wheel_path.is_file())
        self.assertEqual(self.wheel_path.name, "story_universe_architect_workbench-1.1.0-py3-none-any.whl")

    def test_02_wheel_pep427_contents(self):
        with zipfile.ZipFile(self.wheel_path, "r") as z:
            self.assertIsNone(z.testzip())
            namelist = z.namelist()

            # Python code
            self.assertIn("story_universe_architect/__init__.py", namelist)
            self.assertIn("story_universe_architect/model.py", namelist)
            self.assertIn("story_universe_architect/server.py", namelist)
            self.assertIn("story_universe_architect/store.py", namelist)
            self.assertIn("story_universe_architect/cli.py", namelist)
            self.assertIn("story_universe_architect/__main__.py", namelist)

            # Embedded web bundle
            self.assertIn("story_universe_architect/web/index.html", namelist)
            self.assertIn("story_universe_architect/web/style.css", namelist)
            self.assertIn("story_universe_architect/web/app.js", namelist)
            self.assertIn("story_universe_architect/web/core.js", namelist)

            # Schemas
            self.assertIn("story_universe_architect/schemas/universe.schema.json", namelist)
            self.assertIn("story_universe_architect/schemas/archetypes.json", namelist)
            self.assertIn("story_universe_architect/schemas/themes.json", namelist)

            # PEP 427 dist-info
            dist_info = "story_universe_architect_workbench-1.1.0.dist-info"
            self.assertIn(f"{dist_info}/METADATA", namelist)
            self.assertIn(f"{dist_info}/WHEEL", namelist)
            self.assertIn(f"{dist_info}/entry_points.txt", namelist)
            self.assertIn(f"{dist_info}/RECORD", namelist)

            # Check entry point definition
            ep_text = z.read(f"{dist_info}/entry_points.txt").decode("utf-8")
            self.assertIn("sua = story_universe_architect.cli:main", ep_text)

            # Check no .pyc files
            for n in namelist:
                self.assertFalse(n.endswith(".pyc"))
                self.assertNotIn("__pycache__", n)

    def test_03_skill_zip_contents(self):
        self.assertTrue(self.skill_path.is_file())
        self.assertEqual(self.skill_path.name, "StoryUniverseArchitect.zip")

        with zipfile.ZipFile(self.skill_path, "r") as z:
            self.assertIsNone(z.testzip())
            namelist = z.namelist()

            # SKILL.md
            self.assertIn("SKILL.md", namelist)

            # References
            self.assertIn("references/installation.json", namelist)
            self.assertIn("references/protocol.md", namelist)
            self.assertIn("references/universe.schema.json", namelist)

            # Scripts
            self.assertIn("scripts/story_universe_connect.py", namelist)
            self.assertIn("scripts/story_universe_cli.py", namelist)
            self.assertIn("scripts/story_universe_host.py", namelist)

    def test_04_manifest_consistency(self):
        release_json = ROOT / "release.json"
        runtime_json = ROOT / "runtime-manifest.json"
        install_json = ROOT / "skills" / "StoryUniverseArchitect" / "references" / "installation.json"

        rel_data = json.loads(release_json.read_text(encoding="utf-8"))
        rt_data = json.loads(runtime_json.read_text(encoding="utf-8"))
        inst_data = json.loads(install_json.read_text(encoding="utf-8"))

        self.assertEqual(rel_data["version"], "1.1.0")
        self.assertEqual(rt_data["version"], "1.1.0")
        self.assertEqual(inst_data["version"], "1.1.0")

        # Wheel SHA256 matches across all manifests
        wheel_sha = rel_data["runtime_sha256"]
        self.assertGreater(len(wheel_sha), 0)
        self.assertEqual(wheel_sha, rt_data["sha256"]["wheel"])
        self.assertEqual(wheel_sha, inst_data["sha256"])

    def test_05_cli_help_invocation(self):
        from story_universe_architect import cli
        with self.assertRaises(SystemExit) as cm:
            cli.main(["--help"])
        self.assertEqual(cm.exception.code, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
