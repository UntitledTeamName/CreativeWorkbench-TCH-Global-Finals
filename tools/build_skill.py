"""Package the WorkBuddy Skill into dist/CharacterOS.zip."""
from __future__ import annotations

import os
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_SRC = ROOT / "skills" / "CharacterOS"
DIST = ROOT / "dist"

EXCLUDED_NAMES = {"__pycache__", ".DS_Store", "Thumbs.db"}
EXCLUDED_EXTS = {".pyc", ".pyo"}


def build_skill_zip(output_path: Optional[Path] = None) -> Path:
    dest = (output_path or DIST / "CharacterOS.zip").resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)

    if not (SKILL_SRC / "SKILL.md").is_file():
        raise FileNotFoundError(f"SKILL.md missing in {SKILL_SRC}")

    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for file_path in sorted(SKILL_SRC.rglob("*")):
            if not file_path.is_file():
                continue
            if any(part in EXCLUDED_NAMES for part in file_path.parts):
                continue
            if file_path.suffix in EXCLUDED_EXTS:
                continue

            rel = file_path.relative_to(SKILL_SRC)
            # Store with exact relative path (SKILL.md at zip root)
            z.write(file_path, rel.as_posix())

    # Integrity verification
    with zipfile.ZipFile(dest) as z:
        bad = z.testzip()
        if bad:
            raise RuntimeError(f"Skill ZIP failed CRC check: {bad}")

    return dest


if __name__ == "__main__":
    out = build_skill_zip()
    print(f"Built Skill ZIP: {out} ({out.stat().st_size} bytes)")
