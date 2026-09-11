"""Deterministic PEP 427 pure-Python wheel packager for CharacterOS."""
from __future__ import annotations

import base64
import hashlib
import os
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_PKG = ROOT / "src" / "story_universe_architect"
DIST = ROOT / "dist"

DISTRIBUTION_NAME = "story_universe_architect_workbench"


def get_version() -> str:
    init_file = SRC_PKG / "__init__.py"
    for line in init_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("__version__"):
            return line.split("=")[1].strip().strip("\"'")
    return "1.1.0"


def make_record_entry(archive_name: str, data: bytes) -> str:
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode("ascii").rstrip("=")
    return f"{archive_name},sha256={digest},{len(data)}"


def build_wheel(output_dir: Path | None = None) -> Path:
    version = get_version()
    out_dir = (output_dir or DIST).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    wheel_filename = f"{DISTRIBUTION_NAME}-{version}-py3-none-any.whl"
    wheel_path = out_dir / wheel_filename

    dist_info = f"{DISTRIBUTION_NAME}-{version}.dist-info"
    record_entries = []

    readme_text = ""
    readme_path = ROOT / "README.md"
    if readme_path.is_file():
        readme_text = readme_path.read_text(encoding="utf-8")

    metadata_content = (
        "Metadata-Version: 2.1\n"
        f"Name: {DISTRIBUTION_NAME}\n"
        f"Version: {version}\n"
        "Summary: CharacterOS - Localhost-first narrative workbench and universe compiler.\n"
        "Author: THRESHOLD team\n"
        "Author-email: threshold@story-universe.local\n"
        "Requires-Python: >=3.10\n"
        "Project-URL: Homepage, https://github.com/UntitledTeamName/CharacterOS\n"
        "Project-URL: Repository, https://github.com/UntitledTeamName/CharacterOS\n"
        "Description-Content-Type: text/markdown\n\n"
        + readme_text
    ).encode("utf-8")

    wheel_meta_content = (
        "Wheel-Version: 1.0\n"
        "Generator: characteros-packager\n"
        "Root-Is-Purelib: true\n"
        "Tag: py3-none-any\n"
    ).encode("utf-8")

    entry_points_content = (
        "[console_scripts]\n"
        "characteros = story_universe_architect.cli:main\n"
        "sua = story_universe_architect.cli:main\n"
    ).encode("utf-8")

    with zipfile.ZipFile(wheel_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        # 1. Package Python modules and web assets
        for p in sorted(SRC_PKG.rglob("*")):
            if not p.is_file():
                continue
            if "__pycache__" in p.parts or p.suffix in (".pyc", ".pyo"):
                continue

            rel = p.relative_to(SRC_PKG.parent)
            data = p.read_bytes()
            archive_name = rel.as_posix()
            z.writestr(archive_name, data)
            record_entries.append(make_record_entry(archive_name, data))

        # 2. Add dist-info files
        for arc_name, content in [
            (f"{dist_info}/METADATA", metadata_content),
            (f"{dist_info}/WHEEL", wheel_meta_content),
            (f"{dist_info}/entry_points.txt", entry_points_content),
        ]:
            z.writestr(arc_name, content)
            record_entries.append(make_record_entry(arc_name, content))

        # 3. Add RECORD
        record_name = f"{dist_info}/RECORD"
        record_entries.append(f"{record_name},,")
        record_content = "\n".join(record_entries) + "\n"
        z.writestr(record_name, record_content.encode("utf-8"))

    # Test zip
    with zipfile.ZipFile(wheel_path) as z:
        bad = z.testzip()
        if bad:
            raise RuntimeError(f"Wheel ZIP failed CRC: {bad}")

    return wheel_path


if __name__ == "__main__":
    out = build_wheel()
    print(f"Built wheel: {out} ({out.stat().st_size} bytes)")
