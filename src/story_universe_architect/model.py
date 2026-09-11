"""CharacterOS domain and model layer.

Deterministic validation, schema enforcement, artifact compilation, and stable serialization.
Standard library only; zero external runtime dependencies.
"""
from __future__ import annotations

import copy
import io
import json
import re
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parents[1]

MAX_JSON = 2_000_000


def _locate_resource(filename: str) -> Path:
    candidates = [
        PACKAGE_ROOT / "schemas" / filename,
        REPO_ROOT / "schemas" / filename,
        REPO_ROOT / "data" / filename,
        REPO_ROOT / "schema" / filename,
    ]
    for cand in candidates:
        if cand.is_file():
            return cand
    raise FileNotFoundError(f"Could not locate required resource: {filename}")


def load_schema() -> dict:
    return json.loads(_locate_resource("universe.schema.json").read_text(encoding="utf-8"))


def load_archetypes() -> list:
    return json.loads(_locate_resource("archetypes.json").read_text(encoding="utf-8"))


def load_themes() -> list:
    return json.loads(_locate_resource("themes.json").read_text(encoding="utf-8"))


SCHEMA = load_schema()
ARCHETYPES = load_archetypes()
THEMES = load_themes()


def load_json(path: Union[str, Path]) -> dict:
    p = Path(path)
    with p.open("rb") as f:
        raw = f.read(MAX_JSON + 1)
    if len(raw) > MAX_JSON:
        raise ValueError("JSON exceeds the local 2 MB safety limit.")
    return json.loads(raw.decode("utf-8-sig"))


def shape(value: Any, subschema: dict, path: str = "$", errors: Optional[List[str]] = None) -> List[str]:
    if errors is None:
        errors = []
    if "const" in subschema and value != subschema["const"]:
        errors.append(f"{path}: unexpected constant")
    if "enum" in subschema and value not in subschema["enum"]:
        errors.append(f"{path}: value is not allowed")

    typ = subschema.get("type")
    if typ == "object":
        if not isinstance(value, dict):
            errors.append(f"{path}: expected object")
            return errors
        for k in subschema.get("required", []):
            if k not in value:
                errors.append(f"{path}.{k}: required")
        for k, v in value.items():
            if k in subschema.get("properties", {}):
                shape(v, subschema["properties"][k], f"{path}.{k}", errors)
            elif subschema.get("additionalProperties") is False:
                errors.append(f"{path}.{k}: unexpected field")
    elif typ == "array":
        if not isinstance(value, list):
            errors.append(f"{path}: expected array")
            return errors
        if not (subschema.get("minItems", 0) <= len(value) <= subschema.get("maxItems", 100000)):
            errors.append(f"{path}: array length outside permitted range")
        for i, v in enumerate(value[:100]):
            shape(v, subschema["items"], f"{path}[{i}]", errors)
    elif typ == "string":
        if not isinstance(value, str):
            errors.append(f"{path}: expected text")
            return errors
        min_l = subschema.get("minLength", 0)
        max_l = subschema.get("maxLength", 100000)
        if not (min_l <= len(value) <= max_l) or (min_l > 0 and not value.strip()):
            errors.append(f"{path}: text length outside permitted range")
        if subschema.get("pattern") and not re.search(subschema["pattern"], value):
            errors.append(f"{path}: invalid identifier")
    elif typ == "integer":
        if type(value) is not int or not (subschema.get("minimum", float("-inf")) <= value <= subschema.get("maximum", float("inf"))):
            errors.append(f"{path}: expected bounded integer")
    return errors


