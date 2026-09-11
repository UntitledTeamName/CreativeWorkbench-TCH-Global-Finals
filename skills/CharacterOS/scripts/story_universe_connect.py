"""CharacterOS Git-based immutable runtime acquisition, integrity verification, and API client.

Architecture:
1. Git-based shallow acquisition into a clean staging directory.
2. Cryptographic SHA-256 verification of all declared runtime files against runtime-manifest.json.
3. Atomic installation into an immutable release directory under ~/.characteros-tools/releases/<key>/.
4. Detached loopback-only server hosting (127.0.0.1).
5. Safe caching and remote update detection via git ls-remote.
6. Explicit development mode (--dev / CHARACTEROS_DEV=1) strictly separated from production flow.
"""
from __future__ import annotations

import datetime
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
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

SKILL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_PORT = 8765
MOVABLE_PORTS = tuple(range(8765, 8771))
DEFAULT_REPO_URL = "https://github.com/mrc2rules/CharacterOS.git"
DEFAULT_REF = "main"


def get_tools_base_dir() -> Path:
    """Base directory for CharacterOS immutable releases and temporary staging."""
    override = os.environ.get("CHARACTEROS_TOOLS_DIR")
    if override and override.strip():
        return Path(override.strip()).expanduser().resolve()
    return Path.home() / ".characteros-tools"


def get_releases_dir() -> Path:
    return get_tools_base_dir() / "releases"


def get_staging_dir() -> Path:
    return get_tools_base_dir() / "staging"


def read_installation_config(custom_config: Optional[Union[dict, Path, str]] = None) -> dict:
    """Read configuration containing repository_url, ref, and expected_commit."""
    if isinstance(custom_config, dict):
        cfg = dict(custom_config)
    elif custom_config and Path(custom_config).is_file():
        cfg = json.loads(Path(custom_config).read_text(encoding="utf-8"))
    else:
        meta_path = SKILL_DIR / "references" / "installation.json"
        if meta_path.is_file():
            try:
                cfg = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                cfg = {}
        else:
            cfg = {}

    repo_url = cfg.get("repository_url") or cfg.get("repository") or DEFAULT_REPO_URL
    ref = cfg.get("ref") or "main"
    expected_commit = cfg.get("expected_commit")  # None or 40-char SHA string

    return {
        "repository_url": repo_url.strip(),
        "ref": ref.strip(),
        "expected_commit": expected_commit.strip() if isinstance(expected_commit, str) and expected_commit.strip() else None,
    }


def compute_release_key(repository_url: str, ref: str, resolved_commit: str) -> str:
    """Compute deterministic, collision-resistant release key from runtime identity."""
    identity = [repository_url.lower().rstrip("/"), ref, resolved_commit]
    data = json.dumps(identity, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()[:20]


def find_runtime_source() -> Optional[Path]:
    """Find local development source tree package if present."""
    for parent in [SKILL_DIR.parents[1], SKILL_DIR.parents[2], Path.cwd()]:
        pkg = parent / "src" / "story_universe_architect"
        if pkg.is_dir() and (pkg / "server.py").is_file():
            return pkg
    return None


def find_runtime_installed() -> Optional[str]:
    """Detect if story_universe_architect is importable in current python environment."""
    try:
        import story_universe_architect
        return "story_universe_architect"
    except ImportError:
        return None


def verify_sha256_bytes(content: bytes, expected_hash: str) -> bool:
    """Verify cryptographic SHA-256 hash of bytes."""
    actual = hashlib.sha256(content).hexdigest()
    return actual.lower() == expected_hash.lower()


def resolve_remote_commit(
    repository_url: str,
    ref: str,
    expected_commit: Optional[str] = None,
    timeout: float = 10.0
) -> str:
    """Resolve the target commit for acquisition.
    
    1. If expected_commit is pinned, use it directly.
    2. Otherwise, query remote ref via git ls-remote.
    3. If remote is unreachable, safely fall back to the newest matching local release.
    """
    if expected_commit:
        return expected_commit

    # Query remote ref
    cmd = ["git", "ls-remote", repository_url, ref]
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        )
        if res.returncode == 0 and res.stdout.strip():
            for line in res.stdout.splitlines():
                parts = line.strip().split()
                if parts:
                    sha = parts[0]
                    if len(sha) >= 7 and all(c in "0123456789abcdefABCDEF" for c in sha):
                        return sha
    except Exception:
        pass

    # Network failure or unreachable remote: check for existing matching verified release
    releases_dir = get_releases_dir()
    if releases_dir.is_dir():
        candidates = []
        for d in releases_dir.iterdir():
            receipt_path = d / "receipt.json"
            if d.is_dir() and receipt_path.is_file():
                try:
                    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                    if receipt.get("repository_url", "").lower() == repository_url.lower() and receipt.get("configured_ref") == ref:
                        commit = receipt.get("resolved_commit")
                        if commit and receipt.get("verification_status") == "verified":
                            candidates.append((receipt_path.stat().st_mtime, commit))
                except Exception:
                    continue
        if candidates:
            candidates.sort(reverse=True)
            return candidates[0][1]

    raise RuntimeError(
        f"Unable to resolve remote commit for ref '{ref}' from {repository_url} "
        "and no existing verified local release was found."
    )


