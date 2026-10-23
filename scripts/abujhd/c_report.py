# scripts/abujhd/c_report.py
"""Step C: the whiteboard report. One statement row per line with three citations; analytics on top; sections for everything a person must settle.

Visual system follows providus.io (tokens measured 2026-10-23): light #F2F2F2 page, white cards, ink #151515,
blue #2F6DB2, deep-navy header #02091F, Archivo display + Geist body, 12px radius, pill chips. Status colours are
reserved and always paired with a glyph and a word. Charts are inline SVG built here, no libraries.
"""
import argparse, html, sys, pathlib, re
from collections import defaultdict
from datetime import datetime
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import common
from common import load_json

FONTS = '<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Geist+Mono:wght@400;500&display=swap" rel="stylesheet">'

CSS = """
:root{--page:#F5F5F5;--card:#FFFFFF;--ink:#151515;--mute:#71717A;--line:#E4E4E7;--blue:#554BC5;--blue-h:#4239A9;--navy:#4239A9;--deep:#554BC5;
 --ok:#0A7F3F;--bad:#B42318;--rev:#554BC5;--warn:#A15C00;--neutral:#71717A;--tint:12%;--shadow:0 1px 2px rgba(0,0,0,.04)}
@media(prefers-color-scheme:dark){:root{--page:hsl(247 18% 10%);--card:oklch(0.21 0.006 285.885);--ink:#F2F2F2;--mute:#A1A1AA;--line:rgba(255,255,255,.1);--blue:#7368E6;--blue-h:#9A92EF;--ok:#3DAA6A;--bad:#E06A5F;--rev:#9A92EF;--warn:#D39A3C;--neutral:#A1A1AA;--tint:18%;--shadow:none}}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);font:14px/1.5 "DM Sans",ui-sans-serif,system-ui,sans-serif}
.hero{background:linear-gradient(180deg,#554BC5,#4239A9);color:#fff;padding:40px 32px 32px;background-image:linear-gradient(rgba(255,255,255,.05) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.05) 1px,transparent 1px);background-size:48px 48px}
.hero .top{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;flex-wrap:wrap}
.hero h1{font:600 40px/1.1 "DM Sans",ui-sans-serif,system-ui,sans-serif;margin:0 0 12px;letter-spacing:-.01em}
.hero p{margin:12px 0 0;max-width:760px;color:rgba(255,255,255,.78)}
.lock{font:500 13px "DM Sans",sans-serif;color:rgba(255,255,255,.7);white-space:nowrap;padding-top:14px}
.lock b{color:#fff;font-weight:600;letter-spacing:-.01em}.lock i{display:inline-block;width:0;height:0;border-left:9px solid var(--blue-h);border-top:6px solid transparent;border-bottom:6px solid transparent;margin-left:2px;vertical-align:-1px;filter:drop-shadow(0 0 6px rgba(109,187,255,.6))}
.pills{display:flex;gap:8px;flex-wrap:wrap}.pill{border:1px solid rgba(255,255,255,.22);border-radius:999px;padding:3px 12px;font-size:12px;color:rgba(255,255,255,.85)}
main{padding:24px 32px 48px;max-width:1440px;margin:0 auto}
h2{font:600 22px/1.2 "DM Sans",ui-sans-serif,system-ui,sans-serif;margin:36px 0 12px;letter-spacing:-.01em}h2 small{font:400 13px "DM Sans",sans-serif;color:var(--mute);margin-left:8px}
.grid{display:grid;gap:16px}.g4{grid-template-columns:repeat(auto-fit,minmax(220px,1fr))}.g3{grid-template-columns:repeat(auto-fit,minmax(340px,1fr))}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px;box-shadow:var(--shadow)}
.tile .k{font-size:12px;color:var(--mute);font-weight:500;text-transform:uppercase;letter-spacing:.04em}.tile .v{font:600 32px/1.15 "DM Sans",sans-serif;margin:6px 0 2px;font-variant-numeric:tabular-nums}.tile .s{font-size:12px;color:var(--mute)}
.card h3{font:600 13px "DM Sans",sans-serif;margin:0 0 10px;color:var(--ink)}.card .note{font-size:12px;color:var(--mute);margin-top:8px}
svg text{font-family:"DM Sans",ui-sans-serif,system-ui,sans-serif}
.legend{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--mute);margin-top:10px}.legend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px;vertical-align:-1px}
details{margin-top:10px;font-size:12px}summary{cursor:pointer;color:var(--blue)}details table td,details table th{font-size:12px;padding:3px 6px}
.tbl{overflow:auto}table{border-collapse:collapse;width:100%}th,td{border-top:1px solid var(--line);padding:8px 10px;text-align:left;vertical-align:top;font-size:13px}
tr:first-child th{border-top:0}th{color:var(--mute);font-weight:500;font-size:12px}.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.chip{display:inline-flex;align-items:center;gap:5px;padding:2px 10px 2px 7px;border-radius:6px;font-size:11.5px;font-weight:600;white-space:nowrap;color:var(--c);background:color-mix(in srgb,var(--c) var(--tint),transparent)}
.chip b{font-weight:700}
.thumb{height:56px;border:1px solid var(--line);border-radius:6px;cursor:zoom-in;margin:2px 4px 2px 0;background:#fff}.strip{height:22px;max-width:260px;object-fit:cover;object-position:left}
.ev{min-width:300px}.ev div{font-size:12px;color:var(--mute);display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin:2px 0}.ev b{flex:0 0 66px;font-weight:500;color:var(--mute)}
.mark{background:color-mix(in srgb,var(--warn) 18%,transparent);color:var(--warn);padding:0 6px;border-radius:999px;font-size:11px;font-weight:600}
#ov{position:fixed;inset:0;background:rgba(2,9,31,.82);display:none;align-items:flex-start;justify-content:center;overflow:auto;padding:24px;z-index:9}
#ov .wrap{position:relative}#ov img{max-width:90vw;border-radius:8px}#ov .box{position:absolute;border:3px solid var(--blue-h);box-shadow:0 0 0 9999px rgba(2,9,31,.4);border-radius:3px}
.mute{color:var(--mute)}.mono{font-family:"Geist Mono",ui-monospace,monospace;font-size:12px}
"""
JS = """
const ov=document.getElementById('ov');ov.onclick=()=>ov.style.display='none';document.addEventListener('keydown',e=>{if(e.key==='Escape')ov.style.display='none'});
document.querySelectorAll('.thumb').forEach(t=>t.onclick=e=>{e.stopPropagation();
 const [x0,y0,x1,y1]=t.dataset.box.split(',').map(Number);const img=ov.querySelector('img');img.src=t.dataset.src;
 img.onload=()=>{const b=ov.querySelector('.box');b.style.left=(x0/1000*img.width)+'px';b.style.top=(y0/1000*img.height)+'px';b.style.width=((x1-x0)/1000*img.width)+'px';b.style.height=((y1-y0)/1000*img.height)+'px';b.scrollIntoView({block:'center'})};
 ov.style.display='flex'});
"""

