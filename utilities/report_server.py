#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import webbrowser
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    project_root = Path(args.project_root).resolve()

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
            if parsed.path == "/run-command":
                qs = parse_qs(parsed.query)
                command = (qs.get("command", [""])[0] or "").strip()
                if not command:
                    self.send_response(400); self.end_headers(); self.wfile.write(b"missing command"); return
                try:
                    subprocess.Popen(command, shell=True, cwd=str(project_root))
                    self.send_response(200); self.end_headers(); self.wfile.write(b"ok")
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
                    subprocess.Popen(command, shell=True, cwd=str(project_root))
                    self.send_response(200); self.end_headers(); self.wfile.write(b"ok")
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
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
