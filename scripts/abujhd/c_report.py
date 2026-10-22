# scripts/abujhd/c_report.py
"""Step C: whiteboard report. One statement row per line with its evidence; sections for everything a human must fix."""
import argparse, html, sys, pathlib
from datetime import datetime
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import common
from common import load_json

CSS = """
:root{--bg:#fff;--fg:#111;--mute:#667;--line:#ddd;--chip:#eef;--ok:#1f8a4c;--warn:#b26a00;--bad:#c0392b;--rev:#5b4ac9}
@media(prefers-color-scheme:dark){:root{--bg:#121417;--fg:#e8e8e8;--mute:#9aa;--line:#2a2f36;--chip:#1e2430}}
body{margin:0;padding:16px;font:14px/1.45 system-ui,sans-serif;background:var(--bg);color:var(--fg)}
h1{font-size:22px;margin:0 0 4px}h2{font-size:16px;margin:28px 0 8px}
.tie{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px;margin:12px 0}
.card{border:1px solid var(--line);border-radius:10px;padding:10px 12px}.card b{font-size:18px}.card small{color:var(--mute)}
table{border-collapse:collapse;width:100%}th,td{border-top:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top;font-size:13px}
th{color:var(--mute);font-weight:600}.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.chip{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11px;font-weight:600;background:var(--chip)}
.MATCHED{color:var(--ok)}.TIED{color:var(--ok)}.LINKED{color:var(--ok)}.MISSING_RECEIPT,.ORPHAN,.UNEXPLAINED{color:var(--bad)}.AMOUNT_MISMATCH{color:var(--warn)}.REVIEW{color:var(--rev)}
.thumb{height:64px;border:1px solid var(--line);border-radius:4px;cursor:zoom-in;margin-right:4px}
.orange{background:rgba(255,140,0,.18);padding:0 4px;border-radius:3px;font-size:11px}
#ov{position:fixed;inset:0;background:rgba(0,0,0,.8);display:none;align-items:flex-start;justify-content:center;overflow:auto;padding:20px;z-index:9}
#ov .wrap{position:relative}#ov img{max-width:90vw}#ov .box{position:absolute;border:3px solid #ff3b3b;box-shadow:0 0 0 9999px rgba(0,0,0,.35)}
.mute{color:var(--mute)}.mono{font-family:ui-monospace,monospace;font-size:12px}
"""
JS = """
const ov=document.getElementById('ov');ov.onclick=()=>ov.style.display='none';document.addEventListener('keydown',e=>{if(e.key==='Escape')ov.style.display='none'});
document.querySelectorAll('.thumb').forEach(t=>t.onclick=e=>{e.stopPropagation();
 const [x0,y0,x1,y1]=t.dataset.box.split(',').map(Number);const img=ov.querySelector('img');img.src=t.dataset.src;
 img.onload=()=>{const b=ov.querySelector('.box');b.style.left=(x0/1000*img.width)+'px';b.style.top=(y0/1000*img.height)+'px';b.style.width=((x1-x0)/1000*img.width)+'px';b.style.height=((y1-y0)/1000*img.height)+'px';b.scrollIntoView({block:'center'})};
 ov.style.display='flex'});
"""

def chip(s): return f'<span class="chip {esc(s)}">{esc(s)}</span>'
def money(x): return f"{x:,.2f}" if isinstance(x, (int, float)) else ""
def esc(s): return "" if s is None else html.escape(str(s))

def cthumb(c, src, label):
    """A clickable crop for one citation; the overlay opens data-src and outlines data-box (1000-space)."""
    if not c or not c.get("crop") or not c.get("box"): return ""
    return f'<img class="thumb" src="{esc(c["crop"])}" data-src="{esc(src)}" data-box="{esc(",".join(map(str, c["box"])))}" alt="{esc(label)}" title="{esc(label)}">'

def evidence(stmt, rcpts, ledger):
    """Three labelled citations: statement strip, receipt crops, ledger cell. `stmt` and `rcpts` are lists of citations from b_match, `ledger` one citation or None."""
    st = "".join(cthumb(c, "pages/statement-200.png", f'Stmt {c["ref"]}') for c in stmt or [])
    rc = "".join(cthumb(c, f'pages/page-{int(c["page"]):02d}.png', f'Rcpt {c["group_id"]} p{c["page"]}') for c in rcpts or [])
    lg = f'{esc(ledger["sheet"])}!{esc(ledger["cell"])} · {esc(ledger["code"])} · {money(ledger["amount"])} · {esc(ledger["relation"])}' if ledger else "—"
    return f'<div><b>Stmt</b> {st or "none"}</div><div><b>Rcpt</b> {rc or "none"}</div><div><b>Ledger</b> <span class=mono>{lg}</span></div>'

