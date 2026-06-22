from __future__ import annotations

import base64
import html
import json
import os
import re
import uuid
import webbrowser
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
JOURNAL_DIR = PROJECT_ROOT / "data" / "journal"
JOURNAL_PATH = JOURNAL_DIR / "transactions.json"
SCREENSHOT_DIR = JOURNAL_DIR / "screenshots"
HTML_PATH = JOURNAL_DIR / "transactions.html"


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_symbol(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", (value or "instrument").strip()).strip("_")
    return safe or "instrument"


def load_entries() -> list[dict[str, Any]]:
    try:
        data = json.loads(JOURNAL_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except FileNotFoundError:
        return []
    except Exception:
        return []


def _write_entries(entries: list[dict[str, Any]]) -> None:
    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    tmp = JOURNAL_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(JOURNAL_PATH)


def save_entry(payload: dict[str, Any]) -> dict[str, Any]:
    entry = dict(payload or {})
    entry.setdefault("id", uuid.uuid4().hex)
    entry.setdefault("created_at", _now())
    entry.setdefault("status", "open")
    entry.setdefault("outcome", "pending")
    entry.setdefault("review_notes", "")
    screenshot = str(entry.pop("screenshot", "") or "")
    if screenshot.startswith("data:image/png;base64,"):
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        path = SCREENSHOT_DIR / f"{entry['created_at'][:10]}_{_safe_symbol(str(entry.get('symbol') or entry.get('instrument') or 'chart'))}_{entry['id'][:8]}.png"
        path.write_bytes(base64.b64decode(screenshot.split(",", 1)[1]))
        entry["screenshot_path"] = str(path.relative_to(PROJECT_ROOT))
    entries = load_entries()
    entries.append(entry)
    _write_entries(entries)
    write_html(entries)
    return entry


def close_entry(entry_id: str, outcome: str, notes: str = "", exit_price: str = "", screenshot: str = "") -> dict[str, Any] | None:
    entries = load_entries()
    found = None
    for entry in entries:
        if str(entry.get("id")) == str(entry_id):
            entry["status"] = "closed"
            entry["outcome"] = outcome or entry.get("outcome") or "closed"
            entry["closed_at"] = _now()
            entry["review_notes"] = notes
            if exit_price:
                entry["exit_price"] = exit_price
            if screenshot.startswith("data:image/png;base64,"):
                SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
                path = SCREENSHOT_DIR / f"{entry['closed_at'][:10]}_{_safe_symbol(str(entry.get('symbol') or 'chart'))}_{entry['id'][:8]}_close.png"
                path.write_bytes(base64.b64decode(screenshot.split(",", 1)[1]))
                entry["close_screenshot_path"] = str(path.relative_to(PROJECT_ROOT))
            found = entry
            break
    if found is not None:
        _write_entries(entries)
        write_html(entries)
    return found


def _row(entry: dict[str, Any]) -> str:
    def e(v: Any) -> str:
        return html.escape(str(v or ""))
    shot = e(entry.get("screenshot_path"))
    shot_html = f"<a href='../../{shot}' target='_blank'>screenshot</a>" if shot else ""
    close_shot = e(entry.get("close_screenshot_path"))
    close_html = f"<a href='../../{close_shot}' target='_blank'>close shot</a>" if close_shot else ""
    review = ""
    if str(entry.get("status") or "open") == "open":
        eid = e(entry.get("id"))
        review = (
            f"<div class='review noprint' data-id='{eid}'>"
            "<select class='outcome'><option value='won'>Won</option><option value='lost'>Lost / stop loss</option><option value='closed'>Closed</option></select>"
            "<input class='exit-price' placeholder='exit/profit price'>"
            "<textarea class='notes' rows='3' placeholder='Why / stop loss profitable place / lessons'></textarea>"
            "<pre class='preview'></pre><button type='button' onclick='closeJournalEntry(this)'>Save review</button></div>"
        )
    return "".join([
        "<tr>",
        f"<td>{e(entry.get('created_at'))}</td><td><b>{e(entry.get('symbol') or entry.get('instrument'))}</b></td>",
        f"<td>{e(entry.get('technique'))}</td><td>{e(entry.get('direction'))}</td><td>{e(entry.get('amount'))}</td>",
        f"<td>{e(entry.get('entry'))}</td><td>{e(entry.get('stop_loss'))}</td><td>{e(entry.get('take_profit'))}</td>",
        f"<td>{e(entry.get('status'))}</td><td>{e(entry.get('outcome'))}</td><td>{e(entry.get('pattern'))}</td>",
        f"<td>{e(entry.get('touches'))}</td><td><pre>{e(entry.get('notes'))}</pre><pre>{e(entry.get('review_notes'))}</pre></td>",
        f"<td>{shot_html} {close_html} {review}</td>",
        "</tr>",
    ])


def html_document(entries: list[dict[str, Any]] | None = None) -> str:
    entries = entries if entries is not None else load_entries()
    rows = "\n".join(_row(e) for e in entries)
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>StockHelper Transaction Journal</title>
<style>body{{font-family:Inter,Arial;margin:0 auto;max-width:1400px;padding:18px;background:#f8fafc}}table{{width:100%;border-collapse:collapse;background:white}}th,td{{border:1px solid #e2e8f0;padding:7px;vertical-align:top}}th{{background:#e0f2fe;position:sticky;top:0}}pre{{white-space:pre-wrap;margin:0}}.btn{{display:inline-block;padding:7px 10px;border:1px solid #cbd5e1;border-radius:8px;background:white;color:#0f172a;text-decoration:none}}@media print{{.noprint{{display:none}}body{{max-width:none}}}}</style></head><body>
<h1>StockHelper Transaction Journal</h1><p>Generated: {html.escape(_now())}</p><p class='noprint'><button class='btn' onclick='window.print()'>Download PDF</button></p>
<table><thead><tr><th>Date</th><th>Instrument</th><th>Technique</th><th>Dir</th><th>Amount</th><th>Entry</th><th>Stop loss</th><th>Take profit</th><th>Status</th><th>Outcome</th><th>Pattern</th><th>Touches</th><th>Notes</th><th>Screens</th></tr></thead><tbody>{rows}</tbody></table>
<script>
function closeJournalEntry(btn){{
  const box=btn.closest('.review'); if(!box) return;
  const payload={{id:box.dataset.id,outcome:box.querySelector('.outcome').value,exit_price:box.querySelector('.exit-price').value,notes:box.querySelector('.notes').value}};
  const preview=box.querySelector('.preview'); if(preview) preview.textContent=payload.outcome+' @ '+payload.exit_price+'\n'+payload.notes;
  fetch('/journal-close',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(payload)}}).then(r=>r.json()).then(d=>{{btn.textContent=d.ok?'Saved':'Failed';}}).catch(()=>{{btn.textContent='Failed';}});
}}

</script></body></html>"""


def write_html(entries: list[dict[str, Any]] | None = None) -> Path:
    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    HTML_PATH.write_text(html_document(entries), encoding="utf-8")
    return HTML_PATH


def open_html() -> Path:
    path = write_html()
    webbrowser.open(path.resolve().as_uri())
    return path
