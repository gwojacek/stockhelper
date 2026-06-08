#!/usr/bin/env python3
from __future__ import annotations

import argparse
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Print report-server console log updates to this terminal")
    parser.add_argument("--log", required=True, help="Log file to follow")
    parser.add_argument("--idle-timeout", type=float, default=12 * 60 * 60, help="Seconds to stay alive without new output")
    args = parser.parse_args()

    path = Path(args.log)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)

    offset = path.stat().st_size
    last_output = time.time()
    while True:
        try:
            size = path.stat().st_size
            if size < offset:
                offset = 0
            if size > offset:
                with path.open("r", encoding="utf-8", errors="replace") as handle:
                    handle.seek(offset)
                    chunk = handle.read()
                    offset = handle.tell()
                if chunk:
                    print(chunk, end="", flush=True)
                    last_output = time.time()
            elif time.time() - last_output > args.idle_timeout:
                return 0
        except KeyboardInterrupt:
            return 130
        except Exception as exc:
            print(f"[report-console] failed to follow {path}: {exc}", flush=True)
            time.sleep(2.0)
        time.sleep(0.25)


if __name__ == "__main__":
    raise SystemExit(main())