def validate(u: dict) -> dict:
    errors = shape(u, SCHEMA)
    if errors:
        return {"ok": False, "errors": errors[:40], "warnings": []}

    ids = set()
    eids = set()
    pairs = set()
    sids = set()
    pids = set()
    proposed_edges = set()
    warnings = []
    aids = {a["id"] for a in ARCHETYPES}

    for c in u.get("characters", []):
        if c["id"] in ids:
            errors.append(f"Duplicate character id: {c['id']}")
        ids.add(c["id"])
        if c.get("archetype_id") not in aids:
            errors.append(f"Unknown archetype: {c.get('archetype_id')}")

    def check_edge(e, allowed):
        if e["source"] not in allowed or e["target"] not in allowed:
            errors.append(f"Unknown endpoint: {e['id']}")
        if e["source"] == e["target"]:
            errors.append(f"Self edge: {e['id']}")

    for e in u.get("relationships", []):
        if e["id"] in eids:
            errors.append(f"Duplicate relationship id: {e['id']}")
        eids.add(e["id"])
        check_edge(e, ids)
        pair = tuple(sorted([e["source"], e["target"]]))
        if pair in pairs:
            errors.append("Use one two-perspective relationship per pair")
        pairs.add(pair)

    for p in u.get("suggestions", []):
        if p["id"] in sids:
            errors.append("Duplicate suggestion id")
        sids.add(p["id"])
        char = p.get("character", {})
        cid = char.get("id")
        if cid in pids:
            errors.append("Two suggestions share a character id")
        pids.add(cid)

        if p.get("status") != "accepted" and cid in ids:
            errors.append("Unaccepted suggestion appears in canon")
        if p.get("status") == "accepted" and cid not in ids:
            errors.append("Accepted suggestion missing from canon")
        if char.get("archetype_id") not in aids:
            errors.append("Unknown suggested archetype")

        allowed = ids | {cid}
        local_edges = set()
        for e in p.get("relationships", []):
            check_edge(e, allowed)
            if cid not in (e["source"], e["target"]):
                errors.append("Proposed edge must connect the new character")
            if e["id"] in local_edges or e["id"] in proposed_edges:
                errors.append("Duplicate proposed edge id")
            local_edges.add(e["id"])
            proposed_edges.add(e["id"])
            if p.get("status") != "accepted" and e["id"] in eids:
                errors.append("Proposed edge id already used")
            if p.get("status") == "accepted" and not any(
                r["id"] == e["id"] and r["source"] == e["source"] and r["target"] == e["target"]
                for r in u.get("relationships", [])
            ):
                errors.append("Accepted relationship missing or changed endpoints")

    for c in u.get("characters", []):
        if u.get("relationships") and not any(
            c["id"] in (e["source"], e["target"]) for e in u["relationships"]
        ):
            warnings.append(f"{c['name']} is structurally isolated; this may be intentional.")

    names = [c["name"].lower() for c in u.get("characters", []) if "name" in c]
    if len(set(names)) != len(names):
        warnings.append("Some characters share a name; IDs remain distinct.")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def require_valid(u: dict) -> dict:
    res = validate(u)
    if not res["ok"]:
        raise ValueError("\n".join(res["errors"][:12]))
    return u


