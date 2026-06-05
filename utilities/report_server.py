#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
import webbrowser
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

REPORT_SERVER_PROTOCOL = "stockhelper-report-server-v3"


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

    def _open_console_path(path: str, fallback):
        if not path:
            return fallback, None
        try:
            handle = open(path, "a", buffering=1, encoding="utf-8", errors="replace")
            return handle, handle
        except Exception:
            return fallback, None

    console_out, close_console_out = sys.stdout, None
    console_err, close_console_err = sys.stderr, None

    def _set_console_targets(stdout_path: str = "", stderr_path: str = "") -> bool:
        nonlocal console_out, close_console_out, console_err, close_console_err
        new_out, new_close_out = _open_console_path(stdout_path, sys.stdout)
        new_err, new_close_err = _open_console_path(stderr_path, sys.stderr)
        if stdout_path and new_close_out is None:
            return False
        if stderr_path and new_close_err is None:
            if new_close_out is not None:
                new_close_out.close()
            return False
        old_close_out, old_close_err = close_console_out, close_console_err
        console_out, close_console_out = new_out, new_close_out
        console_err, close_console_err = new_err, new_close_err
        if old_close_out is not None:
            old_close_out.close()
        if old_close_err is not None and old_close_err is not old_close_out:
            old_close_err.close()
        return True

    # Open the launcher console once while the parent `run` process is still
    # alive. If this server is reused by a later report open, /attach-console
    # refreshes these handles to that newer launcher terminal.
    _set_console_targets(
        os.environ.get("STOCKHELPER_REPORT_CONSOLE_STDOUT", ""),
        os.environ.get("STOCKHELPER_REPORT_CONSOLE_STDERR", ""),
    )

    def _is_report_chart_command(argv: list[str]) -> bool:
        return len(argv) >= 3 and Path(argv[1]).name == "run" and argv[2] in {"-c", "--chart"}

    def _run_chart_command(command: str) -> tuple[int, dict]:
        command = _canonicalize_chart_command(command)
        argv = shlex.split(command)
        if len(argv) >= 2 and argv[0] in {"python", "python3"} and argv[1] == "run":
            argv = [sys.executable, str(project_root / "run"), *argv[2:]]
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["STOCKHELPER_REPORT_LAUNCHED_CHART"] = "1"
        print(f"[report] running chart command: {' '.join(shlex.quote(a) for a in argv)}", file=console_out, flush=True)

        if _is_report_chart_command(argv):
            fd, url_path = tempfile.mkstemp(prefix="stockhelper_chart_url_", suffix=".txt")
            os.close(fd)
            try:
                env["STOCKHELPER_CHART_URL_FILE"] = url_path
                env["STOCKHELPER_CHART_NO_AUTO_OPEN"] = "1"
                proc = subprocess.Popen(argv, cwd=str(project_root), env=env, stdout=console_out, stderr=console_err)
                chart_url = ""
                for _ in range(80):
                    try:
                        chart_url = Path(url_path).read_text(encoding="utf-8").strip()
                    except Exception:
                        chart_url = ""
                    if chart_url:
                        break
                    if proc.poll() is not None:
                        break
                    time.sleep(0.1)
                if chart_url:
                    # The report page opens a tab synchronously on the user click and
                    # navigates it to this URL from the JSON response. Do not open a
                    # second server-side browser tab here; duplicate chart tabs can
                    # unload one another and trigger the chart shutdown handler.
                    print(f"[report] chart ui url: {chart_url} pid={proc.pid}", file=console_out, flush=True)
                    return 0, {"ok": True, "url": chart_url, "pid": proc.pid}
                rc = proc.poll()
                if rc is None:
                    rc = proc.wait(timeout=5)
                print(f"[report] chart command exited before UI url, exit={rc}", file=console_out, flush=True)
                return int(rc or 1), {"ok": False, "error": f"chart command exited before UI url (exit {rc})"}
            finally:
                try:
                    Path(url_path).unlink(missing_ok=True)
                except Exception:
                    pass

        # Non-chart commands are rare here; keep them synchronous and status-backed.
        rc = subprocess.call(argv, cwd=str(project_root), env=env, stdout=console_out, stderr=console_err)
        print(f"[report] chart command exit: {rc}", file=console_out, flush=True)
        return rc, {"ok": rc == 0, "exit": rc}

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
                    rc, payload = _run_chart_command(command)
                    self.send_response(200 if rc == 0 else 500); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(json.dumps(payload).encode("utf-8"))
                except Exception as exc:
                    self.send_response(500); self.end_headers(); self.wfile.write(str(exc).encode("utf-8"))
                return
            super().do_GET()

        def do_POST(self):
            parsed = urlparse(self.path)
            if parsed.path == "/attach-console":
                try:
                    ln = int(self.headers.get("content-length", "0") or "0")
                    raw = self.rfile.read(ln).decode("utf-8") if ln > 0 else "{}"
                    payload = json.loads(raw or "{}")
                    ok = _set_console_targets(str(payload.get("stdout", "")), str(payload.get("stderr", "")))
                    self.send_response(200 if ok else 500); self.end_headers(); self.wfile.write(json.dumps({"ok": ok}).encode("utf-8"))
                except Exception as exc:
                    self.send_response(500); self.end_headers(); self.wfile.write(str(exc).encode("utf-8"))
                return
            if parsed.path == "/run-command":
                qs = parse_qs(parsed.query)
                command = (qs.get("command", [""])[0] or "").strip()
                if not command:
                    self.send_response(400); self.end_headers(); self.wfile.write(b"missing command"); return
                try:
                    rc, payload = _run_chart_command(command)
                    self.send_response(200 if rc == 0 else 500); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(json.dumps(payload).encode("utf-8"))
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
