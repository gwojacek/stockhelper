#!/usr/bin/env python3
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import html
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import uuid
import threading
import time
import webbrowser
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import urlopen

REPORT_SERVER_PROTOCOL = "stockhelper-report-server-v13"


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

    def _durable_console_path(path: str) -> str:
        if not path:
            return ""
        try:
            target = os.readlink(path)
        except Exception:
            return path
        # `/proc/<launcher-pid>/fd/<n>` disappears when the short-lived report
        # opener exits. When it points at a real terminal, keep the terminal path
        # itself so chart-finish calculations can still print in PyCharm/terminal.
        if target.startswith("/dev/") and Path(target).exists():
            return target
        return path

    def _open_console_path(path: str, fallback):
        if not path:
            return fallback, None, ""
        resolved_path = _durable_console_path(path)
        try:
            handle = open(resolved_path, "a", buffering=1, encoding="utf-8", errors="replace")
            return handle, handle, resolved_path
        except Exception:
            return fallback, None, ""

    console_out, close_console_out = sys.stdout, None
    console_err, close_console_err = sys.stderr, None
    console_stdout_path = ""
    console_stderr_path = ""
    console_log_path = os.environ.get("STOCKHELPER_REPORT_CONSOLE_LOG", "")
    console_log = None
    chart_groups: dict[str, dict] = {}
    chart_group_lock = threading.Lock()
    if console_log_path:
        try:
            Path(console_log_path).parent.mkdir(parents=True, exist_ok=True)
            console_log = open(console_log_path, "a", buffering=1, encoding="utf-8", errors="replace")
        except Exception:
            console_log = None


    def _clean_group_text(value: object) -> str:
        text = str(value or "").strip()
        return text.encode("utf-8", "ignore").decode("utf-8", "ignore")

    def _set_console_targets(stdout_path: str = "", stderr_path: str = "") -> bool:
        nonlocal console_out, close_console_out, console_err, close_console_err, console_stdout_path, console_stderr_path
        new_out, new_close_out, resolved_stdout_path = _open_console_path(stdout_path, sys.stdout)
        new_err, new_close_err, resolved_stderr_path = _open_console_path(stderr_path, sys.stderr)
        if stdout_path and new_close_out is None:
            return False
        if stderr_path and new_close_err is None:
            if new_close_out is not None:
                new_close_out.close()
            return False
        old_close_out, old_close_err = close_console_out, close_console_err
        console_out, close_console_out = new_out, new_close_out
        console_err, close_console_err = new_err, new_close_err
        console_stdout_path = resolved_stdout_path if new_close_out is not None else ""
        console_stderr_path = resolved_stderr_path if new_close_err is not None else ""
        if old_close_out is not None:
            old_close_out.close()
        if old_close_err is not None and old_close_err is not old_close_out:
            old_close_err.close()
        return True

    def _console_target_is_alive(path: str) -> bool:
        if not path:
            return True
        # If we successfully opened `/proc/<pid>/fd/<n>`, we now own a duplicate
        # handle. It may remain writable after the short-lived opener process exits,
        # and `_safe_print` will drop it if an actual write fails.
        if re.match(r"^/proc/(\d+)/fd/\d+$", path):
            return True
        return Path(path).exists()

    def _drop_stale_console_targets() -> None:
        nonlocal console_out, close_console_out, console_err, close_console_err, console_stdout_path, console_stderr_path
        stale_out = console_stdout_path and not _console_target_is_alive(console_stdout_path)
        stale_err = console_stderr_path and not _console_target_is_alive(console_stderr_path)
        if stale_out:
            if close_console_out is not None:
                close_console_out.close()
            console_out, close_console_out, console_stdout_path = sys.stdout, None, ""
        if stale_err:
            if close_console_err is not None and close_console_err is not close_console_out:
                close_console_err.close()
            console_err, close_console_err, console_stderr_path = sys.stderr, None, ""

    def _safe_print(message: str, *, err: bool = False) -> None:
        nonlocal console_out, close_console_out, console_err, close_console_err, console_stdout_path, console_stderr_path
        _drop_stale_console_targets()
        if console_log is not None:
            try:
                print(message, file=console_log, flush=True)
            except Exception:
                pass
        stream = console_err if err else console_out
        try:
            print(message, file=stream, flush=True)
        except Exception:
            if err:
                if close_console_err is not None:
                    close_console_err.close()
                console_err, close_console_err, console_stderr_path = sys.stderr, None, ""
            else:
                if close_console_out is not None:
                    close_console_out.close()
                console_out, close_console_out, console_stdout_path = sys.stdout, None, ""

    def _forward_process_output(pipe, *, err: bool = False) -> None:
        try:
            for line in pipe:
                _safe_print(line.rstrip("\n"), err=err)
        except Exception as exc:
            _safe_print(f"[report] failed to forward process output: {exc}", err=True)
        finally:
            try:
                pipe.close()
            except Exception:
                pass

    def _start_process(argv: list[str], env: dict[str, str]) -> subprocess.Popen:
        proc = subprocess.Popen(
            argv,
            cwd=str(project_root),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        if proc.stdout is not None:
            threading.Thread(target=_forward_process_output, args=(proc.stdout,), daemon=True).start()
        if proc.stderr is not None:
            threading.Thread(target=_forward_process_output, args=(proc.stderr,), kwargs={"err": True}, daemon=True).start()
        return proc

    # Open the launcher console once while the parent `run` process is still
    # alive. If this server is reused by a later report open, /attach-console
    # refreshes these handles to that newer launcher terminal.
    _set_console_targets(
        os.environ.get("STOCKHELPER_REPORT_CONSOLE_STDOUT", ""),
        os.environ.get("STOCKHELPER_REPORT_CONSOLE_STDERR", ""),
    )

    def _is_report_chart_command(argv: list[str]) -> bool:
        return len(argv) >= 3 and Path(argv[1]).name == "run" and argv[2] in {"-c", "--chart"}

    def _run_chart_command(command: str, group_id: str = "") -> tuple[int, dict]:
        original_command = command
        command = _canonicalize_chart_command(command)
        argv = shlex.split(command)
        if len(argv) >= 2 and argv[0] in {"python", "python3"} and argv[1] == "run":
            argv = [sys.executable, str(project_root / "run"), *argv[2:]]
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["STOCKHELPER_REPORT_LAUNCHED_CHART"] = "1"
        if group_id:
            with chart_group_lock:
                group_data = chart_groups.get(group_id, {})
            group_items = group_data.get("items") or []
            if group_items:
                env["STOCKHELPER_CHART_GROUP_JSON"] = json.dumps(
                    {
                        "id": group_id,
                        "label": str(group_data.get("label") or "Quick charts from group btn"),
                        "items": group_items,
                        "current": original_command,
                        "reportServer": f"http://{args.host}:{args.port}",
                    },
                    ensure_ascii=False,
                )
        _safe_print(f"[report] running chart command: {' '.join(shlex.quote(a) for a in argv)}")

        if _is_report_chart_command(argv):
            fd, url_path = tempfile.mkstemp(prefix="stockhelper_chart_url_", suffix=".txt")
            os.close(fd)
            try:
                env["STOCKHELPER_CHART_URL_FILE"] = url_path
                env["STOCKHELPER_CHART_NO_AUTO_OPEN"] = "1"
                proc = _start_process(argv, env)
                chart_url = ""
                # Chart startup can take longer than a few seconds when the
                # command has to import scanner modules or refresh/load a local
                # symbol before the lightweight UI writes its URL. Keep the
                # report request alive long enough to receive that URL instead
                # of falling through to a short proc.wait timeout.
                for _ in range(300):
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
                    # Do not hand the browser a URL until the chart HTTP server is
                    # actually accepting requests. The chart process writes the URL
                    # as soon as it knows the port; this guard prevents a redirect
                    # race that can show ERR_EMPTY_RESPONSE in the report-opened tab.
                    chart_ready = False
                    for _ in range(30):
                        try:
                            with urlopen(chart_url, timeout=0.25) as resp:
                                chart_ready = 200 <= int(getattr(resp, "status", 200)) < 500
                        except Exception:
                            chart_ready = False
                        if chart_ready:
                            break
                        if proc.poll() is not None:
                            break
                        time.sleep(0.1)
                    if not chart_ready:
                        rc = proc.poll()
                        _safe_print(f"[report] chart ui url did not respond, exit={rc}")
                        return int(rc or 1), {"ok": False, "error": "chart UI URL did not respond", "url": chart_url, "pid": proc.pid}
                    _safe_print(f"[report] chart ui url: {chart_url} pid={proc.pid}")
                    return 0, {"ok": True, "url": chart_url, "pid": proc.pid}
                rc = proc.poll()
                if rc is None:
                    try:
                        rc = proc.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        _safe_print(f"[report] chart command still running before UI url, pid={proc.pid}")
                        return 1, {"ok": False, "error": "chart command is still starting and did not publish a UI URL yet", "pid": proc.pid}
                _safe_print(f"[report] chart command exited before UI url, exit={rc}")
                return int(rc or 1), {"ok": False, "error": f"chart command exited before UI url (exit {rc})"}
            finally:
                try:
                    Path(url_path).unlink(missing_ok=True)
                except Exception:
                    pass

        # Non-chart commands are rare here; keep them synchronous and status-backed.
        proc = _start_process(argv, env)
        rc = proc.wait()
        _safe_print(f"[report] chart command exit: {rc}")
        return rc, {"ok": rc == 0, "exit": rc}


    def _html_response(title: str, message: str, debug: dict | None = None, status: int = 500) -> bytes:
        debug = debug or {}
        rows = "\n".join(f"{html.escape(str(k))}: {html.escape(str(v))}" for k, v in debug.items())
        return f"""<!doctype html>
<html><head><meta charset=\"utf-8\"><title>{html.escape(title)}</title></head>
<body style=\"font-family:sans-serif;background:#0f172a;color:#e5e7eb;padding:24px\">
<h3>{html.escape(title)}</h3><p>{html.escape(message)}</p>
<h4>Debug</h4><pre style=\"white-space:pre-wrap;background:#111827;border:1px solid #334155;border-radius:8px;padding:12px\">{rows}</pre>
</body></html>""".encode("utf-8")

    def _send_html(handler, title: str, message: str, debug: dict | None = None, status: int = 500) -> None:
        body = _html_response(title, message, debug, status)
        handler.send_response(status)
        handler.send_header("Content-Type", "text/html; charset=utf-8")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)

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
                    self.send_response(400); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(json.dumps({"ok": False, "error": "missing command"}).encode("utf-8")); return
                try:
                    rc, payload = _run_chart_command(command)
                    self.send_response(200 if rc == 0 else 500); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(json.dumps(payload).encode("utf-8"))
                except Exception as exc:
                    payload = {"ok": False, "error": str(exc), "command": command}
                    _safe_print(f"[report] chart command failed: {exc}", err=True)
                    self.send_response(500); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(json.dumps(payload).encode("utf-8"))
                return
            if parsed.path == "/open-chart":
                qs = parse_qs(parsed.query)
                command = (qs.get("command", [""])[0] or "").strip()
                debug = {"command": command, "path": self.path}
                if not command:
                    _send_html(self, "StockHelper chart failed", "missing command", debug, 400); return
                try:
                    group_id = (qs.get("group", [""])[0] or "").strip()
                    rc, payload = _run_chart_command(command, group_id)
                    debug.update(payload or {})
                    if rc == 0 and payload.get("url"):
                        self.send_response(303)
                        self.send_header("Location", str(payload["url"]))
                        self.end_headers()
                        return
                    _send_html(self, "StockHelper chart failed", str(payload.get("error") or f"exit {rc}"), debug, 500); return
                except Exception as exc:
                    debug["error"] = str(exc)
                    _safe_print(f"[report] chart command failed: {exc}", err=True)
                    _send_html(self, "StockHelper chart failed", str(exc), debug, 500); return
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
                    self.send_response(400); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(json.dumps({"ok": False, "error": "missing command"}).encode("utf-8")); return
                try:
                    rc, payload = _run_chart_command(command)
                    self.send_response(200 if rc == 0 else 500); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(json.dumps(payload).encode("utf-8"))
                except Exception as exc:
                    payload = {"ok": False, "error": str(exc), "command": command}
                    _safe_print(f"[report] chart command failed: {exc}", err=True)
                    self.send_response(500); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(json.dumps(payload).encode("utf-8"))
                return
            if parsed.path == "/chart-group":
                try:
                    ln = int(self.headers.get("content-length", "0") or "0")
                    raw = self.rfile.read(ln).decode("utf-8") if ln > 0 else "{}"
                    payload = json.loads(raw or "{}")
                    group_label = _clean_group_text(payload.get("label") or "Quick charts from group btn")
                    raw_items = payload.get("items") or []
                    items = []
                    for item in raw_items:
                        if not isinstance(item, dict):
                            continue
                        command = _clean_group_text(item.get("command") or "")
                        if not command:
                            continue
                        label = _clean_group_text(item.get("label") or command)
                        section = _clean_group_text(item.get("section") or "")
                        items.append({"command": command, "label": label, "section": section})
                    if not items:
                        self.send_response(400); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(json.dumps({"ok": False, "error": "missing commands"}).encode("utf-8")); return
                    group_id = uuid.uuid4().hex
                    with chart_group_lock:
                        chart_groups[group_id] = {"label": group_label, "items": items}
                    first_command = items[0]["command"]
                    first_url = f"/open-chart?command={quote(first_command, safe="")}&group={quote(group_id, safe="")}"
                    self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(json.dumps({"ok": True, "group": group_id, "url": first_url}).encode("utf-8"))
                except Exception as exc:
                    self.send_response(500); self.end_headers(); self.wfile.write(str(exc).encode("utf-8"))
                return
            if parsed.path == "/open-charts":
                try:
                    ln = int(self.headers.get("content-length", "0") or "0")
                    raw = self.rfile.read(ln).decode("utf-8") if ln > 0 else "{}"
                    payload = json.loads(raw or "{}")
                    commands = [c.strip() for c in payload.get("commands") or [] if isinstance(c, str) and c.strip()]
                    open_in_browser = bool(payload.get("open", True))
                    group_id = str(payload.get("group") or "").strip()

                    def _run_grouped_chart(command: str) -> dict:
                        try:
                            rc, result = _run_chart_command(command, group_id)
                            return {"command": command, "ok": rc == 0, **(result or {})}
                        except Exception as exc:
                            _safe_print(f"[report] grouped chart command failed: {exc}", err=True)
                            return {"command": command, "ok": False, "error": str(exc)}

                    results = [None] * len(commands)
                    if commands:
                        workers = min(len(commands), 8)
                        with ThreadPoolExecutor(max_workers=workers) as executor:
                            futures = {executor.submit(_run_grouped_chart, command): idx for idx, command in enumerate(commands)}
                            for future in as_completed(futures):
                                results[futures[future]] = future.result()
                    results = [r for r in results if r is not None]
                    opened = 0
                    if open_in_browser:
                        for result in results:
                            if result.get("ok") and result.get("url"):
                                webbrowser.open_new_tab(str(result["url"]))
                                opened += 1
                    urls = [str(r.get("url", "")) if r.get("ok") and r.get("url") else "" for r in results]
                    self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(json.dumps({"opened": opened, "urls": urls, "results": results}).encode("utf-8"))
                except Exception as exc:
                    self.send_response(500); self.end_headers(); self.wfile.write(str(exc).encode("utf-8"))
                return
            if parsed.path == "/journal-close":
                try:
                    ln = int(self.headers.get("content-length", "0") or "0")
                    raw = self.rfile.read(ln).decode("utf-8") if ln > 0 else "{}"
                    payload = json.loads(raw or "{}")
                    from journal import close_entry
                    entry = close_entry(str(payload.get("id") or ""), str(payload.get("outcome") or "closed"), str(payload.get("notes") or ""), str(payload.get("exit_price") or ""), str(payload.get("screenshot") or ""))
                    self.send_response(200 if entry else 404); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(json.dumps({"ok": bool(entry)}).encode("utf-8"))
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
        if console_log is not None:
            console_log.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
