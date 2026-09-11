"""Story Universe Architect workspace and persistent state management.

Isolates user data safely in ~/.story-universe-architect/workspaces (or configurable dir).
Never mutates installed package directories.
Provides atomic persistence, listing, retrieval, and structured patching.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from . import model

DEFAULT_DATA_DIR = Path.home() / ".story-universe-architect" / "workspaces"


def sanitize_workspace_id(wid: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "-", wid.strip()).strip("-")
    if not cleaned:
        cleaned = "default-universe"
    return cleaned[:80]


class WorkspaceStore:
    def __init__(self, data_dir: Optional[Union[str, Path]] = None):
        if data_dir:
            self.dir = Path(data_dir).expanduser().resolve()
        elif "SUA_DATA_DIR" in os.environ and os.environ["SUA_DATA_DIR"].strip():
            self.dir = Path(os.environ["SUA_DATA_DIR"].strip()).expanduser().resolve()
        else:
            self.dir = DEFAULT_DATA_DIR
        self.dir.mkdir(parents=True, exist_ok=True)

    def _file_for(self, workspace_id: str) -> Path:
        wid = sanitize_workspace_id(workspace_id)
        return self.dir / f"{wid}.universe.json"

    def list_workspaces(self) -> List[Dict[str, Any]]:
        results = []
        for p in self.dir.glob("*.universe.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                stat = p.stat()
                results.append({
                    "id": p.name[:-len(".universe.json")],
                    "title": data.get("title", p.stem),
                    "concept": data.get("concept", ""),
                    "format": data.get("format", ""),
                    "genre": data.get("genre", ""),
                    "tone": data.get("tone", ""),
                    "characters_count": len(data.get("characters", [])),
                    "relationships_count": len(data.get("relationships", [])),
                    "suggestions_count": len(data.get("suggestions", [])),
                    "revision": data.get("revision", 1),
                    "updated_at": datetime.datetime.fromtimestamp(stat.st_mtime, tz=datetime.timezone.utc).isoformat(),
                })
            except (OSError, json.JSONDecodeError):
                continue
        results.sort(key=lambda x: x["updated_at"], reverse=True)
        return results

    def get_workspace(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        p = self._file_for(workspace_id)
        if not p.is_file():
            return None
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            stat = p.stat()
            wid = sanitize_workspace_id(workspace_id)
            return {
                "id": wid,
                "workspace_id": wid,
                "title": data.get("title", wid),
                "path": str(p),
                "updated_at": datetime.datetime.fromtimestamp(stat.st_mtime, tz=datetime.timezone.utc).isoformat(),
                "universe": data,
            }
        except (OSError, json.JSONDecodeError):
            return None

    def get_universe(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        ws = self.get_workspace(workspace_id)
        return ws["universe"] if ws else None

    def save_universe(self, workspace_id: str, universe: dict) -> Dict[str, Any]:
        """Validate and atomically save universe state."""
        wid = sanitize_workspace_id(workspace_id)
        model.require_valid(universe)
        target = self._file_for(wid)

        # Atomic write: write to temp file in same dir, then replace
        fd, tmp_path = tempfile.mkstemp(prefix=f"{wid}-", suffix=".tmp", dir=str(self.dir))
        try:
            with open(fd, "w", encoding="utf-8") as f:
                json.dump(universe, f, ensure_ascii=False, indent=2)
            shutil.move(tmp_path, target)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

        return self.get_workspace(wid)

    save_workspace = save_universe

    def patch_universe(self, workspace_id: str, patch_data: dict) -> Dict[str, Any]:
        """Apply targeted semantic updates to an existing universe."""
        u = self.get_universe(workspace_id)
        if not u:
            raise FileNotFoundError(f"Workspace '{workspace_id}' not found.")

        action = patch_data.get("action", "")

        if action == "accept_suggestion":
            sid = patch_data.get("suggestion_id")
            if not sid:
                raise ValueError("Missing 'suggestion_id'")
            u = model.accept_suggestion(u, sid)

        elif action == "reject_suggestion":
            sid = patch_data.get("suggestion_id")
            if not sid:
                raise ValueError("Missing 'suggestion_id'")
            u = model.reject_suggestion(u, sid)

        elif action == "rename_character":
            cid = patch_data.get("character_id")
            name = patch_data.get("name", "")
            if not cid or not name:
                raise ValueError("Requires 'character_id' and 'name'")
            u = model.rename_character(u, cid, name)

        elif action == "update_character":
            char_update = patch_data.get("character", {})
            cid = char_update.get("id")
            if not cid:
                raise ValueError("Missing character 'id'")
            char = next((c for c in u.get("characters", []) if c["id"] == cid), None)
            if not char:
                raise ValueError(f"Character '{cid}' not found.")
            for field, val in char_update.items():
                if field != "id":
                    char[field] = val
            u["revision"] = u.get("revision", 1) + 1
            model.require_valid(u)

        elif action == "add_character":
            char = patch_data.get("character", {})
            if not char or not char.get("id"):
                raise ValueError("Missing character data or id")
            if any(c["id"] == char["id"] for c in u.get("characters", [])):
                raise ValueError(f"Character '{char['id']}' already exists.")
            u.setdefault("characters", []).append(char)
            u["revision"] = u.get("revision", 1) + 1
            model.require_valid(u)

        elif action == "update_relationship":
            rel_update = patch_data.get("relationship", {})
            rid = rel_update.get("id")
            if not rid:
                raise ValueError("Missing relationship 'id'")
            rel = next((r for r in u.get("relationships", []) if r["id"] == rid), None)
            if not rel:
                raise ValueError(f"Relationship '{rid}' not found.")
            for field, val in rel_update.items():
                if field not in ("id", "source", "target"):
                    rel[field] = val
            u["revision"] = u.get("revision", 1) + 1
            model.require_valid(u)

        elif action == "add_relationship":
            rel = patch_data.get("relationship", {})
            if not rel or not rel.get("id"):
                raise ValueError("Missing relationship data or id")
            if any(r["id"] == rel["id"] for r in u.get("relationships", [])):
                raise ValueError(f"Relationship '{rel['id']}' already exists.")
            u.setdefault("relationships", []).append(rel)
            u["revision"] = u.get("revision", 1) + 1
            model.require_valid(u)

        elif action == "update_story":
            fields = patch_data.get("fields", {})
            for k, v in fields.items():
                if k in ("title", "concept", "format", "genre", "tone", "setting", "thematic_thesis"):
                    u[k] = v
                elif k == "visual" and isinstance(v, dict):
                    u["visual"].update(v)
            u["revision"] = u.get("revision", 1) + 1
            model.require_valid(u)

        elif "universe" in patch_data:
            # Full replacement candidate
            u = patch_data["universe"]
            model.require_valid(u)

        else:
            # Direct top-level fields support
            applied = False
            for k in ("title", "concept", "format", "genre", "tone", "setting", "thematic_thesis"):
                if k in patch_data:
                    u[k] = patch_data[k]
                    applied = True
            if "visual" in patch_data and isinstance(patch_data["visual"], dict):
                u.setdefault("visual", {}).update(patch_data["visual"])
                applied = True
            if "characters" in patch_data and isinstance(patch_data["characters"], list):
                for ch in patch_data["characters"]:
                    existing = next((c for c in u.get("characters", []) if c["id"] == ch.get("id")), None)
                    if existing:
                        existing.update(ch)
                    else:
                        u.setdefault("characters", []).append(ch)
                applied = True
            if "relationships" in patch_data and isinstance(patch_data["relationships"], list):
                for rl in patch_data["relationships"]:
                    existing = next((r for r in u.get("relationships", []) if r["id"] == rl.get("id")), None)
                    if existing:
                        existing.update(rl)
                    else:
                        u.setdefault("relationships", []).append(rl)
                applied = True

            if not applied:
                raise ValueError(f"Unknown or empty patch: '{patch_data}'")
            u["revision"] = u.get("revision", 1) + 1
            model.require_valid(u)

        self.save_universe(workspace_id, u)
        return self.get_universe(workspace_id)

    patch_workspace = patch_universe

    def delete_workspace(self, workspace_id: str) -> bool:
        p = self._file_for(workspace_id)
        if p.is_file():
            p.unlink()
            return True
        return False

    def export_workspace(self, workspace_id: str, fmt: str, portable_html: Optional[str] = None) -> Union[str, bytes]:
        u = self.get_universe(workspace_id)
        if not u:
            raise FileNotFoundError(f"Workspace '{workspace_id}' not found.")

        fmt_lower = fmt.lower().strip()
        if fmt_lower == "json":
            return json.dumps(u, indent=2, ensure_ascii=False)
        elif fmt_lower in ("markdown", "bible", "md"):
            return model.compile_bible(u)
        elif fmt_lower == "prompts":
            return model.compile_prompt_kit_markdown(u)
        elif fmt_lower == "seeds":
            return json.dumps(model.compile_seeds(u), indent=2, ensure_ascii=False)
        elif fmt_lower == "svg":
            return model.compile_graph_svg(u)
        elif fmt_lower == "zip":
            return model.package_zip(u, portable_html=portable_html)
        else:
            raise ValueError(f"Unsupported export format: '{fmt}'")