# Status vocabulary: a word, a glyph and a reserved colour. Colour never carries meaning alone.
STATUS = {
    "MATCHED": ("Matched", "✓", "var(--ok)"), "TIED": ("Tied to ledger", "✓", "var(--ok)"), "LINKED": ("Linked", "✓", "var(--ok)"),
    "MISSING_RECEIPT": ("Missing receipt", "✕", "var(--bad)"), "ORPHAN": ("No card row", "✕", "var(--bad)"),
    "REVIEW": ("Needs a decision", "?", "var(--rev)"),
    "UNEXPLAINED": ("Not in ledger", "!", "var(--warn)"), "AMOUNT_MISMATCH": ("Amounts differ", "!", "var(--warn)"),
}
HEX = {"var(--ok)": "#0A7F3F", "var(--bad)": "#B42318", "var(--rev)": "#554BC5", "var(--warn)": "#A15C00", "var(--neutral)": "#8C8C8C"}

def esc(s): return "" if s is None else html.escape(str(s))
def money(x): return f"{x:,.2f}" if isinstance(x, (int, float)) else ""
def chip(s):
    word, glyph, col = STATUS.get(s, (s, "·", "var(--neutral)"))
    return f'<span class="chip" style="--c:{col}"><b>{glyph}</b>{esc(word)}</span>'