def rowev(r):
    c = r["citations"]; return evidence([c["statement"]], c["receipts"], c["ledger"])

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--data", default="data/abujhd"); a = ap.parse_args(); common.set_data(a.data)
    m = load_json(common.DATA / "matches.json")
    rows, receipts, t = m["rows"], m["receipts"], m["tieout"]
    title = f'ABUJHD petty cash — {datetime.strptime(common.config()["month"], "%Y-%m").strftime("%B %Y")}'
    H = [f"<!doctype html><meta charset=utf-8><title>{title}</title><style>{CSS}</style><body>",
         f"<h1>{title}</h1><div class=mute>Statement rows are the key. Every line cites three sources: its statement row, its receipt crop and its ledger cell (click a thumbnail to see it on the page).</div>"]
    H.append("<h2>Tie-out</h2><div class=tie>")
    for label, k in (("Card loads vs ledger top-ups", "loads_vs_topups"), ("ATM vs ledger cash withdrawals", "atm_vs_withdrawals"), ("Purchases + ATM vs ledger roll-up", "purchases_vs_rollup")):
        v = t[k]; H.append(f'<div class=card><small>{label}</small><br><b>{money(v["statement"])}</b> statement<br>{money(v["ledger"])} ledger<br><span class="{"MISSING_RECEIPT" if v["diff"] else "MATCHED"}">diff {money(v["diff"])}</span></div>')
    s = m["summary"]["rows"]; H.append('<div class=card><small>Statement rows</small><br>' + "<br>".join(f'{chip(k)} {n}' for k, n in sorted(s.items())) + "</div>")
    s = m["summary"]["receipts"]; H.append('<div class=card><small>Receipts (groups)</small><br>' + "<br>".join(f'{chip(k)} {n}' for k, n in sorted(s.items())) + "</div>")
    H.append('<div class=card><small>Orange highlight vs status</small><br>' + "<br>".join(f'<span class=mono>{esc(k)}</span> {n}' for k, n in sorted(m["orange_vs_status"].items())) + "</div></div>")

    H.append("<h2>Statement</h2><table><tr><th>Status</th><th>Date</th><th class=num>Amount</th><th>Merchant</th><th>Evidence</th><th>Ref / reason</th></tr>")
    for r in sorted(rows, key=lambda r: (r["date"], r["time"])):
        H.append(f'<tr><td>{chip(r["status"])}</td><td class=mono>{esc(r["date"])} {esc(r["time"][:5])}{" <span class=orange>orange</span>" if r["orange"] else ""}</td><td class=num>{money(r["amount"])}</td>'
                 f'<td>{esc(r["merchant"][:48])}<br><span class=mute>{esc(r["kind"])}</span></td><td>{rowev(r)}</td><td class=mono>{esc(r["ref"])}<br><span class=mute>{esc(r["reason"])}</span></td></tr>')
    H.append("</table>")

    def section(title, heads, items, render):
        if not items: return
        H.append(f"<h2>{title} <span class=mute>({len(items)})</span></h2><table><tr>" + "".join(f"<th>{h}</th>" for h in heads) + "</tr>" + "".join(render(i) for i in items) + "</table>")
    rbyref = {r["ref"]: r for r in rows}
    lby = {l["code"]: l for l in m["ledger"]}
    atm_n = sum(1 for r in rows if r["kind"] == "atm"); pr = t["purchases_vs_rollup"]
    def cand(ref, sc):
        r = rbyref.get(ref)
        return f'<span class=mono>{esc(ref)}</span>' + (f' · {esc(r["date"])} · {money(r["amount"])} · {esc(r["merchant"][:40])}' if r else "") + f' · score {esc(sc)}'
    def ledger_row(kv):
        code, text = kv[0].split("|", 1); l = lby.get(code, {})
        amt = l.get("debit") or l.get("credit")
        chk = (f'Roll-up differs from card purchases + ATM by {money(pr["diff"])} — check the {atm_n} ATM withdrawals ({money(t["atm_vs_withdrawals"]["statement"])}) and the MISSING/REVIEW rows above'
               if (l.get("credit") or 0) > 1000 else f'No statement row ties to this {money(amt)} line (amount/date). Check the bank side or the posting.')
        return f'<tr><td class=mono>{esc(code)}</td><td class=mono>{esc(l.get("date"))}</td><td class=num>{money(l.get("debit"))}</td><td class=num>{money(l.get("credit"))}</td><td>{esc(text)}</td><td class=mute>{esc(chk)}</td></tr>'
    def review_ev(g):   # the candidates' statement strips, the group's own receipt crops, the ledger cell of the first candidate
        cs = [rbyref[ref]["citations"] for ref, _ in g["review"] if ref in rbyref]
        return evidence([c["statement"] for c in cs], g["citations"]["receipt"], cs[0]["ledger"] if cs else None)
    section("Missing receipts — find or request the document", ["Date", "Amount", "Merchant", "Ref", "Evidence", "What to check"], [r for r in rows if r["status"] == "MISSING_RECEIPT"],
            lambda r: f'<tr><td class=mono>{esc(r["date"])}</td><td class=num>{money(r["amount"])}</td><td>{esc(r["merchant"])}</td><td class=mono>{esc(r["ref"])}</td><td>{rowev(r)}</td><td class=mute>What to check: a receipt dated {esc(r["date"])}±1 for {money(r["amount"])} SAR at this merchant; if paid by card, the POS slip shows the amount.</td></tr>')
    section("Orphan receipts — document with no card transaction", ["Evidence", "Page / group", "Amounts", "Merchant", "What to check"], [g for g in receipts if g["status"] == "ORPHAN"],
            lambda g: f'<tr><td>{evidence(None, g["citations"]["receipt"], None)}</td><td class=mono>p{esc(g["page"])} {esc(g["id"])}</td><td class=num>{", ".join(money(v) for v in sorted({a["value"] for a in g["amounts"]})[:4])}</td><td>{esc((g.get("fields") or {}).get("merchant") or (g["merchant_candidates"] or [""])[0])}</td><td class=mute>What to check: cash purchase (not on the card), wrong total read, or belongs to another month. {esc(g.get("notes") or "")}</td></tr>')
    section("Amount mismatch", ["Date", "Amount", "Evidence", "Ref / reason", "What to check"], [r for r in rows if r["status"] == "AMOUNT_MISMATCH"],
            lambda r: f'<tr><td class=mono>{esc(r["date"])}</td><td class=num>{money(r["amount"])}</td><td>{rowev(r)}</td><td class=mono>{esc(r["ref"])}<br><span class=mute>{esc(r["reason"])}</span></td><td class=mute>Statement and receipt totals differ — check tips, VAT, or a partial card payment.</td></tr>')
    section("Review — pick the right link", ["Evidence", "Page / group", "Candidate statement rows", "What to check"], [g for g in receipts if g["status"] == "REVIEW"],
            lambda g: f'<tr><td>{review_ev(g)}</td><td class=mono>p{esc(g["page"])} {esc(g["id"])}</td><td>' + ("<br>".join(cand(ref, sc) for ref, sc in g["review"]) or '<span class=mute>candidates taken by other receipts</span>') + f'</td><td class=mute>{esc(g["reason"])} — set overrides.json links["{esc(g["id"])}"].</td></tr>')
    section("Statement rows not tied to the ledger (ATM/loads)", ["Date", "Amount", "Kind", "Ref", "Evidence", "What to check"], [r for r in rows if r["status"] == "UNEXPLAINED"],
            lambda r: f'<tr><td class=mono>{esc(r["date"])}</td><td class=num>{money(r["amount"])}</td><td>{esc(r["kind"])}</td><td class=mono>{esc(r["ref"])}</td><td>{rowev(r)}</td><td class=mute>What to check: no ledger cash-withdrawal/top-up line matches; confirm how ATM cash is booked.</td></tr>')
    section("Ledger lines not explained by the statement", ["Code", "Date", "Debit", "Credit", "Text", "What to check"], [(k, v) for k, v in t["ledger_status"].items() if v == "UNEXPLAINED"], ledger_row)
    H.append('<div id=ov><div class=wrap><img><div class=box></div></div></div>' + f"<script>{JS}</script>")
    (common.DATA / "report.html").write_text("\n".join(H), encoding="utf-8")
    print("wrote", common.DATA / "report.html")

if __name__ == "__main__":
    main()