def verify_manifest(staging_dir: Path) -> dict:
    """Verify cryptographic SHA-256 integrity of all declared files in runtime-manifest.json."""
    manifest_path = staging_dir / "runtime-manifest.json"
    if not manifest_path.is_file():
        raise ValueError("Runtime integrity error: 'runtime-manifest.json' not found in acquired repository.")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as ex:
        raise ValueError(f"Runtime integrity error: Failed to parse runtime-manifest.json: {ex}") from ex

    declared_files = manifest.get("files")
    if not isinstance(declared_files, dict) or not declared_files:
        raise ValueError("Runtime integrity error: runtime-manifest.json contains no 'files' dictionary.")

    for rel_path, expected_hash in declared_files.items():
        target_file = staging_dir / rel_path
        if not target_file.is_file():
            raise ValueError(f"Runtime integrity check failed: Missing required file '{rel_path}'.")

        with target_file.open("rb") as f:
            raw_content = f.read()
        actual_hash = hashlib.sha256(raw_content).hexdigest()

        if actual_hash.lower() != expected_hash.lower():
            # Tolerate OS line-ending conversion (CRLF vs LF) across platforms
            normalized_hash = hashlib.sha256(raw_content.replace(b"\r\n", b"\n")).hexdigest()
            if normalized_hash.lower() == expected_hash.lower():
                actual_hash = expected_hash
            else:
                raise ValueError(
                    f"Runtime integrity check failed for '{rel_path}' (Hash mismatch)!\n"
                    f"Expected SHA-256: {expected_hash}\n"
                    f"Actual SHA-256:   {actual_hash}"
                )

    return manifest