def cthumb(c, src, label, cls="thumb"):
    """A clickable crop for one citation; the overlay opens data-src and outlines data-box (1000-space)."""
    if not c or not c.get("crop") or not c.get("box"): return ""
    return f'<img class="{cls}" src="{esc(c["crop"])}" data-src="{esc(src)}" data-box="{esc(",".join(map(str, c["box"])))}" alt="{esc(label)}" title="{esc(label)}">'

def evidence(stmt, rcpts, ledger):
    """Three labelled citations: statement strip, receipt crops, ledger cell."""
    st = "".join(cthumb(c, "pages/statement-200.png", f'Statement row {c["ref"]}', "thumb strip") for c in stmt or [])
    rc = "".join(cthumb(c, f'pages/page-{int(c["page"]):02d}.png', f'Receipt {c["group_id"]}, page {c["page"]}') for c in rcpts or [])
    lg = f'{esc(ledger["sheet"])}!{esc(ledger["cell"])} · {esc(ledger["code"])} · {money(ledger["amount"])} · {esc(ledger["relation"])}' if ledger else "no ledger line"
    return f'<div class=ev><div><b>Statement</b> {st or "none"}</div><div><b>Receipt</b> {rc or "none"}</div><div><b>Ledger</b> <span class=mono>{lg}</span></div></div>'

def rowev(r):
    c = r["citations"]; return evidence([c["statement"]], c["receipts"], c["ledger"])

# ---------- charts (inline SVG, no libraries) ----------
def _mix(a, b, t):
    a = tuple(int(a[i:i+2], 16) for i in (1, 3, 5)); b = tuple(int(b[i:i+2], 16) for i in (1, 3, 5))
    return "#%02X%02X%02X" % tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))

def ramp(t):
    """Sequential blue, light to navy, for a 0..1 share."""
    return _mix("#D6E4F3", "#2F6DB2", t * 2) if t < .5 else _mix("#2F6DB2", "#033659", (t - .5) * 2)

def status_bars(purchases):
    order = ["MATCHED", "REVIEW", "MISSING_RECEIPT", "AMOUNT_MISMATCH"]
    cnt = {k: sum(1 for r in purchases if r["status"] == k) for k in order}
    amt = {k: sum(r["amount"] for r in purchases if r["status"] == k) for k in order}
    W = 600
    def bar(y, vals, total, fmt):
        x, out = 0, []
        for k in order:
            if not vals[k]: continue
            w = vals[k] / total * W
            out.append(f'<rect x="{x:.1f}" y="{y}" width="{max(w-2,1):.1f}" height="22" rx="3" fill="{HEX[STATUS[k][2]]}"><title>{STATUS[k][0]}: {fmt(vals[k])}</title></rect>')
            if w > 46: out.append(f'<text x="{x+8:.1f}" y="{y+15}" font-size="11" font-weight="600" fill="#fff">{fmt(vals[k])}</text>')
            x += w
        return "".join(out)
    svg = (f'<svg viewBox="0 0 {W} 78" width="100%" role="img" aria-label="Purchase rows by status, by count and by amount">'
           f'<text x="0" y="10" font-size="11" style="fill:var(--mute)">By count · {len(purchases)} rows</text>{bar(16, cnt, max(1, len(purchases)), lambda v: str(v))}'
           f'<text x="0" y="56" font-size="11" style="fill:var(--mute)">By amount · {money(sum(amt.values()))} SAR</text>{bar(62-6, amt, max(1, sum(amt.values())), money)}</svg>')
    legend = '<div class=legend>' + "".join(f'<span><i style="background:{HEX[STATUS[k][2]]}"></i>{STATUS[k][0]} · {cnt[k]} · {money(amt[k])}</span>' for k in order if cnt[k]) + '</div>'
    table = '<details><summary>Table</summary><table><tr><th>Status</th><th class=num>Rows</th><th class=num>SAR</th></tr>' + "".join(f'<tr><td>{STATUS[k][0]}</td><td class=num>{cnt[k]}</td><td class=num>{money(amt[k])}</td></tr>' for k in order if cnt[k]) + '</table></details>'
    return svg + legend + table