def validate_response(request: dict, response: dict, mode: str = "workbuddy") -> dict:
    if not isinstance(response, dict):
        raise ValueError("Response must be an object.")
    if response.get("request_id") != request.get("request_id"):
        raise ValueError("Response belongs to another request.")
    if response.get("base_fingerprint") != request.get("base_fingerprint"):
        raise ValueError("Stale response fingerprint.")

    u = copy.deepcopy(response.get("universe"))
    require_valid(u)

    if request.get("stage") == "cast":
        count = request.get("input", {}).get("count")
        if u.get("revision") != 1:
            raise ValueError("New cast revision must be 1.")
        if u.get("concept") != request.get("input", {}).get("concept"):
            raise ValueError("Preserve the submitted premise exactly.")
        req_fmt = request.get("input", {}).get("format")
        if req_fmt and u.get("format") != req_fmt:
            raise ValueError("Preserve the selected non-game format.")
        if count is not None and len(u.get("characters", [])) != count:
            raise ValueError(f"Expected {count} initial characters.")
        if u.get("relationships") or u.get("suggestions"):
            raise ValueError("Cast stage must leave relationships/suggestions empty for review.")
    else:
        base = request.get("universe", {})
        for field in ("id", "title", "concept", "format", "genre", "tone", "setting", "thematic_thesis", "visual", "characters"):
            if u.get(field) != base.get(field):
                raise ValueError(f"Relationship stage must preserve approved {field}")
        if u.get("revision") != base.get("revision", 0) + 1:
            raise ValueError("Relationship revision must be approved revision + 1.")
        if len(u.get("relationships", [])) < max(3, len(u.get("characters", [])) - 1):
            raise ValueError("Provide enough meaningful edges for a connected graph and at least three story seeds.")
        seen = {u["characters"][0]["id"]}
        while True:
            extended = seen | {
                e["source"] for e in u["relationships"] if e["target"] in seen
            } | {
                e["target"] for e in u["relationships"] if e["source"] in seen
            }
            if extended == seen:
                break
            seen = extended
        if len(seen) != len(u["characters"]):
            raise ValueError("Generated relationship map must connect every approved character.")
        if not (2 <= len(u.get("suggestions", [])) <= 3):
            raise ValueError("Provide two or three optional cast additions.")
        if any(p.get("status") != "pending" for p in u.get("suggestions", [])):
            raise ValueError("New suggestions must remain pending.")

    if "provenance" in u and isinstance(u["provenance"], dict):
        u["provenance"]["mode"] = mode
    return {"request_id": request["request_id"], "base_fingerprint": request["base_fingerprint"], "universe": u}


# --- State mutation operations ---

def accept_suggestion(u: dict, suggestion_id: str) -> dict:
    v = copy.deepcopy(u)
    p = next((s for s in v.get("suggestions", []) if s["id"] == suggestion_id), None)
    if not p or p.get("status") != "pending":
        raise ValueError("This proposal is not pending.")
    if len(v.get("characters", [])) >= 10:
        raise ValueError("This workbench supports up to ten approved characters.")
    char = p.get("character")
    if any(c["id"] == char["id"] for c in v.get("characters", [])):
        raise ValueError("Character already exists in canon.")
    v["characters"].append(copy.deepcopy(char))
    v["relationships"].extend(copy.deepcopy(p.get("relationships", [])))
    p["status"] = "accepted"
    v["revision"] = v.get("revision", 1) + 1
    return require_valid(v)


def reject_suggestion(u: dict, suggestion_id: str) -> dict:
    v = copy.deepcopy(u)
    p = next((s for s in v.get("suggestions", []) if s["id"] == suggestion_id), None)
    if not p or p.get("status") != "pending":
        raise ValueError("This proposal is not pending.")
    p["status"] = "rejected"
    v["revision"] = v.get("revision", 1) + 1
    return require_valid(v)


def rename_character(u: dict, character_id: str, new_name: str) -> dict:
    new_name = new_name.strip()
    if not new_name:
        raise ValueError("A name is required.")
    v = copy.deepcopy(u)
    c = next((char for char in v.get("characters", []) if char["id"] == character_id), None)
    if not c:
        raise ValueError("Character not found.")
    old_name = c["name"]

    def walk(obj):
        if isinstance(obj, str):
            return obj.replace(old_name, new_name)
        if isinstance(obj, list):
            return [walk(x) for x in obj]
        if isinstance(obj, dict):
            return {
                k: (v if k in ("id", "source", "target", "archetype_id") else walk(v))
                for k, v in obj.items()
            }
        return obj

    updated = walk(v)
    updated["revision"] = updated.get("revision", 1) + 1
    return require_valid(updated)


# --- Serialization & Fingerprinting ---

def stable_obj(value: Any) -> Any:
    if isinstance(value, list):
        return [stable_obj(x) for x in value]
    if isinstance(value, dict):
        return {k: stable_obj(value[k]) for k in sorted(value)}
    return value


