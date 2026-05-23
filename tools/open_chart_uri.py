#!/usr/bin/env python3
from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: open_chart_uri.py 'chart:python%20run%20-c%20TPE%20--show-ichimoku'")
        return 2

    raw = sys.argv[1].strip()
    if not raw.startswith("chart:"):
        print("Expected chart: URI.")
        return 2

    payload = unquote(raw[len("chart:"):]).strip()
    parts = shlex.split(payload)
    if len(parts) < 4 or parts[0] != "python" or parts[1] != "run" or parts[2] != "-c":
        print("Unsupported payload. Expected: python run -c <target> [args]")
        return 2

    project_root = Path(__file__).resolve().parents[1]
    cmd = [sys.executable, str(project_root / "run"), *parts[2:]]
    env = os.environ.copy()
    return subprocess.call(cmd, cwd=project_root, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