def waterfall(t):
    loads = t["loads_vs_topups"]["statement"]; purch = t["purchases_vs_rollup"]["purchases_only"]; atm = t["atm_vs_withdrawals"]["statement"]
    spend = t["purchases_vs_rollup"]["statement"]; roll = t["purchases_vs_rollup"]["ledger"]; gap = roll - spend
    steps = [("Card loads", 0, loads, "total"), ("Purchases", 0, purch, "up"), ("ATM cash", purch, atm, "up"),
             ("Card spend", 0, spend, "total"), ("Gap", min(spend, roll), abs(gap), "gap"), ("Ledger roll-up", 0, roll, "total")]
    top = max(loads, roll, spend) * 1.15; W, H, pad = 620, 220, 34; bw = (W - 20) / len(steps) - 18
    fill = {"total": "#8C8C8C", "up": "#2F6DB2", "gap": "#A15C00"}
    out = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Tie-out bridge from card loads to the ledger roll-up">']
    for i, (name, base, val, kind) in enumerate(steps):
        x = 10 + i * ((W - 20) / len(steps)); y1 = H - pad - (base + val) / top * (H - pad - 20); h = max(val / top * (H - pad - 20), 1)
        out.append(f'<rect x="{x:.1f}" y="{y1:.1f}" width="{bw:.1f}" height="{h:.1f}" rx="4" fill="{fill[kind]}"><title>{name}: {money(val)} SAR</title></rect>')
        out.append(f'<text x="{x+bw/2:.1f}" y="{y1-6:.1f}" font-size="11" font-weight="600" text-anchor="middle" style="fill:var(--ink)">{money(val)}</text>')
        out.append(f'<text x="{x+bw/2:.1f}" y="{H-pad+16}" font-size="11" text-anchor="middle" style="fill:var(--mute)">{name}</text>')
    out.append(f'<line x1="0" x2="{W}" y1="{H-pad}" y2="{H-pad}" stroke="#E0E0E0"/></svg>')
    legend = f'<div class=legend><span><i style="background:#2F6DB2"></i>card spend parts</span><span><i style="background:#A15C00"></i>unexplained gap · {money(gap)} SAR</span><span><i style="background:#8C8C8C"></i>totals</span></div>'
    table = '<details><summary>Table</summary><table><tr><th>Step</th><th class=num>SAR</th></tr>' + "".join(f'<tr><td>{n}</td><td class=num>{money(v)}</td></tr>' for n, _, v, _ in steps) + '</table></details>'
    return "".join(out) + legend + table

def merchant_key(m):
    words = [w for w in re.split(r"[^A-Za-z؀-ۿ]+", m) if w]
    return " ".join(words[:2]).title() if words else m[:20]

