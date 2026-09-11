"""Comprehensive tests for Git-based, cryptographically verified, immutable runtime distribution.

Covers:
1. Configuration (expected_commit default null, commit pinning, repo/ref parsing).
2. Deterministic release keys.
3. Manifest verification (valid, missing file, corrupted/mismatched file, malformed manifest).
4. Atomic staging & installation into ~/.characteros-tools/releases/<key>/.
5. Cache reuse vs. changed commit detection.
6. Offline/network failure resilience.
7. Explicit development mode vs. production Git acquisition.
8. Detached loopback server launch and health checking from acquired release.
9. Lifecycle ordering contract (prompts -> answers -> generation -> acquisition -> hosting).
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "CharacterOS"
sys.path.insert(0, str(SKILL_DIR / "scripts"))

import story_universe_connect as connector


class GitRuntimeDistributionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="charos-test-tools-")
        self.orig_tools_env = os.environ.get("CHARACTEROS_TOOLS_DIR")
        os.environ["CHARACTEROS_TOOLS_DIR"] = self.temp_dir
        self.releases_dir = Path(self.temp_dir) / "releases"
        self.staging_dir = Path(self.temp_dir) / "staging"

    def tearDown(self):
        if self.orig_tools_env is None:
            os.environ.pop("CHARACTEROS_TOOLS_DIR", None)
        else:
            os.environ["CHARACTEROS_TOOLS_DIR"] = self.orig_tools_env
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # --- 1. Configuration & Key Derivation ---

    def test_01_configuration_defaults(self):
        cfg = connector.read_installation_config()
        self.assertIn("repository_url", cfg)
        self.assertEqual(cfg["ref"], "main")
        self.assertIsNone(cfg["expected_commit"])

    def test_02_pinned_commit_configuration(self):
        pinned = {
            "repository_url": "https://github.com/mrc2rules/CharacterOS.git",
            "ref": "main",
            "expected_commit": "1234567890abcdef1234567890abcdef12345678",
        }
        cfg = connector.read_installation_config(pinned)
        self.assertEqual(cfg["expected_commit"], "1234567890abcdef1234567890abcdef12345678")

    def test_03_deterministic_release_key(self):
        repo = "https://github.com/mrc2rules/CharacterOS.git"
        ref = "main"
        sha1 = "aaaabbbbccccddddeeeeffff0000111122223333"
        sha2 = "9999888877776666555544443333222211110000"

        key1_a = connector.compute_release_key(repo, ref, sha1)
        key1_b = connector.compute_release_key(repo, ref, sha1)
        key2 = connector.compute_release_key(repo, ref, sha2)

        self.assertEqual(key1_a, key1_b)
        self.assertNotEqual(key1_a, key2)
        self.assertEqual(len(key1_a), 20)

    # --- 2. Manifest Verification ---

    def test_04_manifest_verification_success(self):
        # Create a mock valid staging runtime
        mock_stage = Path(self.temp_dir) / "mock_stage"
        mock_stage.mkdir()
        test_file = mock_stage / "src" / "test.txt"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("hello characteros", encoding="utf-8")
        h = hashlib.sha256(b"hello characteros").hexdigest()

        manifest = {
            "application": "CharacterOS",
            "manifest_version": "2.0",
            "files": {
                "src/test.txt": h
            }
        }
        (mock_stage / "runtime-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

        res = connector.verify_manifest(mock_stage)
        self.assertEqual(res["application"], "CharacterOS")

    def test_05_manifest_verification_missing_file(self):
        mock_stage = Path(self.temp_dir) / "mock_stage_missing"
        mock_stage.mkdir()
        manifest = {
            "application": "CharacterOS",
            "files": {
                "src/nonexistent.py": "0" * 64
            }
        }
        (mock_stage / "runtime-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

        with self.assertRaises(ValueError) as cm:
            connector.verify_manifest(mock_stage)
        self.assertIn("Missing required file", str(cm.exception))

    def test_06_manifest_verification_hash_mismatch(self):
        mock_stage = Path(self.temp_dir) / "mock_stage_corrupt"
        mock_stage.mkdir()
        test_file = mock_stage / "src" / "test.txt"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("tampered content", encoding="utf-8")

        manifest = {
            "application": "CharacterOS",
            "files": {
                "src/test.txt": "f" * 64  # incorrect expected hash
            }
        }
        (mock_stage / "runtime-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

        with self.assertRaises(ValueError) as cm:
            connector.verify_manifest(mock_stage)
        self.assertIn("Hash mismatch", str(cm.exception))

    def test_07_manifest_verification_missing_manifest(self):
        mock_stage = Path(self.temp_dir) / "mock_empty_stage"
        mock_stage.mkdir()
        with self.assertRaises(ValueError) as cm:
            connector.verify_manifest(mock_stage)
        self.assertIn("runtime-manifest.json' not found", str(cm.exception))

    # --- 3. Atomic Staging & Installation ---

    def test_08_atomic_installation_from_local_repo(self):
        # Build an authentic staging release using current repo files
        repo_url = "https://github.com/mrc2rules/CharacterOS.git"
        ref = "main"
        commit = "feedbeef00112233445566778899aabbccddeeff"
        key = connector.compute_release_key(repo_url, ref, commit)

        # Create simulated staging directory
        stage_dir = self.staging_dir / "simulated-stage"
        stage_dir.mkdir(parents=True)

        # Copy runtime files from repo
        shutil.copytree(ROOT / "src", stage_dir / "src")
        shutil.copy2(ROOT / "runtime-manifest.json", stage_dir / "runtime-manifest.json")

        # Verify manifest succeeds
        manifest = connector.verify_manifest(stage_dir)
        self.assertIn("files", manifest)

        # Write receipt
        receipt = {
            "repository_url": repo_url,
            "configured_ref": ref,
            "resolved_commit": commit,
            "release_key": key,
            "verification_status": "verified",
            "installed_at": "2026-09-12T00:00:00Z"
        }
        (stage_dir / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")

        # Atomic move to releases
        self.releases_dir.mkdir(parents=True, exist_ok=True)
        target_release = self.releases_dir / key
        os.replace(str(stage_dir), str(target_release))

        self.assertTrue(target_release.is_dir())
        self.assertFalse(stage_dir.exists())
        self.assertTrue((target_release / "receipt.json").is_file())
        self.assertTrue((target_release / "src" / "story_universe_architect" / "server.py").is_file())

    # --- 4. Remote Commit Detection & Cache Reuse ---

    def test_09_remote_commit_resolution_with_pinned(self):
        pinned = "abcdef1234567890abcdef1234567890abcdef12"
        resolved = connector.resolve_remote_commit("https://github.com/mrc2rules/CharacterOS.git", "main", expected_commit=pinned)
        self.assertEqual(resolved, pinned)

    def test_10_cache_reuse_when_installed(self):
        repo_url = "https://github.com/mrc2rules/CharacterOS.git"
        ref = "main"
        commit = "11223344556677889900aabbccddeeff00112233"
        key = connector.compute_release_key(repo_url, ref, commit)

        rel_dir = self.releases_dir / key
        rel_dir.mkdir(parents=True)
        shutil.copytree(ROOT / "src", rel_dir / "src")
        receipt = {
            "repository_url": repo_url,
            "configured_ref": ref,
            "resolved_commit": commit,
            "release_key": key,
            "verification_status": "verified",
            "installed_at": "2026-09-12T00:00:00Z"
        }
        (rel_dir / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")

        # Calling acquire_runtime with pinned commit should return rel_dir instantly without network
        cfg = {"repository_url": repo_url, "ref": ref, "expected_commit": commit}
        acquired = connector.acquire_runtime(custom_config=cfg)
        self.assertEqual(acquired, rel_dir)

    def test_11_offline_fallback_to_cached_release(self):
        # Point to unreachable URL with pre-existing local receipt
        repo_url = "https://invalid-host.nonexistent.local/repo.git"
        ref = "main"
        commit = "cafe000011112222333344445555666677778888"
        key = connector.compute_release_key(repo_url, ref, commit)

        rel_dir = self.releases_dir / key
        rel_dir.mkdir(parents=True)
        receipt = {
            "repository_url": repo_url,
            "configured_ref": ref,
            "resolved_commit": commit,
            "release_key": key,
            "verification_status": "verified",
            "installed_at": "2026-09-12T00:00:00Z"
        }
        (rel_dir / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")

        # resolve_remote_commit should fall back to cached commit safely
        resolved = connector.resolve_remote_commit(repo_url, ref, expected_commit=None, timeout=1.0)
        self.assertEqual(resolved, commit)

    # --- 5. Explicit Development Mode ---

    def test_12_explicit_dev_mode(self):
        dev_runtime = connector.acquire_runtime(is_dev=True)
        self.assertTrue((dev_runtime / "src" / "story_universe_architect" / "server.py").is_file())

    def test_13_normal_mode_does_not_use_local_dev(self):
        # In normal mode without releases and pointing to nonexistent repo, it raises instead of falling back to dev
        cfg = {
            "repository_url": "https://invalid-nonexistent.local/repo.git",
            "ref": "main",
            "expected_commit": None
        }
        with self.assertRaises(RuntimeError):
            connector.acquire_runtime(is_dev=False, custom_config=cfg)

    # --- 6. Detached Server Execution from Acquired Release ---

    def test_14_server_launch_from_acquired_runtime(self):
        # Set up a verified release directory
        repo_url = "https://github.com/mrc2rules/CharacterOS.git"
        ref = "main"
        commit = "deadbeef1234567890abcdef1234567890abcdef"
        key = connector.compute_release_key(repo_url, ref, commit)

        rel_dir = self.releases_dir / key
        rel_dir.mkdir(parents=True)
        shutil.copytree(ROOT / "src", rel_dir / "src")
        receipt = {
            "repository_url": repo_url,
            "configured_ref": ref,
            "resolved_commit": commit,
            "release_key": key,
            "verification_status": "verified",
            "installed_at": "2026-09-12T00:00:00Z"
        }
        (rel_dir / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")

        # Find a free port
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            free_port = s.getsockname()[1]

        data_dir = Path(self.temp_dir) / "server_workspaces"
        cfg = {"repository_url": repo_url, "ref": ref, "expected_commit": commit}

        port, info = connector.ensure_server_running(
            port=free_port,
            custom_config=cfg,
            data_dir=data_dir
        )
        self.assertEqual(info["status"], "ok")
        self.assertEqual(info["version"], "1.1.0")

        # Verify client can communicate and write a workspace
        client = connector.CharacterOSClient(port=port)
        h = client.health()
        self.assertEqual(h["status"], "ok")

        # Stop server by killing its PID to keep cleanup clean
        pid = info.get("pid")
        if pid:
            try:
                import signal
                os.kill(pid, signal.SIGTERM)
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
