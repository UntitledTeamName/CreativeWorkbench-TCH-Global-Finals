"""Synchronize release metadata, hashes, and installation references."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def update_manifests(
    wheel_path: Optional[Path] = None,
    skill_zip_path: Optional[Path] = None,
    skill_path: Optional[Path] = None
):
    actual_skill = skill_zip_path or skill_path
    if wheel_path is None:
        wheel_candidates = list((ROOT / "dist").glob("story_universe_architect_workbench-*.whl"))
        if wheel_candidates:
            wheel_path = wheel_candidates[0]

    wheel_sha = file_sha256(wheel_path) if wheel_path and wheel_path.is_file() else ""
    skill_sha = file_sha256(actual_skill) if actual_skill and actual_skill.is_file() else ""

    # 1. Update release.json
    rel_path = ROOT / "release.json"
    if rel_path.is_file():
        rel = json.loads(rel_path.read_text(encoding="utf-8"))
        if wheel_sha and wheel_path:
            rel["runtime_artifact"] = wheel_path.name
            rel["runtime_sha256"] = wheel_sha
        if skill_sha and actual_skill:
            rel["skill_artifact"] = actual_skill.name
            rel["skill_sha256"] = skill_sha
        rel_path.write_text(json.dumps(rel, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # 2. Update runtime-manifest.json
    run_path = ROOT / "runtime-manifest.json"
    if run_path.is_file():
        run = json.loads(run_path.read_text(encoding="utf-8"))
        if wheel_sha and wheel_path:
            run["wheel"] = f"dist/{wheel_path.name}"
            run["sha256"]["wheel"] = wheel_sha
        if skill_sha and actual_skill:
            run["skill_zip"] = f"dist/{actual_skill.name}"
            run["sha256"]["skill"] = skill_sha
        run_path.write_text(json.dumps(run, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # 3. Update Skill installation.json
    inst_path = ROOT / "skills" / "CharacterOS" / "references" / "installation.json"
    if inst_path.is_file():
        inst = json.loads(inst_path.read_text(encoding="utf-8"))
        if wheel_sha and wheel_path:
            inst["artifact"] = wheel_path.name
            inst["sha256"] = wheel_sha
        inst_path.write_text(json.dumps(inst, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

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
    from pathlib import Path
    import sys
    dist = ROOT / "dist"
    wheels = list(dist.glob("*.whl"))
    skills = list(dist.glob("*.zip"))
    if not wheels:
        print("No wheel found in dist/")
        sys.exit(1)
    w_sha, s_sha = update_manifests(wheels[0], skills[0] if skills else None)
    print(f"Updated manifests: wheel SHA256={w_sha[:16]}..., skill SHA256={s_sha[:16]}...")
