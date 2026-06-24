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


def _selected(value: Any, expected: str) -> str:
    return " selected" if str(value or "").lower() == expected else ""


def _row(entry: dict[str, Any], number: int = 1) -> str:
    def e(v: Any) -> str:
        return html.escape(str(v or ""))

    eid = e(entry.get("id"))
    status = str(entry.get("status") or "open").lower()
    outcome = str(entry.get("outcome") or ("pending" if status == "open" else "closed")).lower()
    ended = status == "closed" or outcome in {"profit", "loss"}
    estimated = entry.get("estimated_pl")
    if estimated in (None, ""):
        estimated = _estimate_pl(entry)
    reason = entry.get("reason_label") or entry.get("reason") or entry.get("pattern")
    amount = str(entry.get("amount") or "") + (" " + str(entry.get("amount_currency")) if entry.get("amount_currency") else "")
    thumb_html = _thumb(str(entry.get("screenshot_path") or "")) or "<div class='screen-empty'>No screenshot</div>"
    close_thumb = _thumb(str(entry.get("close_screenshot_path") or ""))
    status_text = ("completed · " + outcome) if ended else (outcome or status)
    outcome_dot = "🟢" if outcome == "profit" else ("🔴" if outcome == "loss" else "🟡")
    review_inner = (
        "<div class='section-title'>Status</div>"
        f"<select class='outcome'><option value='profit'{_selected(outcome, 'profit')}>🟢 Profit</option><option value='loss'{_selected(outcome, 'loss')}>🔴 Loss</option></select>"
        f"<div class='section-title'>Price (sold / close price)</div><input class='exit-price' placeholder='close price' value='{e(entry.get('exit_price'))}'>"
        f"<div class='review-grid'><div><div class='section-title'>Mode</div><select class='exit-reason'><option value='manual'{_selected(entry.get('exit_reason'), 'manual')}>👤 Manually</option><option value='stop_loss'{_selected(entry.get('exit_reason'), 'stop_loss')}>🛑 Stop loss</option></select></div>"
        f"<div><div class='section-title'>Stop loss moves count</div><input class='stop-loss-moves' placeholder='0' value='{e(entry.get('stop_loss_moves'))}'></div></div>"
        f"<div class='section-title'>Review notes</div><textarea class='notes' rows='4' placeholder='Review notes'>{e(entry.get('review_notes'))}</textarea>"
        f"<div class='kv'><span>Position Value</span><b>{e(amount)}</b></div><div class='kv'><span>Close Price</span><b class='js-close-price'>{e(entry.get('exit_price') or '--')}</b></div><div class='kv'><span>Setup</span><b>{e(reason)}</b></div>"
        "<pre class='preview'></pre><button class='btn btn-outline' type='button' onclick='closeJournalEntry(this)'>💾 Save Review</button>"
    )
    if ended:
        review = f"<details class='panel review noprint collapsed-review' data-id='{eid}'><summary>✎ Trade / Review (completed)</summary>{review_inner}</details>"
    else:
        review = f"<section class='panel review noprint' data-id='{eid}'><div class='panel-head'>✎ Trade / Review</div>{review_inner}</section>"
    edit = (
        f"<details class='panel edit noprint' data-id='{eid}'>"
        "<summary>⚙ Modify entry <span>(optional)</span></summary>"
        f"<div class='edit-grid'><label>Amount<input class='edit-amount' placeholder='amount' value='{e(entry.get('amount'))}'></label>"
        f"<label>Entry price<input class='edit-entry' placeholder='entry' value='{e(entry.get('entry'))}'></label>"
        f"<label>Reason<input class='edit-reason' placeholder='reason' value='{e(reason)}'></label>"
        f"<label>Touches<input class='edit-touches' placeholder='touches' value='{e(entry.get('touches'))}'></label></div>"
        f"<textarea class='edit-notes' rows='3' placeholder='notes'>{e(entry.get('notes'))}</textarea>"
        "<div class='actions'><button class='btn btn-primary' type='button' onclick='updateJournalEntry(this)'>↻ Update</button>"
        "<button class='btn btn-danger' type='button' onclick='deleteJournalEntry(this)'>🗑 Delete</button></div></details>"
    )
    return "".join([
        f"<article class='journal-card {e(status)} {e(outcome)}' data-year='{e(_entry_year(entry))}'>",
        f"<header><div class='badge'>#{number}</div><div><h2>{e(entry.get('symbol') or entry.get('instrument'))}</h2><p>{e(_clean_date(entry.get('created_at')))} · {e(entry.get('technique'))} · {e(entry.get('direction'))}</p></div><span class='status {e(status)} {e(outcome)}'>{outcome_dot} {e(status_text)}</span></header>",
        "<div class='card-grid'><section class='panel screens'><div class='panel-head'>▧ Chart</div>", thumb_html, close_thumb, "</section>",
        f"<section class='panel facts {'completed-summary' if ended else ''}'><div class='panel-head'>✅ Trade Summary <span>{e(status_text)}</span></div>",
        f"<div class='kv'><span>Position Value</span><b>{e(amount)}</b></div>",
        f"<div class='kv'><span>Buy / Entry</span><b>{e(entry.get('entry'))}</b></div>",
        f"<div class='kv'><span>Sold / Close</span><b>{e(entry.get('exit_price') or '--')}</b></div>",
        f"<div class='kv'><span>Estimated P/L</span><b>{e(estimated or '--')}</b></div>",
        f"<div class='kv'><span>Stop loss</span><b>{e(entry.get('stop_loss'))}</b></div>",
        f"<div class='kv'><span>Reason</span><b>{e(reason)}</b></div>",
        f"<div class='kv'><span>Touches</span><b>{e(entry.get('touches'))}</b></div>",
        f"<div class='kv'><span>Exit reason</span><b>{e(entry.get('exit_reason'))}</b></div>",
        "</section>", review,
        f"<section class='panel notes'><div class='panel-head'>📄 Auto Context / Notes</div><pre>{e(entry.get('notes'))}</pre><pre>{e(entry.get('review_notes'))}</pre></section>",
        edit,
        "</div></article>",
    ])


