"""Build the standalone single-file index.html for CharacterOS."""
from __future__ import annotations

import base64
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "src" / "story_universe_architect" / "web"


def build_h5() -> Path:
    schema = json.loads((ROOT / "schemas" / "universe.schema.json").read_text(encoding="utf-8"))
    archetypes = json.loads((ROOT / "schemas" / "archetypes.json").read_text(encoding="utf-8"))
    themes = json.loads((ROOT / "schemas" / "themes.json").read_text(encoding="utf-8"))

    examples = {}
    for p in sorted((ROOT / "examples").glob("*.universe.json")):
        key = p.name.split(".")[0]
        examples[key] = json.loads(p.read_text(encoding="utf-8"))

    boot_data = {
        "schema": schema,
        "archetypes": archetypes,
        "themes": themes,
        "examples": examples,
    }

    template = (WEB_DIR / "index.template.html").read_text(encoding="utf-8")
    css = (WEB_DIR / "style.css").read_text(encoding="utf-8")
    core = (WEB_DIR / "core.js").read_text(encoding="utf-8")
    app = (WEB_DIR / "app.js").read_text(encoding="utf-8")

    logo_path = WEB_DIR / "logo.png"
    if logo_path.is_file():
        b64_logo = base64.b64encode(logo_path.read_bytes()).decode("ascii")
        app = app.replace("/*__LOGO_SRC__*/ 'logo.png'", f"'data:image/png;base64,{b64_logo}'")

    rendered = template.replace("/*__CSS__*/", css)
    rendered = rendered.replace("/*__CORE__*/", core)
    rendered = rendered.replace("/*__APP__*/", app)
    rendered = rendered.replace("/*__DATA__*/", json.dumps(boot_data, ensure_ascii=False).replace("<", "\\u003c"))

    out_file = WEB_DIR / "index.html"
    out_file.write_text(rendered, encoding="utf-8")
    return out_file


if __name__ == "__main__":
    out = build_h5()
    print(f"Built standalone index.html: {out} ({out.stat().st_size} bytes)")
