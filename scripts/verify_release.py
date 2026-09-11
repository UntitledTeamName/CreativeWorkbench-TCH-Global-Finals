"""Isolated End-to-End Release Verifier.
Validates installable artifacts in a pristine sandbox without workspace source tree dependencies.
Returns exit code 0 only on full verification pass.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"

WHEEL_NAME = "story_universe_architect_workbench-1.1.0-py3-none-any.whl"
SKILL_ZIP_NAME = "StoryUniverseArchitect.zip"


def log(msg: str):
    print(f"[VERIFY] {msg}", flush=True)


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def run_isolated_verification() -> int:
    wheel_file = DIST / WHEEL_NAME
    skill_zip = DIST / SKILL_ZIP_NAME

    if not wheel_file.is_file():
        sys.stderr.write(f"Error: Missing wheel artifact: {wheel_file}\n")
        return 1
    if not skill_zip.is_file():
        sys.stderr.write(f"Error: Missing skill zip artifact: {skill_zip}\n")
        return 1

    log(f"Found release artifacts in {DIST}")
    log(f"  - Wheel: {wheel_file.name} ({wheel_file.stat().st_size:,} bytes)")
    log(f"  - Skill: {skill_zip.name} ({skill_zip.stat().st_size:,} bytes)")

    with tempfile.TemporaryDirectory(prefix="sua-verify-") as temp_str:
        sandbox = Path(temp_str).resolve()
        log(f"Created isolated sandbox at: {sandbox}")

        # 1. Unpack wheel into isolated site-packages
        site_packages = sandbox / "site-packages"
        site_packages.mkdir()
        with zipfile.ZipFile(wheel_file, "r") as z:
            z.extractall(site_packages)
        log("Unpacked pure-Python wheel into sandbox site-packages.")

        # 2. Verify dist-info and embedded web bundle
        dist_info = site_packages / "story_universe_architect_workbench-1.1.0.dist-info"
        if not (dist_info / "METADATA").is_file():
            sys.stderr.write("Error: Missing METADATA in dist-info\n")
            return 1
        if not (dist_info / "entry_points.txt").is_file():
            sys.stderr.write("Error: Missing entry_points.txt in dist-info\n")
            return 1

        web_dir = site_packages / "story_universe_architect" / "web"
        if not (web_dir / "index.html").is_file() or not (web_dir / "app.js").is_file():
            sys.stderr.write("Error: Missing embedded web assets in wheel\n")
            return 1
        log("Wheel structure and embedded assets validated.")

        # 3. Test CLI from isolated environment
        env = os.environ.copy()
        env["PYTHONPATH"] = str(site_packages)
        env["PYTHONUTF8"] = "1"

        cli_cmd = [sys.executable, "-m", "story_universe_architect.cli", "--help"]
        res = subprocess.run(cli_cmd, env=env, capture_output=True, text=True, timeout=10)
        if res.returncode != 0 or "Story Universe Architect" not in res.stdout:
            sys.stderr.write(f"Error: CLI --help failed:\n{res.stderr}\n")
            return 1
        log("CLI entrypoint verified.")

        # 4. Start isolated server
        port = find_free_port()
        data_dir = sandbox / "workspaces"
        data_dir.mkdir()

        srv_cmd = [
            sys.executable,
            "-m",
            "story_universe_architect.server",
            "--port",
            str(port),
            "--data-dir",
            str(data_dir),
            "--no-browser",
        ]
        srv_proc = subprocess.Popen(
            srv_cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        try:
            # Poll /api/health
            base_url = f"http://127.0.0.1:{port}"
            deadline = time.time() + 10.0
            healthy = False
            while time.time() < deadline:
                try:
                    req = urllib.request.Request(
                        f"{base_url}/api/health",
                        headers={"Host": f"127.0.0.1:{port}"}
                    )
                    with urllib.request.urlopen(req, timeout=1) as resp:
                        if resp.status == 200:
                            data = json.loads(resp.read().decode("utf-8"))
                            if data.get("status") == "ok" and data.get("version") == "1.1.0":
                                healthy = True
                                break
                except Exception:
                    time.sleep(0.2)

            if not healthy:
                sys.stderr.write("Error: Isolated server failed health check.\n")
                return 1
            log(f"Isolated server running and healthy on 127.0.0.1:{port}.")

            # 5. REST operations test
            sample_uni = json.loads((ROOT / "examples" / "restaurant.universe.json").read_text(encoding="utf-8"))

            # Create workspace
            create_req = urllib.request.Request(
                f"{base_url}/api/workspaces",
                data=json.dumps({"id": "verify-ws", "universe": sample_uni}).encode("utf-8"),
                headers={"Host": f"127.0.0.1:{port}", "Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(create_req, timeout=5) as resp:
                if resp.status != 201:
                    sys.stderr.write(f"Error: POST /api/workspaces returned {resp.status}\n")
                    return 1

            # Patch workspace
            patch_req = urllib.request.Request(
                f"{base_url}/api/workspaces/verify-ws/universe",
                data=json.dumps({"concept": "Verified isolated runtime execution."}).encode("utf-8"),
                headers={"Host": f"127.0.0.1:{port}", "Content-Type": "application/json"},
                method="PATCH"
            )
            with urllib.request.urlopen(patch_req, timeout=5) as resp:
                if resp.status != 200:
                    sys.stderr.write(f"Error: PATCH /api/workspaces returned {resp.status}\n")
                    return 1

            # Test exports
            for fmt in ["json", "prompts", "bible", "seeds", "svg", "zip"]:
                exp_req = urllib.request.Request(
                    f"{base_url}/api/workspaces/verify-ws/export/{fmt}",
                    headers={"Host": f"127.0.0.1:{port}"}
                )
                with urllib.request.urlopen(exp_req, timeout=5) as resp:
                    if resp.status != 200:
                        sys.stderr.write(f"Error: Export format '{fmt}' returned {resp.status}\n")
                        return 1
            log("Isolated REST endpoints and export pipelines verified.")

            # Test web serving
            web_req = urllib.request.Request(
                f"{base_url}/?workspace=verify-ws",
                headers={"Host": f"127.0.0.1:{port}"}
            )
            with urllib.request.urlopen(web_req, timeout=5) as resp:
                if resp.status != 200:
                    sys.stderr.write(f"Error: Web index returned {resp.status}\n")
                    return 1
                body = resp.read().decode("utf-8")
                if "Story Universe Architect" not in body or "Verified isolated runtime execution." not in body:
                    sys.stderr.write("Error: Dynamic universe injection into HTML failed.\n")
                    return 1
            log("Web application serving and workspace injection verified.")

        finally:
            try:
                srv_proc.terminate()
                srv_proc.wait(timeout=3)
            except Exception:
                srv_proc.kill()

        # 6. Verify Skill ZIP extraction and Mode 3 simulation
        skill_unpack = sandbox / "skill_unpacked"
        skill_unpack.mkdir()
        with zipfile.ZipFile(skill_zip, "r") as z:
            z.extractall(skill_unpack)

        if not (skill_unpack / "SKILL.md").is_file():
            sys.stderr.write("Error: Skill ZIP missing SKILL.md\n")
            return 1
        inst_json_path = skill_unpack / "references" / "installation.json"
        if not inst_json_path.is_file():
            sys.stderr.write("Error: Skill ZIP missing references/installation.json\n")
            return 1

        inst_data = json.loads(inst_json_path.read_text(encoding="utf-8"))
        wheel_sha = hashlib.sha256(wheel_file.read_bytes()).hexdigest()
        if inst_data.get("sha256") != wheel_sha:
            sys.stderr.write(
                f"Error: Skill installation.json SHA256 mismatch!\n"
                f"  installation.json: {inst_data.get('sha256')}\n"
                f"  actual wheel:      {wheel_sha}\n"
            )
            return 1
        log("Skill package structure and cryptographic binding verified.")

    log("ALL RELEASE VERIFICATIONS PASSED SUCCESSFULLY.")
    return 0


if __name__ == "__main__":
    sys.exit(run_isolated_verification())