def merchants(purchases, top_n=10):
    by = defaultdict(lambda: [0.0, 0.0, 0])
    for r in purchases:
        k = merchant_key(r["merchant"]); by[k][0] += r["amount"]; by[k][2] += 1
        if r["status"] == "MATCHED": by[k][1] += r["amount"]
    items = sorted(by.items(), key=lambda kv: -kv[1][0])
    head, tail = items[:top_n], items[top_n:]
    if tail:
        head.append(("Other (%d merchants)" % len(tail), [sum(v[0] for _, v in tail), sum(v[1] for _, v in tail), sum(v[2] for _, v in tail)]))
    W, rowh = 620, 24; H = rowh * len(head) + 8; mx = max(v[0] for _, v in head) or 1; lab = 180
    out = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Top merchants by card spend, shaded by evidenced share">']
    for i, (name, (tot, ev, n)) in enumerate(head):
        share = ev / tot if tot else 0; y = i * rowh + 4; w = (W - lab - 90) * tot / mx
        out.append(f'<text x="{lab-8}" y="{y+15}" font-size="12" text-anchor="end" style="fill:var(--ink)">{esc(name[:26])}</text>')
        out.append(f'<rect x="{lab}" y="{y+3}" width="{max(w,2):.1f}" height="{rowh-8}" rx="4" fill="{ramp(share)}"><title>{esc(name)}: {money(tot)} SAR over {n} rows, {share:.0%} evidenced</title></rect>')
        out.append(f'<text x="{lab+w+6:.1f}" y="{y+15}" font-size="11" style="fill:var(--ink)" font-variant-numeric="tabular-nums">{money(tot)} <tspan fill="#8C8C8C">· {share:.0%}</tspan></text>')
    out.append('</svg>')
    legend = '<div class=legend><span>shade = share of the merchant\'s spend with a matched receipt:</span><span><i style="background:' + ramp(0) + '"></i>0%</span><span><i style="background:' + ramp(.5) + '"></i>50%</span><span><i style="background:' + ramp(1) + '"></i>100%</span></div>'
    table = '<details><summary>Table</summary><table><tr><th>Merchant</th><th class=num>Rows</th><th class=num>SAR</th><th class=num>Evidenced</th></tr>' + "".join(f'<tr><td>{esc(n)}</td><td class=num>{v[2]}</td><td class=num>{money(v[0])}</td><td class=num>{(v[1]/v[0] if v[0] else 0):.0%}</td></tr>' for n, v in head) + '</table></details>'
    return "".join(out) + legend + table

