"""Story Universe Architect command-line interface.

Provides commands to start, inspect, stop the server, validate story files,
and manage story workspaces.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from . import __version__
from . import model
from .server import DEFAULT_PORT, MOVABLE_PORTS, run_server
from .store import WorkspaceStore

PID_FILE = Path.home() / ".story-universe-architect" / "sua.pid"


def probe_health(port: int, timeout: float = 1.0) -> Optional[dict]:
    url = f"http://127.0.0.1:{port}/api/health"
    try:
        req = urllib.request.Request(url, headers={"Host": f"127.0.0.1:{port}"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                return data if data.get("status") == "ok" else None
    except Exception:
        return None
    return None


def find_running_server() -> Optional[Tuple[int, dict]]:
    for p in (DEFAULT_PORT, *MOVABLE_PORTS):
        info = probe_health(p)
        if info:
            return p, info
    return None


def cmd_start(args) -> int:
    running = find_running_server()
    if running:
        port, info = running
        print(f"Story Universe Architect is already running at http://127.0.0.1:{port}")
        print(f"Version: {info.get('version')} | Workspaces: {info.get('workspaces_count')}")
        return 0

    if not args.daemon:
        return run_server(port=args.port, data_dir=args.data_dir, no_browser=args.no_browser)

    # Launch detached daemon process
    python_exe = sys.executable or "python"
    cmd = [python_exe, "-m", "story_universe_architect.server", "--port", str(args.port)]
    if args.data_dir:
        cmd.extend(["--data-dir", str(args.data_dir)])
    if args.no_browser:
        cmd.append("--no-browser")

    popen_kwargs = dict(
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if os.name == "nt":
        popen_kwargs["creationflags"] = (
            subprocess.CREATE_NO_WINDOW | getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        )
    else:
        popen_kwargs["start_new_session"] = True

    try:
        proc = subprocess.Popen(cmd, **popen_kwargs)
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    except Exception as e:
        sys.stderr.write(f"Failed to start server process: {e}\n")
        return 1

    # Wait for server to become healthy
    deadline = time.time() + 15.0
    while time.time() < deadline:
        running = find_running_server()
        if running:
            port, info = running
            print(f"Story Universe Architect started successfully at http://127.0.0.1:{port}")
            print(f"PID: {proc.pid} | Data dir: {info.get('data_dir')}")
            return 0
        time.sleep(0.2)

    sys.stderr.write("Server started but did not respond to health check within 15 seconds.\n")
    return 2


def cmd_status(args) -> int:
    running = find_running_server()
    if running:
        port, info = running
        if args.json:
            print(json.dumps({"running": True, "port": port, "health": info}, indent=2))
        else:
            print(f"Story Universe Architect is running at http://127.0.0.1:{port}")
            print(f"  Version:     {info.get('version')}")
            print(f"  PID:         {info.get('pid')}")
            print(f"  Workspaces:  {info.get('workspaces_count')}")
            print(f"  Data dir:    {info.get('data_dir')}")
        return 0
    else:
        if args.json:
            print(json.dumps({"running": False}, indent=2))
        else:
            print("Story Universe Architect is not currently running.")
        return 1


def cmd_stop(args) -> int:
    running = find_running_server()
    stopped = False

    if PID_FILE.is_file():
        try:
            pid = int(PID_FILE.read_text(encoding="utf-8").strip())
            os.kill(pid, signal.SIGTERM)
            stopped = True
        except (OSError, ValueError):
            pass
        PID_FILE.unlink(missing_ok=True)

    if running and not stopped:
        port, info = running
        pid = info.get("pid")
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
                stopped = True
            except OSError:
                pass

    if stopped:
        print("Story Universe Architect server stopped.")
        return 0
    elif running:
        sys.stderr.write("Could not automatically stop the running process. Please terminate PID manually.\n")
        return 1
    else:
        print("Story Universe Architect is not running.")
        return 0


def cmd_validate(args) -> int:
    path = Path(args.file)
    if not path.is_file():
        sys.stderr.write(f"File not found: {path}\n")
        return 1
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        res = model.validate(data)
        if res["ok"]:
            print(f"Valid Story Universe ({len(data.get('characters', []))} characters, {len(data.get('relationships', []))} relationships).")
            if res.get("warnings"):
                for w in res["warnings"]:
                    print(f"  Warning: {w}")
            return 0
        else:
            print("Validation FAILED with errors:")
            for err in res["errors"]:
                print(f"  - {err}")
            return 2
    except Exception as e:
        sys.stderr.write(f"Validation error: {e}\n")
        return 1


def cmd_workspace(args) -> int:
    store = WorkspaceStore(data_dir=args.data_dir)
    if args.ws_action == "list":
        workspaces = store.list_workspaces()
        if args.json:
            print(json.dumps(workspaces, indent=2, ensure_ascii=False))
        else:
            print(f"Story Universe Workspaces ({len(workspaces)}):")
            for ws in workspaces:
                print(f"  - {ws['id']:<24} {ws['title'][:32]:<34} (Cast: {ws['characters_count']}, Revision: {ws['revision']})")
        return 0
    elif args.ws_action == "get":
        ws = store.get_workspace(args.id)
        if not ws:
            sys.stderr.write(f"Workspace not found: '{args.id}'\n")
            return 1
        print(json.dumps(ws["universe"], indent=2, ensure_ascii=False))
        return 0
    elif args.ws_action == "delete":
        if store.delete_workspace(args.id):
            print(f"Workspace '{args.id}' deleted.")
            return 0
        sys.stderr.write(f"Workspace '{args.id}' not found.\n")
        return 1
    return 0


def cmd_export(args) -> int:
    store = WorkspaceStore(data_dir=args.data_dir)
    try:
        content = store.export_workspace(args.workspace_id, args.format)
        if args.output:
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                out_path.write_bytes(content)
            else:
                out_path.write_text(content, encoding="utf-8")
            print(f"Exported {args.workspace_id} ({args.format}) to {out_path}")
        else:
            if isinstance(content, bytes):
                sys.stdout.buffer.write(content)
            else:
                sys.stdout.write(content + "\n")
        return 0
    except Exception as e:
        sys.stderr.write(f"Export failed: {e}\n")
        return 1


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="sua",
        description=f"Story Universe Architect CLI (v{__version__}) - narrative universe workbench",
    )
    ap.add_argument("-v", "--version", action="version", version=f"Story Universe Architect {__version__}")

    sub = ap.add_subparsers(dest="subcommand")

    # sua start
    p_start = sub.add_parser("start", help="Start the local Story Universe Architect server.")
    p_start.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to bind to (default: 8765).")
    p_start.add_argument("--data-dir", type=str, default=None, help="Custom data directory for story universes.")
    p_start.add_argument("--daemon", action="store_true", help="Run server in the background.")
    p_start.add_argument("--no-browser", action="store_true", default=True, help="Do not automatically open browser.")

    # sua status
    p_status = sub.add_parser("status", help="Check status of the local server.")
    p_status.add_argument("--json", action="store_true", help="Emit JSON output.")

    # sua stop
    sub.add_parser("stop", help="Stop the running local server.")

    # sua validate
    p_val = sub.add_parser("validate", help="Validate a story universe JSON file.")
    p_val.add_argument("file", help="Path to universe JSON file.")

    # sua workspace
    p_ws = sub.add_parser("workspace", help="Manage story workspaces.")
    p_ws.add_argument("--data-dir", type=str, default=None, help="Custom data directory.")
    p_ws.add_argument("--json", action="store_true", help="Emit JSON output.")
    ws_sub = p_ws.add_subparsers(dest="ws_action")
    ws_sub.add_parser("list", help="List all saved workspaces.")
    p_ws_get = ws_sub.add_parser("get", help="Get a workspace by ID.")
    p_ws_get.add_argument("id", help="Workspace ID.")
    p_ws_del = ws_sub.add_parser("delete", help="Delete a workspace by ID.")
    p_ws_del.add_argument("id", help="Workspace ID.")

    # sua export
    p_exp = sub.add_parser("export", help="Export a story universe to file.")
    p_exp.add_argument("workspace_id", help="Workspace ID.")
    p_exp.add_argument("format", choices=["json", "markdown", "bible", "prompts", "seeds", "svg", "zip"], help="Export format.")
    p_exp.add_argument("--output", "-o", help="Target output file path.")
    p_exp.add_argument("--data-dir", type=str, default=None, help="Custom data directory.")

    return ap


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.subcommand:
        parser.print_help()
        return 0

    if args.subcommand == "start":
        return cmd_start(args)
    elif args.subcommand == "status":
        return cmd_status(args)
    elif args.subcommand == "stop":
        return cmd_stop(args)
    elif args.subcommand == "validate":
        return cmd_validate(args)
    elif args.subcommand == "workspace":
        return cmd_workspace(args)
    elif args.subcommand == "export":
        return cmd_export(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