def stable_json(value: Any) -> str:
    return json.dumps(stable_obj(value), separators=(",", ":"), ensure_ascii=False)


def fingerprint(u: dict) -> str:
    s = stable_json(u)
    h = 2166136261
    for ch in s:
        h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return f"{h:08x}"


# --- Deterministic Compilers ---

def get_character_name(u: dict, cid: str) -> str:
    for c in u.get("characters", []):
        if c["id"] == cid:
            return c.get("name", cid)
    return cid


def compile_assets(u: dict) -> List[dict]:
    v = u.get("visual", {})
    palette = ", ".join(v.get("palette", []))
    style = (
        f"Visual direction: {v.get('style', '')}. "
        f"Palette: {palette}. "
        f"Lighting: {v.get('lighting', '')}. "
        f"Texture: {v.get('texture', '')}. "
        f"Composition: {v.get('composition', '')}. "
        f"Story tone: {u.get('tone', '')}."
    )
    suffix = f"\n\n{style}\n\nNo watermarks or generated lettering. Leave intentional text areas blank for later typesetting."
    out = []

    def add(item_id, category, title, prompt_body, ratio, refs=None):
        out.append({
            "id": item_id,
            "category": category,
            "title": title,
            "prompt": prompt_body + suffix,
            "aspect_ratio": ratio,
            "character_ids": refs or [],
            "revision": u.get("revision", 1),
        })

    for c in u.get("characters", []):
        prompt_body = (
            f"Create a character portrait for {u.get('format', 'narrative')}: \"{u.get('title', '')}\". {c.get('appearance', '')}\n"
            f"Narrative role: {c.get('role', '')}. Emotional baseline: {c.get('emotional_baseline', '')}. "
            f"Show a person who wants {c.get('core_desire', '')} while fearing {c.get('core_fear', '')}\n"
            f"Pose and expression should suggest this contradiction without literal symbolism or diagnostic stereotypes. "
            f"Bust or half-body; readable silhouette; environment belongs to {u.get('setting', '')}."
        )
        add(f"portrait-{c['id']}", "portraits", f"{c['name']} · portrait", prompt_body, "3:4", [c["id"]])

    add(
        "scene-establishing",
        "scenes",
        "The world before the conflict",
        f"Establishing environment for \"{u.get('title', '')}\": {u.get('setting', '')}\n"
        "Show traces of human use and one unoccupied space that suggests an absent person. Emotional function: establish what could be lost. No identifiable real brands.",
        "16:9",
    )

    ranked = sorted(u.get("relationships", []), key=lambda r: (-r.get("intensity", 3), r.get("id", "")))
    for i, e in enumerate(ranked[:2]):
        s_name = get_character_name(u, e["source"])
        t_name = get_character_name(u, e["target"])
        involved_notes = " | ".join(
            f"{c['name']}: {c.get('appearance', '')}"
            for c in u.get("characters", [])
            if c["id"] in (e["source"], e["target"])
        )
        prompt_body = (
            f"A narrative environment or two-person scene involving {s_name} and {t_name}. Context: {u.get('setting', '')}\n"
            f"Relationship: {e.get('label', '')}. Shared history: {e.get('shared_history', '')}\n"
            f"Possible scene: {e.get('breaking_point', '')}\n"
            f"Use blocking, distance and light to express: {e.get('tension', '')}\n"
            f"Emotional purpose: {e.get('story_potential', '')}\n"
            f"Character identity notes: {involved_notes}."
        )
        add(f"scene-{e['id']}", "scenes", "After the encounter" if i else "The pressure point", prompt_body, "16:9", [e["source"], e["target"]])

    add(
        "ui-card",
        "presentation",
        "Character-card frame",
        f"An empty character-card frame for a {u.get('genre', '')} story bible, themed by {u.get('setting', '')}. "
        "Keep the central portrait area clear, with a quiet lower nameplate area and subtle edge texture. "
        "Use the shared palette; restrained and readable. No actual lettering. Do not reproduce a finished game UI.",
        "3:4",
    )
    add(
        "ui-divider",
        "presentation",
        "Chapter & pitch divider",
        f"A wide editorial divider/background for \"{u.get('title', '')}\". Abstract environmental traces from {u.get('setting', '')}; "
        "generous calm negative space on the left for separately added type. Emotional function: anticipation before a shift in relationships. Avoid embedded words or portrait faces.",
        "16:9",
    )
    add(
        "ui-controls",
        "presentation",
        "Buttons & navigation motifs",
        f"A coordinated presentation-component sheet: three blank button surfaces, a subtle rule, and four simple abstract navigation motifs for {u.get('genre', '')}. "
        f"Material language from {v.get('texture', '')}; high-contrast text-safe centers. No letters or baked-in labels. Intended as visual reference, not accessible working controls.",
        "4:3",
    )
    add(
        "moodboard",
        "moodboard",
        "Universe mood board",
        f"A coherent two-by-two reference collage for \"{u.get('title', '')}\". Panel 1: a close detail of hands working in {u.get('setting', '')}. "
        "Panel 2: the environment after people leave. Panel 3: an ordinary object carrying a shared history. Panel 4: two people separated by a small but meaningful distance.\n"
        f"Unifying theme: {u.get('thematic_thesis', '')}\n"
        "Each panel must feel part of the same world, with different scale and focal interest. No labels or typography.",
        "1:1",
    )
    return out


