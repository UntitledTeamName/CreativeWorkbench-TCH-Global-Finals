"""Command-line interface for WorkBuddy to interact with Story Universe Architect."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from story_universe_connect import SUAClient, ensure_server_running, find_active_server


def main():
    ap = argparse.ArgumentParser(description="WorkBuddy SUA CLI adapter.")
    sub = ap.add_subparsers(dest="action")

    # start
    p_start = sub.add_parser("start", help="Ensure SUA runtime is active and report URL.")
    p_start.add_argument("--port", type=int, default=8765)

    # status
    sub.add_parser("status", help="Check if SUA runtime is running.")

    # validate
    p_val = sub.add_parser("validate", help="Validate a candidate universe JSON file.")
    p_val.add_argument("--input", "-i", required=True, help="Path to universe JSON.")

    # publish
    p_pub = sub.add_parser("publish", help="Validate and publish candidate universe to workspace.")
    p_pub.add_argument("--workspace-id", "-w", required=True, help="Target workspace ID.")
    p_pub.add_argument("--input", "-i", required=True, help="Path to universe JSON.")

    # patch
    p_patch = sub.add_parser("patch", help="Apply structured patch to workspace universe.")
    p_patch.add_argument("--workspace-id", "-w", required=True, help="Target workspace ID.")
    p_patch.add_argument("--input", "-i", required=True, help="Path to patch JSON.")

    # get
    p_get = sub.add_parser("get", help="Retrieve current universe JSON from workspace.")
    p_get.add_argument("--workspace-id", "-w", required=True, help="Target workspace ID.")

    # url
    p_url = sub.add_parser("url", help="Get localhost URL for a workspace.")
    p_url.add_argument("--workspace-id", "-w", required=True, help="Target workspace ID.")

    args = ap.parse_args()
    if not args.action:
        ap.print_help()
        return 0

    if args.action == "status":
        active = find_active_server()
        if active:
            port, info = active
            print(json.dumps({"running": True, "port": port, "url": f"http://127.0.0.1:{port}", "info": info}, indent=2))
            return 0
        else:
            print(json.dumps({"running": False}, indent=2))
            return 1

    client = SUAClient()

    if args.action == "start":
        print(f"SUA runtime ready: {client.base_url}")
        print(f"Health: {json.dumps(client.server_info, indent=2)}")
        return 0

    if args.action == "validate":
        data = json.loads(Path(args.input).read_text(encoding="utf-8"))
        res = client.validate(data)
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0 if res.get("ok") else 2

    if args.action == "publish":
        data = json.loads(Path(args.input).read_text(encoding="utf-8"))
        res = client.publish_universe(args.workspace_id, data)
        print(f"Universe published to workspace '{args.workspace_id}'.")
        print(f"URL: {client.workspace_url(args.workspace_id)}")
        return 0

    if args.action == "patch":
        patch_data = json.loads(Path(args.input).read_text(encoding="utf-8"))
        res = client.patch_universe(args.workspace_id, patch_data)
        print(f"Patch applied to workspace '{args.workspace_id}'.")
        print(f"URL: {client.workspace_url(args.workspace_id)}")
        return 0

    if args.action == "get":
        u = client.get_universe(args.workspace_id)
        print(json.dumps(u, indent=2, ensure_ascii=False))
        return 0

    if args.action == "url":
        print(client.workspace_url(args.workspace_id))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
