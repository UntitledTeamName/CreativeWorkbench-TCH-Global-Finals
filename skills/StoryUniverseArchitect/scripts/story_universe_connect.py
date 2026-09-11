"""Story Universe Architect connection, runtime acquisition, and API client.

Handles:
1. Three runtime acquisition modes:
   - Mode 1: Local development repository
   - Mode 2: Pre-installed runtime wheel
   - Mode 3: Automatic verified GitHub release acquisition
2. Server detection, startup, and health checking.
3. Workspace and universe validation/persistence operations.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

SKILL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_PORT = 8765
MOVABLE_PORTS = tuple(range(8765, 8771))
CACHE_DIR = Path.home() / ".story-universe-architect" / "releases"


def read_installation_meta() -> dict:
    meta_path = SKILL_DIR / "references" / "installation.json"
    if meta_path.is_file():
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "version": "1.1.0",
        "artifact": "story_universe_architect_workbench-1.1.0-py3-none-any.whl",
        "sha256": "",
    }


# --- 1. Runtime Acquisition Modes ---

def detect_mode1_local_dev() -> Optional[Path]:
    """Mode 1: Detect repository source checkout."""
    for parent in [SKILL_DIR.parents[1], SKILL_DIR.parents[2], Path.cwd()]:
        pkg = parent / "src" / "story_universe_architect"
        if pkg.is_dir() and (pkg / "server.py").is_file():
            return pkg.resolve()
    return None


def detect_mode2_preinstalled() -> bool:
    """Mode 2: Checks if story_universe_architect is installed or importable in current Python."""
    try:
        import story_universe_architect
        return True
    except ImportError:
        pass
    try:
        cmd = [sys.executable, "-c", "import story_universe_architect; print(story_universe_architect.__version__)"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=3, env=os.environ)
        return res.returncode == 0
    except Exception:
        return False


def acquire_mode3_cached_release(fixture_wheel: Optional[Path] = None) -> Path:
    """Mode 3: Automatically acquire, verify, and unpack the official release wheel."""
    meta = read_installation_meta()
    version = meta.get("version", "1.1.0")
    wheel_name = meta.get("artifact", f"story_universe_architect_workbench-{version}-py3-none-any.whl")
    expected_sha = meta.get("sha256", "").strip()

    target_dir = CACHE_DIR / version
    wheel_target = target_dir / wheel_name
    extracted_pkg = target_dir / "story_universe_architect"

    if extracted_pkg.is_dir() and (extracted_pkg / "server.py").is_file():
        return extracted_pkg

    target_dir.mkdir(parents=True, exist_ok=True)

    # 1. Acquire wheel: from fixture/dist or download
    if fixture_wheel and Path(fixture_wheel).is_file():
        shutil.copy2(fixture_wheel, wheel_target)
    elif (SKILL_DIR.parents[1] / "dist" / wheel_name).is_file():
        shutil.copy2(SKILL_DIR.parents[1] / "dist" / wheel_name, wheel_target)
    elif not wheel_target.is_file():
        repo = meta.get("repository", "https://github.com/story-universe-architect/story-universe-architect")
        tag = meta.get("release_tag", f"v{version}")
        url = f"{repo}/releases/download/{tag}/{wheel_name}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "StoryUniverseArchitect-Skill"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                wheel_target.write_bytes(resp.read())
        except Exception as ex:
            raise RuntimeError(f"Failed to download release wheel from {url}: {ex}") from ex

    # 2. Verify SHA-256 integrity
    if expected_sha:
        actual_sha = hashlib.sha256(wheel_target.read_bytes()).hexdigest()
        if actual_sha.lower() != expected_sha.lower():
            wheel_target.unlink(missing_ok=True)
            raise ValueError(
                f"Runtime integrity check failed for {wheel_name}!\n"
                f"Expected SHA-256: {expected_sha}\n"
                f"Actual SHA-256:   {actual_sha}"
            )

    # 3. Extract pure wheel contents to cache dir
    with zipfile.ZipFile(wheel_target, "r") as z:
        z.extractall(target_dir)

    if not extracted_pkg.is_dir():
        raise RuntimeError(f"Wheel extraction did not produce expected package: {extracted_pkg}")

    return extracted_pkg


def resolve_runtime_command(fixture_wheel: Optional[Path] = None) -> Tuple[str, List[str]]:
    """Determine the python invocation command for the acquired runtime."""
    # Mode 1
    dev_path = detect_mode1_local_dev()
    if dev_path:
        src_root = dev_path.parent
        return "mode1_dev", [sys.executable, "-m", "story_universe_architect.server"]

    # Mode 2
    if detect_mode2_preinstalled():
        return "mode2_installed", [sys.executable, "-m", "story_universe_architect.server"]

    # Mode 3
    cached_pkg = acquire_mode3_cached_release(fixture_wheel)
    cache_root = cached_pkg.parent
    return "mode3_acquired", [sys.executable, "-m", "story_universe_architect.server"]


# --- 2. Port & Process Management ---

def screen_port(port: int, timeout: float = 0.25) -> bool:
    s = socket.socket()
    s.settimeout(timeout)
    try:
        return s.connect_ex(("127.0.0.1", port)) == 0
    finally:
        s.close()


def probe_server(port: int, timeout: float = 1.0) -> Optional[dict]:
    url = f"http://127.0.0.1:{port}/api/health"
    try:
        req = urllib.request.Request(url, headers={"Host": f"127.0.0.1:{port}"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("status") == "ok":
                    return data
    except Exception:
        return None
    return None


def find_active_server() -> Optional[Tuple[int, dict]]:
    for p in (DEFAULT_PORT, *MOVABLE_PORTS):
        if screen_port(p):
            info = probe_server(p)
            if info:
                return p, info
    return None


def ensure_server_running(port: int = DEFAULT_PORT, fixture_wheel: Optional[Path] = None) -> Tuple[int, dict]:
    active = find_active_server()
    if active:
        return active

    mode_name, base_cmd = resolve_runtime_command(fixture_wheel)
    target_port = next((p for p in [port, *MOVABLE_PORTS] if not screen_port(p)), None)
    if target_port is None:
        raise RuntimeError(f"No free port available in range {DEFAULT_PORT}-{MOVABLE_PORTS[-1]}")

    env = os.environ.copy()
    if mode_name == "mode1_dev":
        dev_pkg = detect_mode1_local_dev()
        if dev_pkg:
            env["PYTHONPATH"] = str(dev_pkg.parent)
    elif mode_name == "mode3_acquired":
        meta = read_installation_meta()
        v = meta.get("version", "1.1.0")
        env["PYTHONPATH"] = str(CACHE_DIR / v)

    cmd = [*base_cmd, "--port", str(target_port), "--no-browser"]
    popen_kwargs = dict(
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    if os.name == "nt":
        popen_kwargs["creationflags"] = (
            subprocess.CREATE_NO_WINDOW | getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        )
    else:
        popen_kwargs["start_new_session"] = True

    proc = subprocess.Popen(cmd, **popen_kwargs)

    deadline = time.time() + 15.0
    while time.time() < deadline:
        info = probe_server(target_port)
        if info:
            return target_port, info
        time.sleep(0.25)

    try:
        proc.terminate()
    except Exception:
        pass
    raise TimeoutError(f"SUA server started on port {target_port} but failed health check within 15 seconds.")


# --- 3. Client API Operations ---

class SUAClient:
    def __init__(self, port: Optional[int] = None, fixture_wheel: Optional[Path] = None):
        if port and probe_server(port):
            self.port = port
            self.server_info = probe_server(port)
        else:
            self.port, self.server_info = ensure_server_running(port or DEFAULT_PORT, fixture_wheel)
        self.base_url = f"http://127.0.0.1:{self.port}"

    def _request(self, path: str, method: str = "GET", body: Optional[dict] = None) -> dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        headers = {
            "Host": f"127.0.0.1:{self.port}",
            "Accept": "application/json",
        }
        if data is not None:
            headers["Content-Type"] = "application/json; charset=utf-8"

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            err_raw = e.read().decode("utf-8", "replace")
            try:
                err_json = json.loads(err_raw)
                raise RuntimeError(f"SUA API error (HTTP {e.code}): {err_json.get('error', err_raw)}") from e
            except json.JSONDecodeError:
                raise RuntimeError(f"SUA API error (HTTP {e.code}): {err_raw}") from e

    def health(self) -> dict:
        return self._request("/api/health")

    def validate(self, universe: dict) -> dict:
        return self._request("/api/validate", method="POST", body={"universe": universe})

    def list_workspaces(self) -> list:
        res = self._request("/api/workspaces")
        return res.get("workspaces", [])

    def get_workspace(self, workspace_id: str) -> dict:
        return self._request(f"/api/workspaces/{workspace_id}")

    def get_universe(self, workspace_id: str) -> dict:
        return self._request(f"/api/workspaces/{workspace_id}/universe")

    def publish_universe(self, workspace_id: str, universe: dict) -> dict:
        return self._request(f"/api/workspaces/{workspace_id}/universe", method="PUT", body={"universe": universe})

    def patch_universe(self, workspace_id: str, patch_data: dict) -> dict:
        return self._request(f"/api/workspaces/{workspace_id}/universe", method="PATCH", body=patch_data)

    def export_workspace(self, workspace_id: str, fmt: str) -> Union[str, bytes]:
        url = f"{self.base_url}/api/workspaces/{workspace_id}/export/{fmt}"
        req = urllib.request.Request(url, headers={"Host": f"127.0.0.1:{self.port}"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
            try:
                return data.decode("utf-8")
            except UnicodeDecodeError:
                return data

    def workspace_url(self, workspace_id: str) -> str:
        return f"{self.base_url}/?workspace={workspace_id}"


# Aliases and verification helper
StoryUniverseClient = SUAClient
find_runtime_source = detect_mode1_local_dev
find_runtime_installed = lambda: "story_universe_architect" if detect_mode2_preinstalled() else None


def verify_sha256_bytes(data: bytes, expected_sha: str) -> bool:
    """Verify SHA-256 integrity of binary data."""
    if not expected_sha:
        return True
    actual = hashlib.sha256(data).hexdigest()
    return actual.lower() == expected_sha.lower()