def compile_seeds(u: dict) -> List[dict]:
    titles = [
        "A debt changes shape",
        "A public choice",
        "The cost of telling",
        "An offer with a boundary",
        "The account that differs",
    ]
    ranked = sorted(u.get("relationships", []), key=lambda r: (-r.get("intensity", 3), r.get("id", "")))
    seeds = []
    for i, e in enumerate(ranked[:5]):
        s_name = get_character_name(u, e["source"])
        t_name = get_character_name(u, e["target"])
        label = e.get("label", "").lower()
        seeds.append({
            "id": f"seed-{e['id']}",
            "title": titles[i] if i < len(titles) else f"Seed {i+1}",
            "relationship_id": e["id"],
            "characters": [e["source"], e["target"]],
            "trigger": e.get("breaking_point", ""),
            "hook": f"{s_name} and {t_name} are connected by {label}. {e.get('tension', '')} {e.get('story_potential', '')}",
            "question": f"What does {s_name} risk by pursuing {e.get('source_wants', '')} when {t_name} wants {e.get('target_wants', '')}?",
            "basis_revision": u.get("revision", 1),
        })
    return seeds


def compile_bible(u: dict) -> str:
    sections = [
        f"# {u.get('title', '')}",
        f"*{u.get('format', '')} · {u.get('genre', '')}*",
        f"\n## Premise\n{u.get('concept', '')}",
        f"\n## Thematic core\n{u.get('thematic_thesis', '')}",
        f"\n## Setting and tone\n{u.get('setting', '')}\n\n{u.get('tone', '')}",
        "\n## Approved cast",
    ]
    for c in u.get("characters", []):
        tendencies = "\n".join(f"- {t}" for t in c.get("tendencies", []))
        voice = "\n>\n".join(f"> {v}" for v in c.get("voice_samples", []))
        sections.append(
            f"\n### {c.get('name', '')}\n"
            f"**{c.get('role', '')} — {c.get('archetype_label', '')}**\n\n"
            f"{c.get('backstory', '')}\n\n"
            f"Communication: {c.get('communication_style', '')}\n\n"
            f"Emotional baseline: {c.get('emotional_baseline', '')}\n\n"
            f"Desire: {c.get('core_desire', '')}\n\n"
            f"Fear: {c.get('core_fear', '')}\n\n"
            f"Tendencies:\n{tendencies}\n\n"
            f"Voice samples:\n{voice}\n\n"
            f"Appearance: {c.get('appearance', '')}"
        )

    sections.append("\n## Relationship map")
    for e in u.get("relationships", []):
        s_name = get_character_name(u, e["source"])
        t_name = get_character_name(u, e["target"])
        sections.append(
            f"\n### {s_name} → {t_name}: {e.get('label', '')}\n\n"
            f"Shared event: {e.get('shared_history', '')}\n\n"
            f"{s_name} wants: {e.get('source_wants', '')}\n\n"
            f"{t_name} wants: {e.get('target_wants', '')}\n\n"
            f"Their interpretations:\n"
            f"- {s_name}: {e.get('source_read', '')}\n"
            f"- {t_name}: {e.get('target_read', '')}\n\n"
            f"Tension: {e.get('tension', '')}\n\n"
            f"Breaking point: {e.get('breaking_point', '')}\n\n"
            f"Story potential: {e.get('story_potential', '')}"
        )

    sections.append("\n## Relationship-derived story seeds")
    for s in compile_seeds(u):
        sections.append(
            f"\n### {s['title']}\n"
            f"{s['trigger']}\n\n"
            f"{s['hook']}\n\n"
            f"{s['question']}\n\n"
            f"Source relationship: {s['relationship_id']}"
        )

    sections.append(f"\n## Visual direction\n{json.dumps(u.get('visual', {}), indent=2, ensure_ascii=False)}")
    prov = u.get("provenance", {})
    sections.append(
        f"\n## Provenance and limits\n"
        f"Revision {u.get('revision', 1)}; source mode: {prov.get('mode', 'workbuddy')}. {prov.get('source', '')}\n\n"
        "Story seeds and visual prompts are compiled from the approved record, not a separate live model call. "
        "No images are generated by this application. Unaccepted proposals are excluded from this bible. "
        "Structural checks are not an assessment of literary quality."
    )
    return "\n".join(sections)


