from __future__ import annotations

import base64
import html
import json
import re
import uuid
import webbrowser
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
JOURNAL_DIR = PROJECT_ROOT / "data" / "journal"
JOURNAL_PATH = JOURNAL_DIR / "transactions.json"
SCREENSHOT_DIR = JOURNAL_DIR / "screenshots"
HTML_PATH = JOURNAL_DIR / "transactions.html"


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _clean_date(value: Any) -> str:
    raw = str(value or "")
    if not raw:
        return ""
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except Exception:
        return raw[:16].replace("T", " ")


def _entry_year(entry: dict[str, Any]) -> str:
    return (_clean_date(entry.get("created_at"))[:4] or "unknown")


def _safe_symbol(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", (value or "instrument").strip()).strip("_")
    return safe or "instrument"


def _num(value: Any) -> float | None:
    text = str(value or "").replace(",", ".")
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except Exception:
        return None


def _estimate_pl(entry: dict[str, Any]) -> float | None:
    entry_price = _num(entry.get("entry"))
    exit_price = _num(entry.get("exit_price"))
    amount = _num(entry.get("amount"))
    if entry_price in (None, 0) or exit_price is None or amount is None:
        return None
    qty = amount / entry_price
    direction = str(entry.get("direction") or "long").lower()
    delta = (entry_price - exit_price) if direction == "short" else (exit_price - entry_price)
    return round(qty * delta, 2)


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


def close_entry(entry_id: str, outcome: str, notes: str = "", exit_price: str = "", screenshot: str = "", exit_reason: str = "", stop_loss_moves: str = "") -> dict[str, Any] | None:
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
            if exit_reason:
                entry["exit_reason"] = exit_reason
            if stop_loss_moves:
                entry["stop_loss_moves"] = stop_loss_moves
            estimated = _estimate_pl(entry)
            if estimated is not None:
                entry["estimated_pl"] = estimated
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


def update_entry(entry_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    entries = load_entries()
    found = None
    allowed = {"amount", "amount_currency", "entry", "exit_price", "reason", "reason_label", "touches", "notes", "review_notes", "outcome", "exit_reason", "stop_loss_moves"}
    for entry in entries:
        if str(entry.get("id")) == str(entry_id):
            for key, value in (updates or {}).items():
                if key in allowed:
                    entry[key] = value
            estimated = _estimate_pl(entry)
            if estimated is not None:
                entry["estimated_pl"] = estimated
            found = entry
            break
    if found is not None:
        _write_entries(entries)
        write_html(entries)
    return found


def delete_entry(entry_id: str) -> bool:
    entries = load_entries()
    kept = [entry for entry in entries if str(entry.get("id")) != str(entry_id)]
    if len(kept) == len(entries):
        return False
    _write_entries(kept)
    write_html(kept)
    return True


def _thumb(path_text: str) -> str:
    if not path_text:
        return ""
    safe = html.escape(path_text)
    return f"<a href='../../{safe}' target='_blank'><img class='thumb' src='../../{safe}' alt='screenshot'></a>"


def _row(entry: dict[str, Any]) -> str:
    def e(v: Any) -> str:
        return html.escape(str(v or ""))
    review = ""
    if str(entry.get("status") or "open") == "open":
        eid = e(entry.get("id"))
        review = (
            f"<div class='review noprint' data-id='{eid}'>"
            "<select class='outcome'><option value='profit'>Profit</option><option value='loss'>Loss</option></select>"
            "<input class='exit-price' placeholder='sold price / close price'>"
            "<select class='exit-reason'><option value='manual'>manually</option><option value='stop_loss'>stop loss</option></select>"
            "<input class='stop-loss-moves' placeholder='stop loss moves count'>"
            "<textarea class='notes' rows='3' placeholder='Review notes'></textarea>"
            "<pre class='preview'></pre><button type='button' onclick='closeJournalEntry(this)'>Save review</button></div>"
        )
    estimated = entry.get("estimated_pl")
    if estimated in (None, ""):
        estimated = _estimate_pl(entry)
    reason = entry.get("reason_label") or entry.get("reason") or entry.get("pattern")
    eid = e(entry.get("id"))
    edit = (
        f"<div class='edit noprint' data-id='{eid}'>"
        f"<input class='edit-amount' placeholder='amount' value='{e(entry.get('amount'))}'>"
        f"<input class='edit-entry' placeholder='entry' value='{e(entry.get('entry'))}'>"
        f"<input class='edit-reason' placeholder='reason' value='{e(reason)}'>"
        f"<input class='edit-touches' placeholder='touches' value='{e(entry.get('touches'))}'>"
        f"<textarea class='edit-notes' rows='2' placeholder='notes'>{e(entry.get('notes'))}</textarea>"
        "<button type='button' onclick='updateJournalEntry(this)'>Update</button>"
        "<button type='button' onclick='deleteJournalEntry(this)'>Delete</button></div>"
    )
    return "".join([
        f"<tr data-year='{e(_entry_year(entry))}'>",
        f"<td>{e(_clean_date(entry.get('created_at')))}</td><td><b>{e(entry.get('symbol') or entry.get('instrument'))}</b></td>",
        f"<td>{e(entry.get('technique'))}</td><td>{e(entry.get('direction'))}</td><td>{e(str(entry.get('amount') or '') + (' ' + str(entry.get('amount_currency')) if entry.get('amount_currency') else ''))}</td>",
        f"<td>{e(entry.get('entry'))}</td><td>{e(entry.get('exit_price'))}</td><td>{e(estimated)}</td>",
        f"<td>{e(entry.get('stop_loss'))}</td><td>{e(entry.get('take_profit'))}</td><td>{e(entry.get('status'))}</td><td>{e(entry.get('outcome'))}</td>",
        f"<td>{e(reason)}</td><td>{e(entry.get('touches'))}</td><td>{e(entry.get('exit_reason'))}</td><td>{e(entry.get('stop_loss_moves'))}</td>",
        f"<td><pre>{e(entry.get('notes'))}</pre><pre>{e(entry.get('review_notes'))}</pre></td>",
        f"<td>{_thumb(str(entry.get('screenshot_path') or ''))}{_thumb(str(entry.get('close_screenshot_path') or ''))}{review}{edit}</td>",
        "</tr>",
    ])


def html_document(entries: list[dict[str, Any]] | None = None) -> str:
    entries = entries if entries is not None else load_entries()
    years = sorted({_entry_year(e) for e in entries}, reverse=True)
    options = "".join(f"<option value='{html.escape(y)}'>{html.escape(y)}</option>" for y in years)
    ordered = sorted(entries, key=lambda e: str(e.get("created_at") or ""), reverse=True)
    row_parts = []
    last_year = None
    for entry in ordered:
        year = _entry_year(entry)
        if year != last_year:
            row_parts.append(f"<tr class='year-row' data-year='{html.escape(year)}'><th colspan='18'>Year {html.escape(year)}</th></tr>")
            last_year = year
        row_parts.append(_row(entry))
    rows = "\n".join(row_parts)
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>StockHelper Transaction Journal</title>
<style>body{{font-family:Inter,Arial;margin:0 auto;max-width:1500px;padding:18px;background:#f8fafc}}table{{width:100%;border-collapse:collapse;background:white}}th,td{{border:1px solid #e2e8f0;padding:7px;vertical-align:top}}th{{background:#e0f2fe;position:sticky;top:0}}pre{{white-space:pre-wrap;margin:0}}input,select,textarea{{width:100%;margin:3px 0}}.btn{{display:inline-block;padding:7px 10px;border:1px solid #cbd5e1;border-radius:8px;background:white;color:#0f172a;text-decoration:none}}.thumb{{width:180px;max-height:120px;object-fit:contain;display:block;margin:3px 0;border:1px solid #cbd5e1;border-radius:6px;background:#0f172a}}.toolbar{{display:flex;gap:10px;align-items:center;margin:10px 0}}@media print{{.noprint{{display:none}}body{{max-width:none}}.thumb{{width:140px}}}}</style></head><body>
<h1>StockHelper Transaction Journal</h1><p>Generated: {html.escape(_clean_date(_now()))}</p><div class='toolbar noprint'><label>Year <select id='year-filter'><option value=''>All years</option>{options}</select></label><button class='btn' onclick='window.print()'>Download PDF</button></div>
<table><thead><tr><th>Date</th><th>Instrument</th><th>Technique</th><th>Dir</th><th>Amount</th><th>Buy/Entry</th><th>Sold/Close</th><th>Estimated P/L</th><th>Stop loss</th><th>Take profit</th><th>Status</th><th>Outcome</th><th>Reason</th><th>Touches</th><th>Exit reason</th><th>SL moves</th><th>Notes</th><th>Screens</th></tr></thead><tbody>{rows}</tbody></table>
<script>
function applyYearFilter(){{const y=document.getElementById('year-filter').value;document.querySelectorAll('tbody tr[data-year]').forEach(r=>r.style.display=(!y||r.dataset.year===y)?'':'none');}}
document.getElementById('year-filter')?.addEventListener('change',applyYearFilter);
function updateJournalEntry(btn){{
  const box=btn.closest('.edit'); if(!box) return;
  const payload={{id:box.dataset.id,amount:box.querySelector('.edit-amount').value,entry:box.querySelector('.edit-entry').value,reason_label:box.querySelector('.edit-reason').value,touches:box.querySelector('.edit-touches').value,notes:box.querySelector('.edit-notes').value}};
  fetch('/journal-update',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(payload)}}).then(r=>r.json()).then(d=>{{btn.textContent=d.ok?'Updated':'Failed';}}).catch(()=>{{btn.textContent='Failed';}});
}}
function deleteJournalEntry(btn){{
  const box=btn.closest('.edit'); if(!box || !confirm('Delete this journal entry?')) return;
  fetch('/journal-delete',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{id:box.dataset.id}})}}).then(r=>r.json()).then(d=>{{if(d.ok){{box.closest('tr').remove();}}else{{btn.textContent='Failed';}}}}).catch(()=>{{btn.textContent='Failed';}});
}}
function closeJournalEntry(btn){{
  const box=btn.closest('.review'); if(!box) return;
  const payload={{id:box.dataset.id,outcome:box.querySelector('.outcome').value,exit_price:box.querySelector('.exit-price').value,exit_reason:box.querySelector('.exit-reason').value,stop_loss_moves:box.querySelector('.stop-loss-moves').value,notes:box.querySelector('.notes').value}};
  const preview=box.querySelector('.preview'); if(preview) preview.textContent=payload.outcome+' @ '+payload.exit_price+'\\nreason: '+payload.exit_reason+'\\nSL moves: '+payload.stop_loss_moves+'\\n'+payload.notes;
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