# ---------- page ----------
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--data", default="data/abujhd"); a = ap.parse_args(); common.set_data(a.data)
    m = load_json(common.DATA / "matches.json"); cfg = common.config()
    rows, receipts, t = m["rows"], m["receipts"], m["tieout"]
    month = datetime.strptime(cfg["month"], "%Y-%m").strftime("%B %Y")
    client = cfg.get("client", "ABUJHD")
    title = f"Petty cash · {month}"
    purchases = [r for r in rows if r["kind"] == "purchase"]
    pr = t["purchases_vs_rollup"]; spend = pr["statement"]; roll = pr["ledger"]; gap = roll - spend
    purch_amt = pr["purchases_only"]; matched_amt = sum(r["amount"] for r in purchases if r["status"] == "MATCHED")
    missing = [r for r in rows if r["status"] == "MISSING_RECEIPT"]

    H = [f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(client)} · {title}</title>{FONTS}<style>{CSS}</style></head><body>']
    H.append(f'''<header class=hero><div class=top><div><h1>{esc(title)}</h1><div class=pills><span class=pill>{esc(client)}</span><span class=pill>bank-card statement · receipts · ledger</span><span class=pill>built {datetime.now():%d %b %Y}</span></div></div>
<div class=lock>powered by <b>providus</b><i></i></div></div>
<p>Each card transaction on the statement is matched to its receipt and to its ledger line. Every row below cites all three sources; click a thumbnail to see the page it came from.</p></header><main>''')

    # hero tiles
    H.append('<div class="grid g4">'
             f'<div class="card tile"><div class=k>Card spend</div><div class=v>{money(spend)}</div><div class=s>SAR · {len(purchases)} purchases + {sum(1 for r in rows if r["kind"]=="atm")} ATM withdrawals</div></div>'
             f'<div class="card tile"><div class=k>Evidenced</div><div class=v>{(matched_amt/purch_amt if purch_amt else 0):.0%}</div><div class=s>{money(matched_amt)} of {money(purch_amt)} SAR has a matched receipt</div></div>'
             f'<div class="card tile"><div class=k>Open gap</div><div class=v>{money(gap)}</div><div class=s>ledger roll-up {money(roll)} minus card spend</div></div>'
             f'<div class="card tile"><div class=k>Receipts to find</div><div class=v>{len(missing)}</div><div class=s>{money(sum(r["amount"] for r in missing))} SAR without a receipt</div></div></div>')

    # analytics
    H.append('<h2>Where the month stands</h2><div class="grid g3">'
             f'<div class=card><h3>Purchases by status</h3>{status_bars(purchases)}</div>'
             f'<div class=card><h3>Card loads to ledger roll-up</h3>{waterfall(t)}<div class=note>Loads vs top-ups: {money(t["loads_vs_topups"]["statement"])} vs {money(t["loads_vs_topups"]["ledger"])} (diff {money(t["loads_vs_topups"]["diff"])}). ATM cash has no ledger withdrawal line.</div></div>'
             f'<div class=card><h3>Top merchants</h3>{merchants(purchases)}</div></div>')

    # orange cross-tab, compact
    ovs = m["orange_vs_status"]; cols = [s for s in ("MATCHED", "REVIEW", "MISSING_RECEIPT", "AMOUNT_MISMATCH") if any(k.endswith("|" + s) for k in ovs)]
    cell = lambda o, s: ovs.get(f"{o}|{s}", 0)
    H.append('<div class="card" style="margin-top:16px"><h3>Rows the client highlighted in orange on the statement</h3><table style="width:auto"><tr><th></th>' + "".join(f'<th>{chip(s)}</th>' for s in cols) + '<th class=num>Total</th></tr>'
             + "".join(f'<tr><td>{lab}</td>' + "".join(f'<td class=num>{cell(o, s)}</td>' for s in cols) + f'<td class=num>{sum(cell(o, s) for s in cols)}</td></tr>' for o, lab in (("orange", "Highlighted"), ("plain", "Not highlighted")))
             + '</table><div class=note>The highlight was only recorded, not interpreted. Most highlighted rows have a matched receipt; the highlighted rows without one are the first to chase.</div></div>')

    # statement table
    H.append(f'<h2>Statement<small>{len(rows)} rows, oldest first</small></h2><div class="card tbl"><table><tr><th>Status</th><th>Date</th><th class=num>SAR</th><th>Merchant</th><th>Evidence</th><th>Ref · note</th></tr>')
    for r in sorted(rows, key=lambda r: (r["date"], r["time"] or "")):
        H.append(f'<tr><td>{chip(r["status"])}</td><td class=mono>{esc(r["date"])} {esc((r["time"] or "")[:5])}{" <span class=mark>orange</span>" if r["orange"] else ""}</td><td class=num>{money(r["amount"])}</td>'
                 f'<td>{esc((r["merchant"] or "")[:48])}<br><span class=mute>{esc(r["kind"])}</span></td><td>{rowev(r)}</td><td class=mono>{esc(r["ref"])}<br><span class=mute>{esc(r["reason"])}</span></td></tr>')
    H.append("</table></div>")

    def section(title, heads, items, render):
        if not items: return
        H.append(f'<h2>{title}<small>{len(items)}</small></h2><div class="card tbl"><table><tr>' + "".join(f"<th>{h}</th>" for h in heads) + "</tr>" + "".join(render(i) for i in items) + "</table></div>")
    rbyref = {r["ref"]: r for r in rows}; lby = {l["code"]: l for l in m["ledger"]}
    atm_n = sum(1 for r in rows if r["kind"] == "atm")
    def cand(ref, sc):
        r = rbyref.get(ref)
        return f'<span class=mono>{esc(ref)}</span>' + (f' · {esc(r["date"])} · {money(r["amount"])} · {esc(r["merchant"][:40])}' if r else "") + f' · score {esc(sc)}'
    def ledger_row(kv):
        code, text = kv[0].split("|", 1); l = lby.get(code, {}); amt = l.get("debit") or l.get("credit")
        chk = (f'The roll-up is {money(gap)} SAR more than the card spend. Start with the {atm_n} ATM withdrawals ({money(t["atm_vs_withdrawals"]["statement"])} SAR), then the missing and undecided rows above.'
               if (l.get("credit") or 0) > 1000 else f'No card transaction matches this {money(amt)} SAR line by amount and date. Check how it was posted.')
        return f'<tr><td class=mono>{esc(code)}</td><td class=mono>{esc(l.get("date"))}</td><td class=num>{money(l.get("debit"))}</td><td class=num>{money(l.get("credit"))}</td><td>{esc(text)}</td><td class=mute>{esc(chk)}</td></tr>'
    def review_ev(g):
        cs = [rbyref[ref]["citations"] for ref, _ in g["review"] if ref in rbyref]
        return evidence([c["statement"] for c in cs], g["citations"]["receipt"], cs[0]["ledger"] if cs else None)
    section("Receipts to find", ["Date", "SAR", "Merchant", "Ref", "Evidence", "What to look for"], missing,
            lambda r: f'<tr><td class=mono>{esc(r["date"])}</td><td class=num>{money(r["amount"])}</td><td>{esc(r["merchant"])}</td><td class=mono>{esc(r["ref"])}</td><td>{rowev(r)}</td><td class=mute>A receipt from {esc(r["date"])} (give or take a day) for {money(r["amount"])} SAR at this merchant. If it was paid by card, the slip shows the same amount.</td></tr>')
    section("Receipts with no card transaction", ["Evidence", "Page · group", "Amounts", "Merchant", "What to look for"], [g for g in receipts if g["status"] == "ORPHAN"],
            lambda g: f'<tr><td>{evidence(None, g["citations"]["receipt"], None)}</td><td class=mono>p{esc(g["page"])} {esc(g["id"])}</td><td class=num>{", ".join(money(v) for v in sorted({a["value"] for a in g["amounts"]})[:4]) or "<span class=mute>no amount read</span>"}</td><td>{esc((g.get("fields") or {}).get("merchant") or (g["merchant_candidates"] or [""])[0])}</td><td class=mute>Paid in cash rather than by card, a misread total, or a receipt from another month. {esc(g.get("notes") or "")}</td></tr>')
    section("Amounts that differ", ["Date", "SAR", "Evidence", "Ref · note", "What to look for"], [r for r in rows if r["status"] == "AMOUNT_MISMATCH"],
            lambda r: f'<tr><td class=mono>{esc(r["date"])}</td><td class=num>{money(r["amount"])}</td><td>{rowev(r)}</td><td class=mono>{esc(r["ref"])}<br><span class=mute>{esc(r["reason"])}</span></td><td class=mute>The statement and the receipt disagree. Usual causes: a tip, VAT added at the till, or part of the bill paid another way.</td></tr>')
    section("Decisions needed", ["Evidence", "Page · group", "Candidate statement rows", "What to do"], [g for g in receipts if g["status"] == "REVIEW"],
            lambda g: f'<tr><td>{review_ev(g)}</td><td class=mono>p{esc(g["page"])} {esc(g["id"])}</td><td>' + ("<br>".join(cand(ref, sc) for ref, sc in g["review"]) or '<span class=mute>its candidates were taken by other receipts</span>') + f'</td><td class=mute>{esc(g["reason"])}. Pick the right row and record it in overrides.json under links["{esc(g["id"])}"].</td></tr>')
    section("ATM withdrawals and loads not in the ledger", ["Date", "SAR", "Kind", "Ref", "Evidence", "What to look for"], [r for r in rows if r["status"] == "UNEXPLAINED"],
            lambda r: f'<tr><td class=mono>{esc(r["date"])}</td><td class=num>{money(r["amount"])}</td><td>{esc(r["kind"])}</td><td class=mono>{esc(r["ref"])}</td><td>{rowev(r)}</td><td class=mute>No ledger top-up or cash-withdrawal line matches. Ask how cash taken from the card is booked.</td></tr>')
    section("Ledger lines without a card transaction", ["Code", "Date", "Debit", "Credit", "Text", "What to look for"], [(k, v) for k, v in t["ledger_status"].items() if v == "UNEXPLAINED"], ledger_row)
    H.append('</main><div id=ov><div class=wrap><img alt="Source page"><div class=box></div></div></div>' + f"<script>{JS}</script></body></html>")
    (common.DATA / "report.html").write_text("\n".join(H), encoding="utf-8")
    print("wrote", common.DATA / "report.html")

if __name__ == "__main__":
    main()
