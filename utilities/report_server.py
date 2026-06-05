#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import webbrowser
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

REPORT_SERVER_PROTOCOL = "stockhelper-report-server-v2"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    project_root = Path(args.project_root).resolve()


    def _canonicalize_chart_command(command: str) -> str:
        # Reports often store WSE tickers as CIG.WA while the normal
        # `python run -c cig` flow stores sessions/configs under `cig.py`.
        # Canonicalize report-launched WSE chart commands so both entrypoints
        # share exactly the same chart session and TradingConfig path.
        return re.sub(
            r"(\bpython(?:3)?\s+run\s+-c\s+)([A-Za-z0-9_-]+)\.(WA|PL)\b",
            lambda m: f"{m.group(1)}{m.group(2)}",
            command,
            flags=re.IGNORECASE,
        )

    def _open_console_target(name: str, fallback):
        path = os.environ.get(name, "")
        if not path:
            return fallback, None
        try:
            handle = open(path, "a", buffering=1, encoding="utf-8", errors="replace")
            return handle, handle
        except Exception:
            return fallback, None

    # Open the launcher console once while the parent `run` process is still
    # alive. If we only opened /proc/<parent>/fd/* later, Chrome/PyCharm may
    # have already let the short-lived launcher exit, making the fd path invalid
    # and hiding report-launched chart calculations. Keeping this handle open
    # preserves the same terminal target for all later /run-command calls.
    console_out, close_console_out = _open_console_target("STOCKHELPER_REPORT_CONSOLE_STDOUT", sys.stdout)
    console_err, close_console_err = _open_console_target("STOCKHELPER_REPORT_CONSOLE_STDERR", sys.stderr)

    def _run_chart_command(command: str) -> int:
        command = _canonicalize_chart_command(command)
        argv = shlex.split(command)
        if len(argv) >= 2 and argv[0] in {"python", "python3"} and argv[1] == "run":
            argv = [sys.executable, str(project_root / "run"), *argv[2:]]
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["STOCKHELPER_REPORT_LAUNCHED_CHART"] = "1"
        print(f"[report] running chart command: {' '.join(shlex.quote(a) for a in argv)}", file=console_out, flush=True)
        # Run synchronously in this server thread. The report page fetch stays
        # pending until the chart is finished, which keeps the post-save
        # `python run <config>` calculation attached to the same visible console.
        rc = subprocess.call(argv, cwd=str(project_root), env=env, stdout=console_out, stderr=console_err)
        print(f"[report] chart command exit: {rc}", file=console_out, flush=True)
        return rc

    class _Handler(SimpleHTTPRequestHandler):
        def __init__(self, *h_args, **h_kwargs):
            super().__init__(*h_args, directory=str(root), **h_kwargs)

        def log_message(self, fmt, *m_args):
            return

        def end_headers(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            super().end_headers()

        def do_OPTIONS(self):
            self.send_response(204)
            self.end_headers()

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/__stockhelper_report_server_info":
                payload = {"protocol": REPORT_SERVER_PROTOCOL, "project_root": str(project_root), "root": str(root)}
                self.send_response(200); self.end_headers(); self.wfile.write(json.dumps(payload).encode("utf-8")); return
            if parsed.path == "/run-command":
                qs = parse_qs(parsed.query)
                command = (qs.get("command", [""])[0] or "").strip()
                if not command:
                    self.send_response(400); self.end_headers(); self.wfile.write(b"missing command"); return
                try:
                    rc = _run_chart_command(command)
                    self.send_response(200 if rc == 0 else 500); self.end_headers(); self.wfile.write(("ok" if rc == 0 else f"exit {rc}").encode("utf-8"))
                except Exception as exc:
                    self.send_response(500); self.end_headers(); self.wfile.write(str(exc).encode("utf-8"))
                return
            super().do_GET()

        def do_POST(self):
            parsed = urlparse(self.path)
            if parsed.path == "/run-command":
                qs = parse_qs(parsed.query)
                command = (qs.get("command", [""])[0] or "").strip()
                if not command:
                    self.send_response(400); self.end_headers(); self.wfile.write(b"missing command"); return
                try:
                    rc = _run_chart_command(command)
                    self.send_response(200 if rc == 0 else 500); self.end_headers(); self.wfile.write(("ok" if rc == 0 else f"exit {rc}").encode("utf-8"))
                except Exception as exc:
                    self.send_response(500); self.end_headers(); self.wfile.write(str(exc).encode("utf-8"))
                return
            if parsed.path == "/open-links":
                try:
                    ln = int(self.headers.get("content-length", "0") or "0")
                    raw = self.rfile.read(ln).decode("utf-8") if ln > 0 else "{}"
                    payload = json.loads(raw or "{}")
                    links = payload.get("links") or []
                    opened = 0
                    for link in links:
                        if isinstance(link, str) and link.startswith("http"):
                            webbrowser.open_new_tab(link)
                            opened += 1
                    self.send_response(200); self.end_headers(); self.wfile.write(json.dumps({"opened": opened}).encode("utf-8"))
                except Exception as exc:
                    self.send_response(500); self.end_headers(); self.wfile.write(str(exc).encode("utf-8"))
                return
            self.send_response(404); self.end_headers()

    server = ThreadingHTTPServer((args.host, args.port), _Handler)
    try:
        server.serve_forever()
    finally:
        if close_console_out is not None:
            close_console_out.close()
        if close_console_err is not None and close_console_err is not close_console_out:
            close_console_err.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
