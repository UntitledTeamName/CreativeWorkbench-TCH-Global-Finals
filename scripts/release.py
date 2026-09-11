"""Authoritative CharacterOS 7-Stage Release Pipeline.
Deterministically produces certified distributable artifacts under dist/ and executes
isolated end-to-end verification. Zero cloud or SaaS dependencies.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Force UTF-8 on Windows stdout/stderr
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
SCRIPTS = ROOT / "scripts"
TOOLS = ROOT / "tools"

sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(TOOLS))

import build_wheel
import build_skill
import runtime_manifest


def banner(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70, flush=True)


def fail(msg: str):
    sys.stderr.write(f"\n[RELEASE ERROR] {msg}\n")
    sys.exit(1)


def stage_1_clean():
    banner("Stage 1/7: Cleaning Build Artifacts")
    if DIST.is_dir():
        for item in DIST.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
    DIST.mkdir(exist_ok=True)

    for egg in ROOT.glob("*.egg-info"):
        if egg.is_dir():
            shutil.rmtree(egg)

    build_dir = ROOT / "build"
    if build_dir.is_dir():
        shutil.rmtree(build_dir)
    print("Cleaned dist/, build/, and egg-info directories.")


def stage_2_run_tests():
    banner("Stage 2/7: Running Source Test Suites")

    # JavaScript core tests
    print("Executing JavaScript test suite...")
    js_cmd = ["node", str(ROOT / "tests" / "core.test.cjs")]
    res_js = subprocess.run(js_cmd, cwd=str(ROOT), capture_output=True, text=True)
    if res_js.returncode != 0:
        sys.stderr.write(res_js.stderr)
        fail("JavaScript core test suite failed.")
    print("[PASS] All JavaScript tests passed.")

    # Python test suite
    print("Executing Python test suite...")
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    py_cmd = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]
    res_py = subprocess.run(py_cmd, cwd=str(ROOT), env=env, capture_output=True, text=True)
    if res_py.returncode != 0:
        sys.stderr.write(res_py.stderr)
        fail("Python test suite failed.")
    print("[PASS] All Python tests passed.")


def stage_3_build_wheel() -> Path:
    banner("Stage 3/7: Building Pure-Python Wheel")
    wheel_path = build_wheel.build_wheel()
    if not wheel_path.is_file():
        fail(f"Wheel build failed: {wheel_path}")
    print(f"[OK] Built wheel: {wheel_path.name} ({wheel_path.stat().st_size:,} bytes)")
    return wheel_path


def stage_4_update_manifests_wheel(wheel_path: Path):
    banner("Stage 4/7: Updating Manifest Digests for Wheel")
    runtime_manifest.update_manifests(wheel_path=wheel_path)
    print("[OK] Updated installation.json, release.json, and runtime-manifest.json with wheel digest.")


def stage_5_build_skill_zip() -> Path:
    banner("Stage 5/7: Building WorkBuddy Skill ZIP")
    skill_zip = build_skill.build_skill_zip()
    if not skill_zip.is_file():
        fail(f"Skill zip build failed: {skill_zip}")
    # Sync final skill zip hash into manifests
    runtime_manifest.update_manifests(skill_path=skill_zip)
    print(f"[OK] Built WorkBuddy Skill ZIP: {skill_zip.name} ({skill_zip.stat().st_size:,} bytes)")
    return skill_zip


def stage_6_generate_checksums(wheel_path: Path, skill_path: Path) -> Path:
    banner("Stage 6/7: Generating Cryptographic Release Manifest (MANIFEST.sha256)")
    manifest_file = DIST / "MANIFEST.sha256"

    wheel_sha = hashlib.sha256(wheel_path.read_bytes()).hexdigest()
    skill_sha = hashlib.sha256(skill_path.read_bytes()).hexdigest()

    lines = [
        f"{wheel_sha}  {wheel_path.name}",
        f"{skill_sha}  {skill_path.name}",
        ""
    ]
    manifest_file.write_text("\n".join(lines), encoding="utf-8")
    print(f"Generated {manifest_file.name}:")
    for line in lines[:-1]:
        print(f"  {line}")
    return manifest_file


def stage_7_verify_release():
    banner("Stage 7/7: Executing Isolated Release Verification")
    verify_script = SCRIPTS / "verify_release.py"
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    res = subprocess.run([sys.executable, str(verify_script)], cwd=str(ROOT), env=env)
    if res.returncode != 0:
        fail("Isolated release verification failed. Release aborted.")
    print("[OK] Isolated release verification succeeded.")


def main():
    banner("CHARACTEROS — OFFICIAL RELEASE PIPELINE (v1.1.0)")
    stage_1_clean()
    stage_2_run_tests()
    wheel_path = stage_3_build_wheel()
    stage_4_update_manifests_wheel(wheel_path)
    skill_path = stage_5_build_skill_zip()
    stage_6_generate_checksums(wheel_path, skill_path)
    stage_7_verify_release()

    banner("RELEASE SUCCESS: CERTIFIED ARTIFACTS IN dist/")
    for item in sorted(DIST.iterdir()):
        if item.is_file():
            size_kb = item.stat().st_size / 1024
            sha = hashlib.sha256(item.read_bytes()).hexdigest()[:16]
            print(f"  - {item.name:<58} {size_kb:>8.1f} KB  [{sha}...]")
    print("\nAll systems certified. Production release complete.\n")


if __name__ == "__main__":
    main()
