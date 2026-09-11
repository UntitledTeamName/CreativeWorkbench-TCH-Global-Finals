"""Synchronize release metadata, runtime file hashes, and installation references."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPO_URL = "https://github.com/mrc2rules/CharacterOS.git"


def file_sha256(path: Path) -> str:
    raw = path.read_bytes()
    # Normalize line endings to canonical LF for text files so hashes are OS-independent
    if path.suffix in (".py", ".json", ".html", ".css", ".js", ".md", ".txt"):
        raw = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def compute_runtime_files() -> dict[str, str]:
    """Compute deterministic SHA-256 for all runtime source files under src/story_universe_architect."""
    src_dir = ROOT / "src" / "story_universe_architect"
    file_hashes: dict[str, str] = {}
    for p in sorted(src_dir.rglob("*")):
        if not p.is_file():
            continue
        if "__pycache__" in p.parts or p.suffix in (".pyc", ".pyo"):
            continue
        rel = p.relative_to(ROOT).as_posix()
        file_hashes[rel] = file_sha256(p)
    return file_hashes


def update_manifests(
    wheel_path: Optional[Path] = None,
    skill_zip_path: Optional[Path] = None,
    skill_path: Optional[Path] = None,
) -> Tuple[str, str]:
    actual_skill = skill_zip_path or skill_path
    if wheel_path is None:
        wheel_candidates = list((ROOT / "dist").glob("story_universe_architect_workbench-*.whl"))
        if wheel_candidates:
            wheel_path = wheel_candidates[0]

    wheel_sha = file_sha256(wheel_path) if wheel_path and wheel_path.is_file() else ""
    skill_sha = file_sha256(actual_skill) if actual_skill and actual_skill.is_file() else ""
    runtime_files = compute_runtime_files()

    # 1. Update release.json
    rel_path = ROOT / "release.json"
    if rel_path.is_file():
        rel = json.loads(rel_path.read_text(encoding="utf-8"))
        rel["repository"] = DEFAULT_REPO_URL
        if wheel_sha and wheel_path:
            rel["runtime_artifact"] = wheel_path.name
            rel["runtime_sha256"] = wheel_sha
        if skill_sha and actual_skill:
            rel["skill_artifact"] = actual_skill.name
            rel["skill_sha256"] = skill_sha
        rel_path.write_text(json.dumps(rel, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # 2. Update runtime-manifest.json
    run_path = ROOT / "runtime-manifest.json"
    run_data: dict = {}
    if run_path.is_file():
        try:
            run_data = json.loads(run_path.read_text(encoding="utf-8"))
        except Exception:
            run_data = {}

    run_data.update({
        "application": "CharacterOS",
        "distribution": "story_universe_architect_workbench",
        "version": "1.1.0",
        "protocol": "1.0",
        "schema": "1.0",
        "manifest_version": "2.0",
        "repository": DEFAULT_REPO_URL,
        "entrypoint": "story_universe_architect.cli:main",
        "files": runtime_files,
    })
    if "sha256" not in run_data:
        run_data["sha256"] = {}
    if wheel_sha and wheel_path:
        run_data["wheel"] = f"dist/{wheel_path.name}"
        run_data["sha256"]["wheel"] = wheel_sha
    if skill_sha and actual_skill:
        run_data["skill_zip"] = f"dist/{actual_skill.name}"
        run_data["sha256"]["skill"] = skill_sha
    run_data["compatibility"] = {
        "python": ">=3.10",
        "workbuddy_skill": "CharacterOS",
    }
    run_path.write_text(json.dumps(run_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # 3. Update Skill installation.json with Git acquisition defaults
    inst_path = ROOT / "skills" / "CharacterOS" / "references" / "installation.json"
    inst_data = {
        "repository_url": DEFAULT_REPO_URL,
        "ref": "main",
        "expected_commit": None,
        "name": "CharacterOS",
        "version": "1.1.0",
        "min_python": "3.10",
    }
    if wheel_sha and wheel_path:
        inst_data["artifact"] = wheel_path.name
        inst_data["sha256"] = wheel_sha
    inst_path.write_text(json.dumps(inst_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # 4. Update dist/MANIFEST.sha256
    manifest_lines = []
    if wheel_sha and wheel_path:
        manifest_lines.append(f"{wheel_sha}  {wheel_path.name}")
    if skill_sha and actual_skill:
        manifest_lines.append(f"{skill_sha}  {actual_skill.name}")
    if manifest_lines:
        manifest_text = "\n".join(manifest_lines) + "\n"
        dist_manifest = ROOT / "dist" / "MANIFEST.sha256"
        dist_manifest.write_text(manifest_text, encoding="utf-8")

    return wheel_sha, skill_sha


if __name__ == "__main__":
    import sys
    dist = ROOT / "dist"
    wheels = list(dist.glob("*.whl"))
    skills = list(dist.glob("*.zip"))
    w_sha, s_sha = update_manifests(
        wheels[0] if wheels else None,
        skills[0] if skills else None
    )
    print(f"Updated manifests: wheel SHA256={w_sha[:16] if w_sha else 'none'}, skill SHA256={s_sha[:16] if s_sha else 'none'}")
