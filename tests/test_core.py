"""Comprehensive core domain, model, compilers, and store tests.
Standard library unittest; zero external dependencies required.
"""
from __future__ import annotations

import copy
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from story_universe_architect import model, store


class CoreDomainTests(unittest.TestCase):
    def setUp(self):
        self.restaurant_path = ROOT / "examples" / "restaurant.universe.json"
        self.cyberpunk_path = ROOT / "examples" / "cyberpunk.universe.json"
        self.assertTrue(self.restaurant_path.is_file())
        self.assertTrue(self.cyberpunk_path.is_file())
        self.restaurant = model.load_json(self.restaurant_path)
        self.cyberpunk = model.load_json(self.cyberpunk_path)

    def test_01_examples_valid(self):
        res_val = model.validate_universe(self.restaurant)
        self.assertTrue(res_val["ok"], f"Restaurant validation errors: {res_val['errors']}")
        self.assertEqual(len(res_val["errors"]), 0)

        cp_val = model.validate_universe(self.cyberpunk)
        self.assertTrue(cp_val["ok"], f"Cyberpunk validation errors: {cp_val['errors']}")
        self.assertEqual(len(cp_val["errors"]), 0)

    def test_02_unknown_archetype(self):
        u = copy.deepcopy(self.restaurant)
        u["characters"][0]["archetype_id"] = "non-existent-archetype"
        val = model.validate_universe(u)
        self.assertFalse(val["ok"])
        self.assertTrue(any("non-existent-archetype" in err for err in val["errors"]))

    def test_03_character_validation(self):
        # Missing required field
        u = copy.deepcopy(self.restaurant)
        del u["characters"][0]["name"]
        val = model.validate_universe(u)
        self.assertFalse(val["ok"])

        # Duplicate character id
        u = copy.deepcopy(self.restaurant)
        u["characters"][1]["id"] = u["characters"][0]["id"]
        val = model.validate_universe(u)
        self.assertFalse(val["ok"])
        self.assertTrue(any("Duplicate character id" in err for err in val["errors"]))

        # Character count below minimum
        u = copy.deepcopy(self.restaurant)
        u["characters"] = [u["characters"][0]]
        val = model.validate_universe(u)
        self.assertFalse(val["ok"])

    def test_04_relationship_validation(self):
        # Relationship target not in characters
        u = copy.deepcopy(self.restaurant)
        invalid_rel = copy.deepcopy(u["relationships"][0])
        invalid_rel["id"] = "rel-invalid-target"
        invalid_rel["target"] = "char-ghost-404"
        u["relationships"].append(invalid_rel)
        val = model.validate_universe(u)
        self.assertFalse(val["ok"])
        self.assertTrue(any("Unknown endpoint" in err or "rel-invalid-target" in err for err in val["errors"]))

        # Self-referential relationship
        u = copy.deepcopy(self.restaurant)
        self_rel = copy.deepcopy(u["relationships"][0])
        self_rel["id"] = "rel-self"
        self_rel["target"] = self_rel["source"]
        u["relationships"].append(self_rel)
        val = model.validate_universe(u)
        self.assertFalse(val["ok"])
        self.assertTrue(any("Self edge" in err or "rel-self" in err for err in val["errors"]))

        # Duplicate relationship id
        u = copy.deepcopy(self.restaurant)
        u["relationships"].append(copy.deepcopy(u["relationships"][0]))
        val = model.validate_universe(u)
        self.assertFalse(val["ok"])
        self.assertTrue(any("Duplicate relationship id" in err for err in val["errors"]))

    def test_05_suggestion_validation(self):
        # Suggestion targeting non-existent character
        u = copy.deepcopy(self.restaurant)
        u["suggestions"][0]["relationships"][0]["target"] = "missing-char-id"
        val = model.validate_universe(u)
        self.assertFalse(val["ok"])

        # Suggestion depending on another pending suggestion's proposed character
        u = copy.deepcopy(self.restaurant)
        if len(u["suggestions"]) >= 2:
            target_id = u["suggestions"][1]["character"]["id"]
            u["suggestions"][0]["relationships"][0]["target"] = target_id
            val = model.validate_universe(u)
            self.assertFalse(val["ok"])

    def test_06_prompt_kit_compiler(self):
        kit = model.compile_prompt_kit(self.restaurant)
        self.assertIsInstance(kit, str)
        self.assertIn("visual asset prompt kit", kit)
        self.assertIn(self.restaurant["title"], kit)
        for char in self.restaurant["characters"]:
            self.assertIn(char["name"], kit)

    def test_07_creative_seeds_compiler(self):
        seeds = model.compile_creative_seeds(self.restaurant)
        self.assertIsInstance(seeds, str)
        self.assertIn("Creative Seeds", seeds)
        self.assertIn("Hook:", seeds)

    def test_08_markdown_bible_compiler(self):
        bible = model.compile_markdown_bible(self.restaurant)
        self.assertIsInstance(bible, str)
        self.assertIn(f"# {self.restaurant['title']}", bible)
        self.assertIn("## Approved cast", bible)
        self.assertIn("## Relationship map", bible)

    def test_09_svg_graph_compiler(self):
        svg = model.compile_svg_graph(self.restaurant)
        self.assertIsInstance(svg, str)
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("</svg>", svg)
        for char in self.restaurant["characters"]:
            self.assertIn(char["name"], svg)

    def test_10_assets_manifest_compiler(self):
        manifest = model.compile_assets_manifest(self.restaurant)
        self.assertIsInstance(manifest, list)
        self.assertGreaterEqual(len(manifest), 4)
        categories = {item["category"] for item in manifest}
        self.assertEqual(categories, {"portraits", "scenes", "presentation", "moodboard"})

    def test_11_export_formats(self):
        formats = ["json", "prompts", "seeds", "bible", "svg", "assets", "zip"]
        for fmt in formats:
            result = model.compile_export(self.restaurant, fmt)
            self.assertIsNotNone(result)
            if fmt == "zip":
                self.assertIsInstance(result, bytes)
                with zipfile.ZipFile(io.BytesIO(result)) as z:
                    self.assertIsNone(z.testzip())
                    names = z.namelist()
                    self.assertIn("universe.json", names)
                    self.assertIn("Character-Bible.md", names)
                    self.assertIn("Relationship-Graph.svg", names)
            elif fmt == "assets":
                self.assertIsInstance(result, str)
                parsed = json.loads(result)
                self.assertIsInstance(parsed, list)
            elif fmt == "json":
                self.assertIsInstance(result, str)
                parsed = json.loads(result)
                self.assertEqual(parsed["id"], self.restaurant["id"])
            else:
                self.assertIsInstance(result, str)

    def test_12_zip_export_unicode(self):
        u = copy.deepcopy(self.restaurant)
        u["title"] = "Café & 世界物語"
        zip_bytes = model.compile_export(u, "zip")
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            self.assertIsNone(z.testzip())
            content = z.read("universe.json").decode("utf-8")
            self.assertIn("Café & 世界物語", content)

    def test_13_canonical_json_and_fingerprint(self):
        canon1 = model.to_canonical_json(self.restaurant)
        canon2 = model.to_canonical_json(copy.deepcopy(self.restaurant))
        self.assertEqual(canon1, canon2)

        fp1 = model.compute_fingerprint(self.restaurant)
        fp2 = model.compute_fingerprint(copy.deepcopy(self.restaurant))
        self.assertEqual(fp1, fp2)
        self.assertIsInstance(fp1, str)
        self.assertGreater(len(fp1), 0)

    def test_14_max_json_safety_limit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            huge_file = Path(tmpdir) / "huge.json"
            huge_file.write_bytes(b" " * (model.MAX_JSON + 10))
            with self.assertRaises(ValueError):
                model.load_json(huge_file)

    def test_15_optional_jsonschema_conformance(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is not installed (optional dev dependency)")
        schema = model.SCHEMA
        jsonschema.Draft202012Validator(schema).validate(self.restaurant)
        jsonschema.Draft202012Validator(schema).validate(self.cyberpunk)


class WorkspaceStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.store = store.WorkspaceStore(self.tmpdir.name)
        self.restaurant = model.load_json(ROOT / "examples" / "restaurant.universe.json")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_01_save_and_get(self):
        saved = self.store.save_workspace("test-rest", self.restaurant)
        self.assertEqual(saved["workspace_id"], "test-rest")
        self.assertEqual(saved["universe"]["id"], self.restaurant["id"])

        loaded = self.store.get_workspace("test-rest")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["title"], self.restaurant["title"])

    def test_02_list_workspaces(self):
        self.store.save_workspace("ws-alpha", self.restaurant)
        cp = model.load_json(ROOT / "examples" / "cyberpunk.universe.json")
        self.store.save_workspace("ws-beta", cp)

        ws_list = self.store.list_workspaces()
        self.assertEqual(len(ws_list), 2)
        ids = {w["id"] for w in ws_list}
        self.assertIn("ws-alpha", ids)
        self.assertIn("ws-beta", ids)

    def test_03_delete_workspace(self):
        self.store.save_workspace("to-delete", self.restaurant)
        self.assertTrue(self.store.delete_workspace("to-delete"))
        self.assertFalse(self.store.delete_workspace("to-delete"))
        self.assertIsNone(self.store.get_workspace("to-delete"))

    def test_04_patch_concept_and_fields(self):
        self.store.save_workspace("patch-test", self.restaurant)
        initial_rev = self.restaurant["revision"]

        patch = {
            "concept": "A high-stakes fusion noodle bar facing an aggressive culinary syndicate takeover.",
            "tone": "Darker, satirical, intense"
        }
        updated = self.store.patch_workspace("patch-test", patch)
        self.assertEqual(updated["concept"], patch["concept"])
        self.assertEqual(updated["tone"], patch["tone"])
        self.assertEqual(updated["revision"], initial_rev + 1)

    def test_05_patch_characters_and_relationships(self):
        self.store.save_workspace("patch-rel-test", self.restaurant)
        new_char = copy.deepcopy(self.restaurant["characters"][0])
        new_char["id"] = "char-critic"
        new_char["name"] = "Evelyn Vance"
        new_char["role"] = "Feared culinary critic"

        updated = self.store.patch_workspace("patch-rel-test", {"characters": [new_char]})
        char_ids = [c["id"] for c in updated["characters"]]
        self.assertIn("char-critic", char_ids)

        new_rel = copy.deepcopy(self.restaurant["relationships"][0])
        new_rel["id"] = "rel-critic-chef"
        new_rel["source"] = "char-critic"
        new_rel["target"] = self.restaurant["characters"][0]["id"]
        new_rel["label"] = "inspector vs chef"

        updated2 = self.store.patch_workspace("patch-rel-test", {"relationships": [new_rel]})
        rel_ids = [r["id"] for r in updated2["relationships"]]
        self.assertIn("rel-critic-chef", rel_ids)

    def test_06_id_sanitization_prevents_traversal(self):
        target = "../../../evil-escaped"
        sanitized = store.sanitize_workspace_id(target)
        self.assertNotIn("..", sanitized)
        self.assertNotIn("/", sanitized)
        self.assertNotIn("\\", sanitized)



if __name__ == "__main__":
    unittest.main(verbosity=2)