def acquire_git_runtime(
    repository_url: str,
    ref: str,
    target_commit: str,
    release_key: str,
    timeout: float = 60.0
) -> Path:
    """Shallow git fetch into a temporary staging directory, verify manifest, and atomically install."""
    releases_dir = get_releases_dir()
    staging_dir = get_staging_dir()
    release_path = releases_dir / release_key

    # If already installed and verified, return
    if release_path.is_dir() and (release_path / "receipt.json").is_file():
        try:
            rc = json.loads((release_path / "receipt.json").read_text(encoding="utf-8"))
            if rc.get("verification_status") == "verified":
                return release_path
        except Exception:
            pass

    releases_dir.mkdir(parents=True, exist_ok=True)
    staging_dir.mkdir(parents=True, exist_ok=True)

    stage_id = f"stage-{uuid.uuid4().hex[:12]}"
    current_stage = staging_dir / stage_id
    current_stage.mkdir(parents=True, exist_ok=True)

    try:
        # 1. Initialize git in staging with core.autocrlf=false
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        git_cmd = ["git", "-c", "core.autocrlf=false"]
        subprocess.run([*git_cmd, "init", "--quiet", str(current_stage)], check=True, capture_output=True, env=env)
        subprocess.run([*git_cmd, "-C", str(current_stage), "config", "core.autocrlf", "false"], check=True, capture_output=True, env=env)
        subprocess.run([*git_cmd, "-C", str(current_stage), "remote", "add", "origin", repository_url], check=True, capture_output=True, env=env)

        # 2. Shallow fetch ref or commit
        fetch_cmd = [*git_cmd, "-C", str(current_stage), "fetch", "--depth", "1", "origin", ref]
        res_fetch = subprocess.run(fetch_cmd, capture_output=True, text=True, timeout=timeout, env=env)
        if res_fetch.returncode != 0:
            # Fallback: try fetching target commit directly
            res_fetch2 = subprocess.run([*git_cmd, "-C", str(current_stage), "fetch", "--depth", "1", "origin", target_commit], capture_output=True, text=True, timeout=timeout, env=env)
            if res_fetch2.returncode != 0:
                raise RuntimeError(f"Git fetch failed: {res_fetch.stderr or res_fetch2.stderr}")

        subprocess.run([*git_cmd, "-C", str(current_stage), "checkout", "--detach", "--quiet", "FETCH_HEAD"], check=True, capture_output=True, env=env)

        # 3. Cryptographically verify runtime manifest
        manifest = verify_manifest(current_stage)

        # 4. Write installation receipt
        receipt = {
            "repository_url": repository_url,
            "configured_ref": ref,
            "resolved_commit": target_commit,
            "release_key": release_key,
            "verification_status": "verified",
            "installed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "manifest_version": manifest.get("manifest_version", "2.0"),
            "files_count": len(manifest.get("files", {})),
        }
        (current_stage / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")

        # 5. Atomic installation
        if release_path.exists():
            shutil.rmtree(release_path, ignore_errors=True)

        try:
            os.replace(str(current_stage), str(release_path))
        except OSError:
            shutil.move(str(current_stage), str(release_path))

        return release_path

    except Exception:
        # Clean up staging directory on any error
        if current_stage.exists():
            shutil.rmtree(current_stage, ignore_errors=True)
        raise


def acquire_runtime(
    is_dev: bool = False,
    force_refresh: bool = False,
    custom_config: Optional[Union[dict, Path, str]] = None,
) -> Path:
    """Acquire or verify CharacterOS runtime.
    
    If is_dev is True (or CHARACTEROS_DEV=1), uses the explicit local development tree.
    Otherwise, uses the Git-based immutable release distribution model.
    """
    if is_dev or os.environ.get("CHARACTEROS_DEV") == "1":
        for parent in [SKILL_DIR.parents[1], SKILL_DIR.parents[2], Path.cwd()]:
            pkg = parent / "src" / "story_universe_architect"
            if pkg.is_dir() and (pkg / "server.py").is_file():
                return parent
        raise RuntimeError("Explicit development mode (--dev) requested, but local source checkout was not found.")

    config = read_installation_config(custom_config)
    repo_url = config["repository_url"]
    ref = config["ref"]
    expected_commit = config["expected_commit"]

    resolved_commit = resolve_remote_commit(repo_url, ref, expected_commit)
    release_key = compute_release_key(repo_url, ref, resolved_commit)

    release_path = get_releases_dir() / release_key
    if not force_refresh and release_path.is_dir() and (release_path / "receipt.json").is_file():
        try:
            rc = json.loads((release_path / "receipt.json").read_text(encoding="utf-8"))
            if rc.get("verification_status") == "verified":
                return release_path
        except Exception:
            pass

    return acquire_git_runtime(repo_url, ref, resolved_commit, release_key)


# --- Port & Process Management ---

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


def ensure_server_running(
    port: int = DEFAULT_PORT,
    is_dev: bool = False,
    force_refresh: bool = False,
    custom_config: Optional[Union[dict, Path, str]] = None,
    data_dir: Optional[Union[Path, str]] = None,
) -> Tuple[int, dict]:
    """Ensure CharacterOS server is running against the verified acquired runtime."""
    active = find_active_server()
    if active:
        return active

    runtime_root = acquire_runtime(is_dev=is_dev, force_refresh=force_refresh, custom_config=custom_config)
    src_dir = runtime_root / "src"
    if not (src_dir / "story_universe_architect" / "server.py").is_file():
        raise RuntimeError(f"Verified runtime does not contain server.py: {src_dir}")

    target_port = next((p for p in [port, *MOVABLE_PORTS] if not screen_port(p)), None)
    if target_port is None:
        raise RuntimeError(f"No free loopback port available in range {DEFAULT_PORT}-{MOVABLE_PORTS[-1]}")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(src_dir)
    env["PYTHONUTF8"] = "1"

    cmd = [sys.executable, "-m", "story_universe_architect.server", "--port", str(target_port), "--no-browser"]
    if data_dir:
        cmd.extend(["--data-dir", str(data_dir)])

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
    raise TimeoutError(f"CharacterOS server started on port {target_port} but failed health check within 15 seconds.")


# --- Client API Operations ---

class CharacterOSClient:
    def __init__(
        self,
        port: Optional[int] = None,
        is_dev: bool = False,
        force_refresh: bool = False,
        custom_config: Optional[Union[dict, Path, str]] = None,
        data_dir: Optional[Union[Path, str]] = None,
    ):
        if port and probe_server(port):
            self.port = port
            self.server_info = probe_server(port)
        else:
            self.port, self.server_info = ensure_server_running(
                port or DEFAULT_PORT,
                is_dev=is_dev,
                force_refresh=force_refresh,
                custom_config=custom_config,
                data_dir=data_dir,
            )
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
                raise RuntimeError(f"CharacterOS API error (HTTP {e.code}): {err_json.get('error', err_raw)}") from e
            except json.JSONDecodeError:
                raise RuntimeError(f"CharacterOS API error (HTTP {e.code}): {err_raw}") from e

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


# Backward compatibility aliases
SUAClient = CharacterOSClient
StoryUniverseClient = CharacterOSClient