def compile_prompt_kit_markdown(u: dict, category: str = "all") -> str:
    lines = [
        f"# {u.get('title', '')} — visual asset prompt kit\n",
        f"Export-only. No images generated. Revision {u.get('revision', 1)}. "
        "Suggested aspect ratios are metadata, not model-specific API parameters.\n",
    ]
    assets = compile_assets(u)
    if category != "all":
        assets = [a for a in assets if a["category"] == category]
    for a in assets:
        lines.append(f"## {a['title']}\nCategory: {a['category']} · Suggested aspect ratio: {a['aspect_ratio']}\n\n{a['prompt']}\n")
    return "\n".join(lines)


def compile_graph_svg(u: dict) -> str:
    """Generate a standalone SVG representation of the relationship graph."""
    characters = u.get("characters", [])
    relationships = u.get("relationships", [])
    width, height = 900, 600
    cx, cy, r = width / 2, height / 2, 220
    import math

    node_pos = {}
    n = max(1, len(characters))
    for i, c in enumerate(characters):
        angle = 2 * math.pi * i / n - math.pi / 2
        node_pos[c["id"]] = (cx + r * math.cos(angle), cy + r * math.sin(angle))

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" style="background:#0f1218; font-family:system-ui,sans-serif;">',
        f'<style>.edge {{ stroke:#5c6b84; stroke-width:2; stroke-opacity:0.6; }} .node {{ fill:#1b2230; stroke:#7c6cff; stroke-width:2; }} .txt {{ fill:#f0f4f8; font-size:12px; text-anchor:middle; }} .lbl {{ fill:#94a3b8; font-size:10px; text-anchor:middle; }}</style>',
        f'<text x="{cx}" y="40" class="txt" style="font-size:18px; font-weight:bold; fill:#ffffff;">{u.get("title", "")} · Relationship Atlas</text>',
    ]

    for rel in relationships:
        s_pos = node_pos.get(rel.get("source"))
        t_pos = node_pos.get(rel.get("target"))
        if s_pos and t_pos:
            lines.append(f'<line x1="{s_pos[0]:.1f}" y1="{s_pos[1]:.1f}" x2="{t_pos[0]:.1f}" y2="{t_pos[1]:.1f}" class="edge" />')
            mx, my = (s_pos[0] + t_pos[0]) / 2, (s_pos[1] + t_pos[1]) / 2
            lines.append(f'<text x="{mx:.1f}" y="{my - 5:.1f}" class="lbl">{rel.get("label", "")}</text>')

    for c in characters:
        pos = node_pos.get(c["id"])
        if pos:
            lines.append(f'<circle cx="{pos[0]:.1f}" cy="{pos[1]:.1f}" r="32" class="node" />')
            lines.append(f'<text x="{pos[0]:.1f}" y="{pos[1] + 4:.1f}" class="txt">{c.get("name", "")}</text>')
            lines.append(f'<text x="{pos[0]:.1f}" y="{pos[1] + 46:.1f}" class="lbl">{c.get("role", "")}</text>')

    lines.append("</svg>")
    return "\n".join(lines)


