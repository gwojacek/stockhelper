#!/usr/bin/env python3
from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: open_chart_uri.py 'chart:python%20run%20-c%20TPE%20--show-ichimoku'")
        return 2

    project_root = Path(__file__).resolve().parents[1]
    raw = sys.argv[1].strip()
    cmd: list[str]

    if raw.startswith("chart://"):
        parsed = urlparse(raw)
        parts = [unquote(x) for x in parsed.path.split("/") if x]
        ticker = unquote(parsed.netloc or "")
        if not ticker:
            print("chart:// URI must include ticker host, e.g. chart://TPE/ichimoku")
            return 2
        cmd = [sys.executable, str(project_root / "run"), "-c", ticker]
        if len(parts) == 1 and parts[0].lower() == "ichimoku":
            cmd.append("--show-ichimoku")
        elif len(parts) >= 3:
            direction, d1, d2 = parts[0], parts[1], parts[2]
            cmd.extend(["--fibo-anchor", direction, d1, d2, "--fibo-levels", "0,23.6,38.2,61.8,100"])
    elif raw.startswith("chart:"):
        payload = unquote(raw[len("chart:"):]).strip()
        p = shlex.split(payload)
        if len(p) < 4 or p[0] != "python" or p[1] != "run" or p[2] != "-c":
            print("Unsupported payload. Expected: python run -c <target> [args]")
            return 2
        cmd = [sys.executable, str(project_root / "run"), *p[2:]]
    else:
        print("Expected chart: or chart:// URI.")
        return 2

    env = os.environ.copy()
    return subprocess.call(cmd, cwd=project_root, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
