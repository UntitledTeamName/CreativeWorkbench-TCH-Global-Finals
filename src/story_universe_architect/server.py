"""CharacterOS local HTTP server.

Loopback-first, dependency-free HTTP server exposing:
- Static web application assets with dynamic boot data injection
- REST API for story universe validation, persistence, retrieval, and compilation
- Safe, restricted access bound to 127.0.0.1
"""
from __future__ import annotations

import argparse
import html
import json
import mimetypes
import os
import re
import socket
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

from . import __version__, model
from .store import WorkspaceStore

DEFAULT_PORT = 8765
MOVABLE_PORTS = tuple(range(8765, 8771))
SRC_DIR = Path(__file__).resolve().parent
WEB_ROOT = SRC_DIR / "web"
MAX_JSON = 2_000_000


def is_port_free(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def find_available_port(start_port: int = DEFAULT_PORT) -> Optional[int]:
    if is_port_free(start_port):
        return start_port
    for p in MOVABLE_PORTS:
        if p != start_port:
            if is_port_free(p):
                return p
    return None


class CharacterOSServerHandler(BaseHTTPRequestHandler):
    server_version = f"CharacterOS/{__version__}"

    @property
    def store(self) -> WorkspaceStore:
        return self.server.store  # type: ignore

    @property
    def web_root(self) -> Path:
        return self.server.web_root  # type: ignore

    def log_message(self, fmt, *args):
        # Do not log story text or private data to stdout/stderr
        sys.stderr.write(f"[{self.log_date_time_string()}] {fmt % args}\n")

    def safe_origin(self) -> bool:
        port = self.server.server_port
        allowed = {f"127.0.0.1:{port}", f"localhost:{port}", "127.0.0.1", "localhost"}
        host = self.headers.get("Host", "")
        origin = self.headers.get("Origin")
        if host not in allowed:
            return False
        if origin is not None:
            allowed_origins = {f"http://{h}" for h in allowed}
            return origin in allowed_origins
        return True

    def send_json(self, code: int, body: Any, ctype: str = "application/json; charset=utf-8"):
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def send_bytes(self, code: int, data: bytes, ctype: str, filename: Optional[str] = None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def parse_json_body(self) -> Optional[dict]:
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > MAX_JSON:
                self.send_json(413, {"error": "Request body exceeds local size limit."})
                return None
            ctype = self.headers.get("Content-Type", "")
            if "application/json" not in ctype:
                self.send_json(415, {"error": "Content-Type must be application/json."})
                return None
            raw = self.rfile.read(size)
            return json.loads(raw.decode("utf-8"))
        except (ValueError, json.JSONDecodeError) as e:
            self.send_json(400, {"error": f"Invalid JSON payload: {str(e)}"})
            return None

    def render_app_html(self, workspace_id: Optional[str] = None) -> bytes:
        index_path = self.web_root / "index.html"
        if not index_path.is_file():
            return b"<!DOCTYPE html><html><body><h1>CharacterOS web assets not found.</h1></body></html>"

        html = index_path.read_text(encoding="utf-8")
        universe = None
        if workspace_id:
            ws = self.store.get_workspace(workspace_id)
            if ws:
                universe = ws["universe"]

        if universe:
            # Inject workspace universe into boot-data
            match = re.search(r'<script\b[^>]*\bid=["\']boot-data["\'][^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE)
            if match:
                try:
                    boot = json.loads(match.group(1))
                    boot["initial"] = universe
                    boot["portable"] = False
                    boot_json = json.dumps(boot, ensure_ascii=False).replace("<", "\\u003c")
                    new_tag = f'<script type="application/json" id="boot-data">{boot_json}</script>'
                    html = html[:match.start()] + new_tag + html[match.end():]
                except Exception:
                    pass

        return html.encode("utf-8")

    def do_GET(self):
        if not self.safe_origin():
            return self.send_json(403, {"error": "Untrusted host or origin."})

        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Health / status
        if path == "/api/health":
            return self.send_json(200, {
                "status": "ok",
                "version": __version__,
                "port": self.server.server_port,
                "pid": os.getpid(),
                "workspaces_count": len(self.store.list_workspaces()),
                "data_dir": str(self.store.dir),
            })

        if path == "/api/status":
            return self.send_json(200, {
                "version": __version__,
                "bridge": True,
                "token": "characteros-loopback-session",
                "live_configured": False,
                "model": "",
                "project": str(SRC_DIR),
                "data_dir": str(self.store.dir),
                "workspaces_count": len(self.store.list_workspaces()),
            })

        # List workspaces
        if path == "/api/workspaces":
            return self.send_json(200, {"workspaces": self.store.list_workspaces()})

        # Workspace details
        match_ws = re.fullmatch(r"/api/workspaces/([a-zA-Z0-9_-]+)", path)
        if match_ws:
            wid = match_ws.group(1)
            ws = self.store.get_workspace(wid)
            if not ws:
                return self.send_json(404, {"error": f"Workspace '{wid}' not found."})
            return self.send_json(200, ws)

        # Workspace universe
        match_uni = re.fullmatch(r"/api/workspaces/([a-zA-Z0-9_-]+)/universe", path)
        if match_uni:
            wid = match_uni.group(1)
            uni = self.store.get_universe(wid)
            if not uni:
                return self.send_json(404, {"error": f"Workspace '{wid}' not found."})
            return self.send_json(200, uni)

        # Workspace export
        match_exp = re.fullmatch(r"/api/workspaces/([a-zA-Z0-9_-]+)/export/([a-zA-Z0-9_-]+)", path)
        if match_exp:
            wid, fmt = match_exp.group(1), match_exp.group(2)
            try:
                portable_html = None
                if fmt.lower() == "zip":
                    try:
                        portable_html = (self.web_root / "index.html").read_text(encoding="utf-8")
                    except OSError:
                        pass
                content = self.store.export_workspace(wid, fmt, portable_html=portable_html)
                if isinstance(content, bytes):
                    return self.send_bytes(200, content, "application/zip", f"{wid}.zip")
                elif fmt.lower() == "svg":
                    return self.send_bytes(200, content.encode("utf-8"), "image/svg+xml", f"{wid}.svg")
                elif fmt.lower() in ("markdown", "bible", "prompts", "md"):
                    return self.send_bytes(200, content.encode("utf-8"), "text/markdown; charset=utf-8", f"{wid}.md")
                else:
                    return self.send_bytes(200, content.encode("utf-8"), "application/json; charset=utf-8", f"{wid}.json")
            except FileNotFoundError:
                return self.send_json(404, {"error": f"Workspace '{wid}' not found."})
            except ValueError as e:
                return self.send_json(400, {"error": str(e)})

        # Static assets
        if path.startswith("/static/"):
            rel_file = path[len("/static/"):]
            target = (self.web_root / rel_file).resolve()
            if self.web_root in target.parents and target.is_file():
                mime, _ = mimetypes.guess_type(str(target))
                return self.send_bytes(200, target.read_bytes(), mime or "application/octet-stream")

        # Top-level files in web/
        if path in ("/style.css", "/app.js", "/core.js"):
            target = (self.web_root / path[1:]).resolve()
            if target.is_file():
                mime, _ = mimetypes.guess_type(str(target))
                return self.send_bytes(200, target.read_bytes(), mime or "application/octet-stream")

        # HTML interface (root, /?workspace=<id>, or /<workspace_id>)
        if path in ("/", "/index.html"):
            wid = query.get("workspace", [None])[0]
            return self.send_bytes(200, self.render_app_html(wid), "text/html; charset=utf-8")

        # Path-based workspace URL: /<workspace_id>
        match_ws_page = re.fullmatch(r"/([a-zA-Z0-9_-]+)", path)
        if match_ws_page:
            wid = match_ws_page.group(1)
            if self.store.get_workspace(wid):
                return self.send_bytes(200, self.render_app_html(wid), "text/html; charset=utf-8")

        return self.send_json(404, {"error": f"Path '{path}' not found."})

    def do_POST(self):
        if not self.safe_origin():
            return self.send_json(403, {"error": "Untrusted host or origin."})

        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Validate universe without saving
        if path == "/api/validate":
            payload = self.parse_json_body()
            if payload is None:
                return
            universe = payload.get("universe", payload)
            res = model.validate(universe)
            return self.send_json(200 if res["ok"] else 422, res)

        # Create or update workspace
        if path == "/api/workspaces":
            payload = self.parse_json_body()
            if payload is None:
                return
            wid = payload.get("workspace_id") or payload.get("id")
            universe = payload.get("universe")
            if not wid or not universe:
                return self.send_json(400, {"error": "Requires 'workspace_id' and 'universe'"})
            try:
                saved = self.store.save_universe(wid, universe)
                return self.send_json(201, saved)
            except ValueError as e:
                return self.send_json(422, {"error": str(e)})

        # Publish / update universe to workspace
        match_uni = re.fullmatch(r"/api/workspaces/([a-zA-Z0-9_-]+)/universe", path)
        if match_uni:
            wid = match_uni.group(1)
            payload = self.parse_json_body()
            if payload is None:
                return
            universe = payload.get("universe", payload)
            try:
                saved = self.store.save_universe(wid, universe)
                return self.send_json(200, saved)
            except ValueError as e:
                return self.send_json(422, {"error": str(e)})

        return self.send_json(404, {"error": f"Post endpoint '{path}' not found."})

    def do_PUT(self):
        # Allow PUT /api/workspaces/<id>/universe
        return self.do_POST()

    def do_PATCH(self):
        if not self.safe_origin():
            return self.send_json(403, {"error": "Untrusted host or origin."})

        match_uni = re.fullmatch(r"/api/workspaces/([a-zA-Z0-9_-]+)/universe", self.path)
        if match_uni:
            wid = match_uni.group(1)
            payload = self.parse_json_body()
            if payload is None:
                return
            try:
                updated = self.store.patch_universe(wid, payload)
                return self.send_json(200, updated)
            except FileNotFoundError as e:
                return self.send_json(404, {"error": str(e)})
            except ValueError as e:
                return self.send_json(422, {"error": str(e)})

        return self.send_json(404, {"error": f"Patch endpoint '{self.path}' not found."})

    def do_DELETE(self):
        if not self.safe_origin():
            return self.send_json(403, {"error": "Untrusted host or origin."})

        match_ws = re.fullmatch(r"/api/workspaces/([a-zA-Z0-9_-]+)", self.path)
        if match_ws:
            wid = match_ws.group(1)
            if self.store.delete_workspace(wid):
                return self.send_json(200, {"ok": True, "deleted": wid})
            return self.send_json(404, {"error": f"Workspace '{wid}' not found."})

        return self.send_json(404, {"error": f"Delete endpoint '{self.path}' not found."})

    def do_OPTIONS(self):
        self.send_json(403, {"error": "Cross-origin access is disabled."})


class CharacterOSServer(ThreadingHTTPServer):
    def __init__(self, host: str = "127.0.0.1", port: int = DEFAULT_PORT, data_dir: Optional[Union[str, Path]] = None, web_root: Optional[Union[str, Path]] = None):
        self.store = WorkspaceStore(data_dir=data_dir)
        self.web_root = Path(web_root).resolve() if web_root else WEB_ROOT
        super().__init__((host, port), CharacterOSServerHandler)


SUAServerHandler = CharacterOSServerHandler
SUAServer = CharacterOSServer


def create_server(host: str = "127.0.0.1", port: int = DEFAULT_PORT, data_dir: Optional[Union[str, Path]] = None, web_root: Optional[Union[str, Path]] = None, store_instance: Optional[WorkspaceStore] = None) -> CharacterOSServer:
    """Factory helper to instantiate a configured CharacterOSServer instance."""
    srv = CharacterOSServer(host=host, port=port, data_dir=data_dir, web_root=web_root)
    if store_instance:
        srv.store = store_instance
    return srv



def run_server(port: int = DEFAULT_PORT, data_dir: Optional[str] = None, no_browser: bool = True) -> int:
    chosen_port = find_available_port(port)
    if chosen_port is None:
        sys.stderr.write(f"Error: Could not find an available port in range {DEFAULT_PORT}-{MOVABLE_PORTS[-1]}.\n")
        return 2

    server = CharacterOSServer(host="127.0.0.1", port=chosen_port, data_dir=data_dir)
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"CharacterOS {__version__} is running at {url}", flush=True)
    print(f"Workspaces data directory: {server.store.dir}", flush=True)

    if not no_browser:
        import webbrowser
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def main():
    ap = argparse.ArgumentParser(prog="characteros-server", description="CharacterOS HTTP server.")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to listen on (default: 8765).")
    ap.add_argument("--data-dir", type=str, default=None, help="Custom data directory for story workspaces.")
    ap.add_argument("--no-browser", action="store_true", default=True, help="Do not automatically open browser.")
    args = ap.parse_args()
    sys.exit(run_server(port=args.port, data_dir=args.data_dir, no_browser=args.no_browser))


if __name__ == "__main__":
    main()
