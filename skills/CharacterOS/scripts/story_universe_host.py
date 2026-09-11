"""CharacterOS host process helper."""
from __future__ import annotations

import json
import os
import signal
import sys
from pathlib import Path

from story_universe_connect import find_active_server, probe_server


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        active = find_active_server()
        if active:
            port, info = active
            print(f"Active on 127.0.0.1:{port} (PID {info.get('pid')})")
            sys.exit(0)
        else:
            print("No active CharacterOS server found.")
            sys.exit(1)

    print("Usage: story_universe_host.py status")
    sys.exit(0)


if __name__ == "__main__":
    main()