def html_fragment(entries: list[dict[str, Any]] | None = None) -> str:
    entries = entries if entries is not None else load_entries()
    ordered = sorted(entries, key=lambda e: str(e.get("created_at") or ""), reverse=False)
    card_parts = []
    last_year = None
    for idx, entry in enumerate(ordered, start=1):
        year = _entry_year(entry)
        if year != last_year:
            card_parts.append(f"<h2 class='year-row' data-year='{html.escape(year)}'>Year {html.escape(year)}</h2>")
            last_year = year
        card_parts.append(_row(entry, idx))
    return "\n".join(card_parts) or "<div class='empty'>No journal entries yet. Open ./run --journal-html for the live journal view.</div>"


def html_document(entries: list[dict[str, Any]] | None = None) -> str:
    entries = entries if entries is not None else load_entries()
    years = sorted({_entry_year(e) for e in entries}, reverse=True)
    options = "".join(f"<option value='{html.escape(y)}'>{html.escape(y)}</option>" for y in years)
    cards = html_fragment(entries)
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>StockHelper Transaction Journal</title>
<style>
:root{{--bg:#f7fbff;--card:#fff;--ink:#10213d;--muted:#64748b;--line:#cbdff5;--blue:#1476f2;--danger:#ef233c}}
*{{box-sizing:border-box}}body{{font-family:Inter,system-ui,-apple-system,Segoe UI,Arial;margin:0;background:radial-gradient(circle at 20% 0,#eef7ff,#fff 42%,#f8fafc);color:var(--ink);padding:22px}}.shell{{max-width:1180px;margin:0 auto}}h1{{margin:0;font-size:32px}}.top{{display:flex;justify-content:space-between;gap:16px;align-items:center;margin-bottom:18px}}.toolbar{{display:flex;gap:10px;align-items:center;flex-wrap:wrap}}select,input,textarea{{width:100%;border:1px solid #b8c9df;border-radius:10px;padding:10px 12px;background:white;color:#1e2f4d;font-size:15px}}.toolbar select{{width:auto;min-width:150px}}.btn{{border:1px solid #bfdbfe;background:white;color:#0f5fd7;border-radius:10px;padding:10px 15px;font-weight:800;cursor:pointer}}.btn-primary{{background:#0876f8;color:white;border-color:#0876f8;box-shadow:0 12px 24px rgba(8,118,248,.22)}}.btn-danger{{color:#ef233c;border-color:#ef233c;background:#fff}}.btn-outline{{background:#f8fbff}}.year-row{{font-size:18px;margin:24px 0 10px;color:#47617f;text-transform:uppercase;letter-spacing:.06em}}.journal-card{{background:rgba(255,255,255,.92);border:1px solid var(--line);border-radius:18px;box-shadow:0 18px 50px rgba(31,64,104,.12);margin:0 0 18px;overflow:hidden}}.journal-card>header{{display:flex;align-items:center;gap:14px;padding:18px 20px;background:linear-gradient(180deg,#f0f7ff,#fff);border-bottom:1px solid var(--line)}}.badge{{width:46px;height:46px;border-radius:14px;display:grid;place-items:center;background:linear-gradient(135deg,#1684ff,#0b4eb8);color:white;font-weight:900;box-shadow:0 12px 28px rgba(20,118,242,.28)}}header h2{{margin:0;font-size:24px}}header p{{margin:3px 0 0;color:var(--muted);font-weight:700}}.status{{margin-left:auto;padding:8px 12px;border-radius:999px;background:#e0f2fe;color:#0369a1;font-weight:900;text-transform:capitalize}}.status.closed{{background:#dcfce7;color:#15803d}}.card-grid{{display:grid;grid-template-columns:360px repeat(2,minmax(240px,1fr));gap:14px;padding:16px}}.panel{{border:1px solid var(--line);border-radius:14px;background:rgba(255,255,255,.82);padding:14px}}.screens{{grid-row:span 2}}.panel-head{{font-size:19px;font-weight:900;margin-bottom:12px}}.thumb{{width:100%;max-height:235px;object-fit:contain;display:block;margin:0 0 10px;border:1px solid #b8c9df;border-radius:10px;background:#0f172a}}.screen-empty{{height:160px;border-radius:10px;background:#eaf2fb;display:grid;place-items:center;color:#64748b;font-weight:800}}.kv{{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 0;border-bottom:1px solid #dbe7f4}}.kv:last-child{{border-bottom:0}}.kv span,.section-title{{color:#64748b;text-transform:uppercase;letter-spacing:.055em;font-size:12px;font-weight:900}}.kv b{{text-align:right;color:#16284a}}.review,.edit{{display:flex;flex-direction:column;gap:8px}}.actions{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:6px}}pre{{white-space:pre-wrap;margin:8px 0 0;color:#334155;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}}.notes{{grid-column:span 2}}.empty{{padding:32px;border:1px dashed var(--line);border-radius:16px;color:#64748b;background:white}}.toast{{position:fixed;right:18px;bottom:18px;padding:12px 16px;border-radius:12px;background:#10213d;color:white;box-shadow:0 16px 40px rgba(0,0,0,.25);display:none}}@media(max-width:980px){{.card-grid{{grid-template-columns:1fr}}.screens,.notes{{grid-column:auto;grid-row:auto}}.top{{display:block}}}}
/* Dark glass journal UI override */
:root{{--bg:#050b16;--card:rgba(15,23,42,.76);--ink:#f8fafc;--muted:#93a4bd;--line:rgba(148,163,184,.28);--blue:#2f8cff;--danger:#fb7185}}
body{{max-width:none;background:radial-gradient(circle at 18% 0,rgba(59,130,246,.16),transparent 32%),radial-gradient(circle at 88% 18%,rgba(168,85,247,.13),transparent 28%),#050b16;color:#f8fafc;padding:26px}}.shell{{max-width:1380px}}.top{{margin-bottom:24px}}h1{{color:#f8fafc;text-shadow:0 4px 18px rgba(0,0,0,.35)}}.top p{{color:#93a4bd}}.toolbar select,.toolbar .btn{{background:rgba(15,23,42,.72);border-color:rgba(96,165,250,.38);color:#dbeafe}}.year-row{{color:#93c5fd}}.journal-card{{background:transparent;border:0;box-shadow:none;margin-bottom:28px}}.journal-card>header{{background:transparent;border:0;padding:0 6px 18px 6px}}.badge{{background:linear-gradient(135deg,#0759d1,#38bdf8);box-shadow:0 0 32px rgba(56,189,248,.45);border-radius:12px}}header h2{{color:#f8fafc;text-transform:uppercase}}header p{{color:#a8b5c9}}.status{{background:linear-gradient(135deg,#7c5b19,#fde68a);color:#fff7ed;box-shadow:0 0 30px rgba(250,204,21,.35)}}.status.closed{{background:linear-gradient(135deg,#166534,#4ade80);color:#dcfce7}}.card-grid{{grid-template-columns:minmax(420px,1.35fr) minmax(250px,.55fr) minmax(320px,.7fr);gap:14px;padding:0}}.panel{{background:linear-gradient(135deg,rgba(30,41,59,.80),rgba(15,23,42,.76));border:1px solid rgba(148,163,184,.28);box-shadow:inset 0 1px 0 rgba(255,255,255,.08),0 18px 50px rgba(0,0,0,.28);backdrop-filter:blur(10px);border-radius:14px}}.screens{{grid-row:span 2}}.panel-head,.section-title{{color:#e0f2fe;text-shadow:0 2px 10px rgba(0,0,0,.3)}}.thumb{{max-height:470px;border-color:rgba(96,165,250,.45);border-radius:13px;background:#08111f;box-shadow:inset 0 0 80px rgba(96,165,250,.08)}}.screen-empty{{background:rgba(15,23,42,.82);color:#93a4bd}}.kv{{border-color:rgba(148,163,184,.22)}}.kv span{{color:#cbd5e1}}.kv b{{color:#f8fafc}}pre{{color:#dbeafe}}select,input,textarea{{background:rgba(15,23,42,.70);border-color:rgba(148,163,184,.34);color:#f8fafc}}select:focus,input:focus,textarea:focus{{outline:none;border-color:#60a5fa;box-shadow:0 0 0 3px rgba(96,165,250,.18)}}.btn{{background:rgba(15,23,42,.65);border-color:rgba(226,232,240,.72);color:#f8fafc}}.btn-primary,.review .btn-outline{{background:linear-gradient(135deg,#0673ff,#38bdf8);border-color:#38bdf8;color:white;box-shadow:0 0 28px rgba(56,189,248,.42)}}.btn-danger{{background:rgba(127,29,29,.35);border-color:#ef4444;color:#fecaca}}.review,.edit{{gap:10px}}.notes{{grid-column:1 / -1;display:flex;gap:14px;flex-wrap:wrap}}.notes pre{{min-width:220px;padding:12px;border:1px solid rgba(148,163,184,.20);border-radius:12px;background:rgba(15,23,42,.46)}}.toast{{background:#071426;border:1px solid rgba(96,165,250,.35)}}@media(max-width:1100px){{.card-grid{{grid-template-columns:1fr}}.screens,.notes{{grid-column:auto;grid-row:auto}}}}@media print{{.noprint,.toolbar{{display:none!important}}body{{background:white;padding:0;color:#0f172a}}.journal-card{{break-inside:avoid;box-shadow:none}}.thumb{{max-height:160px}}}}

.journal-card>header .status{{margin-left:auto;display:inline-flex;align-items:center;gap:10px;padding:12px 18px;border-radius:14px;text-transform:uppercase;letter-spacing:.08em}}.journal-card.closed.profit>header .status,.journal-card.profit>header .status{{background:rgba(22,101,52,.40);border:1px solid #4ade80;color:#86efac;box-shadow:0 0 30px rgba(34,197,94,.24)}}.journal-card.closed.loss>header .status,.journal-card.loss>header .status{{background:rgba(127,29,29,.42);border:1px solid #fb7185;color:#fecaca;box-shadow:0 0 30px rgba(248,113,113,.22)}}.card-grid{{grid-template-columns:minmax(320px,1fr) minmax(320px,1fr) minmax(320px,1fr);align-items:stretch}}.screens{{grid-column:1 / -1;grid-row:auto}}.screens .thumb{{width:100%;max-height:420px;object-fit:contain}}.facts.completed-summary{{border-color:#22c55e;box-shadow:0 0 0 1px rgba(34,197,94,.35),0 18px 50px rgba(34,197,94,.12),inset 0 1px 0 rgba(255,255,255,.08)}}.facts .panel-head{{display:flex;justify-content:space-between;align-items:center;color:#86efac}}.facts .panel-head span{{font-size:12px;padding:6px 10px;border-radius:999px;background:rgba(34,197,94,.14);border:1px solid rgba(34,197,94,.35);text-transform:uppercase;letter-spacing:.08em}}.review-grid,.edit-grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}details.panel{{padding:0;overflow:hidden}}details.panel>summary{{list-style:none;cursor:pointer;padding:18px 20px;color:#dbeafe;font-weight:900;text-transform:uppercase;letter-spacing:.08em}}details.panel>summary::-webkit-details-marker{{display:none}}details.panel>summary::after{{content:'⌄';float:right;color:#cbd5e1;font-size:20px}}details.panel[open]>summary::after{{content:'⌃'}}details.panel.review:not([open]){{min-height:64px}}details.panel.review[open],details.panel.edit[open]{{padding:0 14px 14px}}details.panel.review[open]>summary,details.panel.edit[open]>summary{{margin:0 -14px 12px}}.collapsed-review{{opacity:.92}}.edit{{grid-column:1 / -1}}.edit textarea{{margin-top:12px}}.notes{{grid-column:1 / -1;display:block}}.notes pre{{width:100%;min-height:120px;margin-top:10px}}@media(max-width:1100px){{.card-grid{{grid-template-columns:1fr}}.screens,.notes,.edit{{grid-column:auto}}}}

/* final layout width/screenshot fixes */
body{{padding:18px 20px}}.shell{{width:calc(100vw - 40px);max-width:none;margin:0 auto}}.card-grid{{grid-template-columns:minmax(360px,.95fr) minmax(360px,1fr) minmax(360px,.95fr);gap:16px}}.screens{{grid-column:1 / -1}}.screens .thumb{{width:100%;max-height:640px;min-height:360px;object-fit:contain}}.notes{{grid-column:auto;display:block}}.notes pre{{min-height:250px}}.edit{{grid-column:1 / -1}}.journal-card{{margin-bottom:32px}}@media(max-width:1280px){{.card-grid{{grid-template-columns:1fr}}.screens,.notes,.edit{{grid-column:auto}}.screens .thumb{{min-height:220px}}}}
</style></head><body><div class='shell'>
<div class='top'><div><h1>StockHelper Transaction Journal</h1><p>Generated: {html.escape(_clean_date(_now()))}</p></div><div class='toolbar noprint'><label>Year <select id='year-filter'><option value=''>All years</option>{options}</select></label><button class='btn' onclick='window.print()'>📄 Download PDF</button></div></div>
{cards}</div><div id='toast' class='toast'></div>
<script>
function toast(msg){{const t=document.getElementById('toast');t.textContent=msg;t.style.display='block';setTimeout(()=>t.style.display='none',2600);}}
function api(path,payload){{if(location.protocol==='file:'){{toast('Open journal through ./run --journal-html so update/delete can reach the local server.');return Promise.resolve({{ok:false}});}}return fetch(path,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(payload)}}).then(async r=>{{let d={{}};try{{d=await r.json();}}catch(e){{}}return {{...d,ok:r.ok&&d.ok!==false}};}});}}
function applyYearFilter(){{const y=document.getElementById('year-filter').value;document.querySelectorAll('[data-year]').forEach(r=>r.style.display=(!y||r.dataset.year===y)?'':'none');}}
document.getElementById('year-filter')?.addEventListener('change',applyYearFilter);
document.addEventListener('input',e=>{{if(e.target.classList.contains('exit-price')){{const box=e.target.closest('.review');const out=box?.querySelector('.js-close-price');if(out)out.textContent=e.target.value||'--';}}}});
function updateJournalEntry(btn){{const box=btn.closest('.edit');if(!box)return;const payload={{id:box.dataset.id,amount:box.querySelector('.edit-amount').value,entry:box.querySelector('.edit-entry').value,reason_label:box.querySelector('.edit-reason').value,touches:box.querySelector('.edit-touches').value,notes:box.querySelector('.edit-notes').value}};api('/journal-update',payload).then(d=>toast(d.ok?'Updated':'Update failed'));}}
function deleteJournalEntry(btn){{const box=btn.closest('.edit');if(!box||!confirm('Delete this journal entry?'))return;api('/journal-delete',{{id:box.dataset.id}}).then(d=>{{if(d.ok){{box.closest('.journal-card').remove();toast('Deleted');}}else toast('Delete failed');}});}}
function closeJournalEntry(btn){{const box=btn.closest('.review');if(!box)return;const payload={{id:box.dataset.id,outcome:box.querySelector('.outcome').value,exit_price:box.querySelector('.exit-price').value,exit_reason:box.querySelector('.exit-reason').value,stop_loss_moves:box.querySelector('.stop-loss-moves').value,notes:box.querySelector('.notes').value}};const preview=box.querySelector('.preview');if(preview)preview.textContent=payload.outcome+' @ '+payload.exit_price+'\nreason: '+payload.exit_reason+'\nSL moves: '+payload.stop_loss_moves+'\n'+payload.notes;api('/journal-close',payload).then(d=>toast(d.ok?'Review saved':'Review failed'));}}
</script></body></html>"""

def write_html(entries: list[dict[str, Any]] | None = None) -> Path:
    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    HTML_PATH.write_text(html_document(entries), encoding="utf-8")
    return HTML_PATH


def open_html() -> Path:
    path = write_html()
    webbrowser.open(path.resolve().as_uri())
    return path