def package_zip(u: dict, portable_html: Optional[str] = None) -> bytes:
    """Create complete portable ZIP archive matching CharacterOS export standard."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("universe.json", json.dumps(u, indent=2, ensure_ascii=False))
        z.writestr("Character-Bible.md", compile_bible(u))
        z.writestr("Visual-Prompts.md", compile_prompt_kit_markdown(u))
        z.writestr("Story-Seeds.json", json.dumps(compile_seeds(u), indent=2, ensure_ascii=False))
        z.writestr("Relationship-Graph.svg", compile_graph_svg(u))
        if portable_html:
            z.writestr("studio.html", portable_html)
    return buf.getvalue()


# Ergonomic aliases and export dispatcher
validate_universe = validate
compile_prompt_kit = compile_prompt_kit_markdown
compile_markdown_bible = compile_bible
compile_svg_graph = compile_graph_svg
compile_assets_manifest = compile_assets
compute_fingerprint = fingerprint
to_canonical_json = stable_json


def compile_creative_seeds(u: dict) -> str:
    """Format creative seeds as clean text or markdown."""
    seeds = compile_seeds(u)
    if isinstance(seeds, str):
        return seeds
    lines = [f"# Creative Seeds · {u.get('title', 'Story Universe')}", ""]
    if isinstance(seeds, list):
        for s in seeds:
            if isinstance(s, dict):
                lines.append(f"### {s.get('title', 'Story Seed')}")
                if "hook" in s:
                    lines.append(f"**Hook:** {s['hook']}")
                if "premise" in s:
                    lines.append(f"**Premise:** {s['premise']}")
                if "questions" in s and isinstance(s["questions"], list):
                    lines.append("**Key Questions:**")
                    for q in s["questions"]:
                        lines.append(f"- {q}")
                lines.append("")
            else:
                lines.append(f"- {s}")
    elif isinstance(seeds, dict):
        lines.append(json.dumps(seeds, indent=2, ensure_ascii=False))
    return "\n".join(lines)


def compile_export(u: dict, fmt: str, portable_html: Optional[str] = None) -> Union[str, bytes]:
    """Compile universe to any requested export format."""
    fmt_lower = fmt.lower().strip()
    if fmt_lower == "json":
        return stable_json(u)
    elif fmt_lower in ("markdown", "bible", "md"):
        return compile_bible(u)
    elif fmt_lower == "prompts":
        return compile_prompt_kit_markdown(u)
    elif fmt_lower == "seeds":
        return compile_creative_seeds(u)
    elif fmt_lower == "svg":
        return compile_graph_svg(u)
    elif fmt_lower == "assets":
        return json.dumps(compile_assets(u), indent=2, ensure_ascii=False)
    elif fmt_lower == "zip":
        return package_zip(u, portable_html=portable_html)
    else:
        raise ValueError(f"Unsupported export format: '{fmt}'")

