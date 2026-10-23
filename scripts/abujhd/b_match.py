# scripts/abujhd/b_match.py
"""Step B: key relation + gap analysis. Pure functions over Step A's JSON. No network."""
import argparse, re, sys, pathlib, unicodedata
from datetime import date, timedelta
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import common
from common import load_json, save_json, _days, total_flags

ALIASES = {"ajmy": "ajmi", "ajmi": "ajmi", "asdaf": "اسواق", "اسواق": "اسواق", "أسواق": "اسواق", "masdarusa": "masdar", "masdarman": "masdar", "masdarjana": "masdar",
           "almuhitai": "almuhit", "muhit": "almuhit", "alfares": "fares", "al-fares": "fares"}
STOP = {"company", "co", "est", "trading", "ltd", "llc", "the", "and", "for", "شركة", "مؤسسة", "للتجارة", "التجارية", "sau", "ahsasau", "ahsa", "riyadh"}

def _fold(s):
    return unicodedata.normalize("NFKC", s or "").lower().replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")

def norm_merchant(s):
    s = _fold(s)
    toks = set()
    for t in re.split(r"[^a-z0-9؀-ۿ]+", s):
        if len(t) < 3 or t in STOP: continue
        toks.add(ALIASES.get(t, t))
    return toks

def _prefixes(toks):
    """5-char prefixes of long run-on tokens (ALHASA SOUTHAL AHSASAU style), used only as a fallback when full tokens miss."""
    return {t[:5] for t in toks if len(t) > 6}

def receipt_amounts(g):
    f = g.get("fields") or {}
    healed = {round(v, 2) for v in (f.get("total"), f.get("card_slip_amount")) if isinstance(v, (int, float))}
    if healed: return healed
    # an unmerged record re-ranks its totals from its own text (groups.json may predate the keyword rules); a merged one keeps its merged flags
    if g.get("text") and len(g.get("ids") or [1]) == 1:
        totals = {round(v, 2) for v, t in total_flags(g["text"]).items() if t}
    else:
        totals = {a["value"] for a in g["amounts"] if a["total_candidate"]}
    return totals or {a["value"] for a in g["amounts"]}

def _dates(g):
    f = g.get("fields") or {}
    return ([f["date"]] if f.get("date") else []) + [d for d in g["dates"] if d != f.get("date")]

def _merchants(g):
    f = g.get("fields") or {}
    return ([f["merchant"]] if f.get("merchant") else []) + g["merchant_candidates"]

def collapse_card_slips(groups):
    """A card_slip group joins a same-amount receipt/invoice on the same or previous page (merchant must agree when the slip names one).
    Order-independent: receipts/invoices first in input order, then any slip that found no receipt as its own record."""
    out, used = [], set()
    for g in groups:
        if g.get("kind") == "card_slip" or g["id"] in used: continue
        rec = {**g, "ids": [g["id"]], "boxes": [(g["page"], g.get("box"))]}
        for s in groups:
            if s.get("kind") != "card_slip" or s["id"] in used or s["page"] not in (g["page"], g["page"] + 1): continue
            if not (receipt_amounts(s) & receipt_amounts(g)): continue
            if _merchants(s) and not (norm_merchant(" ".join(_merchants(s))) & norm_merchant(" ".join(_merchants(g)))): continue
            used.add(s["id"]); rec["ids"].append(s["id"]); rec["boxes"].append((s["page"], s.get("box")))
            rec["notes"] = " ".join(filter(None, [rec.get("notes"), s.get("notes")])) or None
            rec["fields"] = {**(rec.get("fields") or {}), "card_slip_amount": next(iter(receipt_amounts(s) & receipt_amounts(g)))}
        used.add(g["id"]); out.append(rec)
    for s in groups:
        if s.get("kind") == "card_slip" and s["id"] not in used:
            out.append({**s, "ids": [s["id"]], "boxes": [(s["page"], s.get("box"))]})
    return out

GENERIC = {_fold(t) for t in ("total", "invoice", "tax", "amount", "words", "kind", "diagram", "logo", "simplified", "customer", "sig", "branch", "main", "details", "payment", "bill", "receipt",
           "التفاصيل", "الكمية", "السعر", "تفاصيل", "الدفع", "فاتورة", "ضريبية", "مبسطة", "المجموع", "الإجمالي", "إجمالي", "الصافي", "توقيع", "المستلم")}

def real_merchant_tokens(g):
    return norm_merchant(" ".join(_merchants(g))) - GENERIC

def collapse_fragments(records):
    """Same-/adjacent-page pieces of one document (same total, compatible merchant) merge into the earliest record.
    Each record tracks `_rm`, the real merchant tokens of everything merged into it, so two different shops never share a record (p10: same 10.00).
    Merchant-less pieces go last (order-independent) and stay unmerged when two different shops would both accept them."""
    out = []
    for i, B in sorted(enumerate(records), key=lambda p: not real_merchant_tokens(p[1])):
        tb = real_merchant_tokens(B)
        same_day_ok = lambda A: not _dates(A) or not _dates(B) or set(_dates(A)) & set(_dates(B))   # two days = two purchases, never one record
        ok = [A for A in out if abs(A["page"] - B["page"]) <= 1 and receipt_amounts(A) & receipt_amounts(B) and (not A["_rm"] or not tb or A["_rm"] & tb) and same_day_ok(A)]
        if not tb and len({frozenset(A["_rm"]) for A in ok if A["_rm"]}) > 1: ok = []
        if not ok:
            out.append({**B, "ids": list(B["ids"]), "boxes": list(B["boxes"]), "amounts": [dict(x) for x in B["amounts"]], "dates": list(B["dates"]), "pages": list(B["pages"]), "_rm": set(tb), "_i": i})
            continue
        A = ok[0]
        A["ids"] += B["ids"]; A["boxes"] += B["boxes"]; A["_rm"] |= tb
        A["notes"] = " ".join(filter(None, [A.get("notes"), B.get("notes")])) or None   # a multi-document note on any piece must survive
        for x in B["amounts"]:
            m = next((y for y in A["amounts"] if y["value"] == x["value"]), None)
            if m: m["total_candidate"] = m["total_candidate"] or x["total_candidate"]
            else: A["amounts"].append(dict(x))
        A["dates"] += [d for d in B["dates"] if d not in A["dates"]]
        if not (A.get("fields") or {}).get("merchant") and (B.get("fields") or {}).get("merchant"): A["fields"] = B["fields"]
        A["pages"] = sorted(set(A["pages"]) | set(B["pages"]))
    out.sort(key=lambda A: A["_i"])
    return [{k: v for k, v in A.items() if k not in ("_rm", "_i")} for A in out]

def _date_readings(d, year):
    """ISO dates a scanned date could really mean: as read, the year corrected, day and month swapped, the Arabic digits
    3/9 confused in the month. What OCR gets wrong on these receipts, so the matcher and the other-month check agree."""
    try: yy, mm, dd = (int(x) for x in d.split("-"))
    except (ValueError, AttributeError): return []
    swap = {3: 9, 9: 3}
    out = []
    for y_, m_, d_ in ((yy, mm, dd), (year, mm, dd), (yy, dd, mm), (year, dd, mm), (yy, swap.get(mm, mm), dd), (year, swap.get(mm, mm), dd)):
        try: out.append(date(y_, m_, d_).isoformat())
        except ValueError: pass
    return list(dict.fromkeys(out))

def _amount_diff(g, row):
    return min((round(abs(a - row["amount"]), 2) for a in receipt_amounts(g)), default=99)

def score(g, row):
    if row["kind"] != "purchase": return 0
    diff = _amount_diff(g, row)
    if diff > 0.05: return 0
    s = 3 if diff == 0 else 2
    ry = int(row["date"][:4])
    ds = [_days(x, row["date"]) for d in _dates(g) for x in _date_readings(d, ry)]
    support = 2 if 0 in ds else 1 if 1 in ds else 0
    A = norm_merchant(" ".join(_merchants(g)))
    B = norm_merchant(row["merchant"])
    overlap = A & B or _prefixes(A) & _prefixes(B)
    support += min(2, len(overlap))
    return s + support if s == 3 or support else 0  # a 5-halala drift alone is not a candidate: needs date or merchant support

_MULTI_DOC = re.compile(r"more than one|multiple documents|two documents|two receipts|separate receipts", re.I)
_ATTACHED_SLIP = re.compile(r"card slip|pos slip|card/pos|pos/card|mada|point[- ]of[- ]sale|payment slip|terminal receipt", re.I)

def _looks_multi_document(notes):
    """A healer note about two documents forces review, unless the second one is the purchase's own card/POS slip."""
    n = notes or ""
    return bool(_MULTI_DOC.search(n)) and not _ATTACHED_SLIP.search(n)

def match_receipts(groups, rows, overrides):
    # a forced link may name any id merged into a record by collapse_*: resolve it to the record's head id
    head_of = {i: g["id"] for g in groups for i in g.get("ids") or [g["id"]]}
    refs = {r["ref"] for r in rows}
    forced = {}
    for gid, ref in ((overrides or {}).get("links") or {}).items():
        if gid not in head_of: print(f"override: unknown group id {gid}", file=sys.stderr); continue
        if ref and ref not in refs: print(f"override: unknown statement ref {ref} for {gid}", file=sys.stderr); continue
        forced[head_of[gid]] = ref
    links, review, taken = {}, {}, set()
    for gid, ref in forced.items():
        links[gid] = ref
        if ref: taken.add(ref)
    pending = {g["id"]: g for g in groups if g["id"] not in forced}
    contested = set()  # rows that tied between groups: stay in review candidate lists, never auto-linked
    while pending:
        best = None  # (score, gid, filtered_scored)
        for gid, g in pending.items():
            scored = sorted(((score(g, r), r["ref"]) for r in rows if r["ref"] not in taken), reverse=True)
            scored = [(s, r) for s, r in scored if s > 0]
            top = scored[0][0] if scored else -1
            if best is None or top > best[0]:
                best = (top, gid, scored)
        top, gid, scored = best
        g = pending.pop(gid)
        if not scored:
            links[gid] = None
            # had candidates before others took them → human should see it
            if any(score(g, r) > 0 for r in rows):
                review[gid] = []
            continue
        tie = len(scored) > 1 and scored[1][0] == scored[0][0]
        # a different pending group wanting the same best row with the same score is also a tie
        rival = any(
            score(h, next(r for r in rows if r["ref"] == scored[0][1])) == scored[0][0]
            for hid, h in pending.items())
        row_ref = scored[0][1]
        if rival:
            contested.add(row_ref)
        # healer saw several documents in one crop: its fields describe only one of them, so a human decides
        if top < 4 or tie or rival or row_ref in contested or _looks_multi_document(g.get("notes")):
            links[gid] = None; review[gid] = [(r, s) for s, r in scored[:3]]
        else:
            links[gid] = row_ref; taken.add(row_ref)
    return links, review

def _r2(x): return round(x, 2)

def split_other_month(groups, month, rows=()):
    """Receipts that belong to another month: every readable date is outside the period (plus a day either side, since a
    card can post next day) under every plausible reading, within a year of it, and no amount on the receipt matches a
    purchase row of this statement. Plausible readings cover what OCR gets wrong on these scans: the year off (same
    month and day), day and month swapped, and the Arabic digits ٣/٩ confused (month 03 vs 09). A date years off is an
    unreadable date, not another month; no date means nothing to judge. The healer's date wins over derived dates."""
    from datetime import date, timedelta
    y, m = (int(x) for x in month.split("-"))
    start = date(y, m, 1) - timedelta(days=1)
    end = date(y + (m == 12), m % 12 + 1, 1)
    def verdict(d):
        readings = _date_readings(d, y)
        if not readings: return None
        if any(start <= date.fromisoformat(x) <= end for x in readings): return "in"
        return "other" if abs((date.fromisoformat(readings[0]) - start).days) <= 366 else None
    amounts_this_month = {round(r["amount"], 2) for r in rows if r.get("kind", "purchase") == "purchase"}
    keep, other = [], []
    for g in groups:
        f = g.get("fields") or {}
        ds = [f["date"]] if f.get("date") else list(g["dates"])
        vs = [verdict(d) for d in ds]
        dated_elsewhere = bool(vs) and "in" not in vs and "other" in vs
        amount_here = bool(receipt_amounts(g) & amounts_this_month)
        (other if dated_elsewhere and not amount_here else keep).append(g)
    return keep, other

def _refs(v): return v if isinstance(v, list) else [v] if v else []

def second_pass(groups, rows, links, review, tol=3.0):
    """Leftovers only: rows nobody linked or listed for review, groups with no link and no review entry. Pass 1 is never touched.
    1) split payment: two same-day rows with the identical statement merchant string summing exactly to a receipt total -> both linked.
    2) near amount: one row within `tol` SAR on the receipt's date, unique both ways -> linked (assign_statuses shows AMOUNT_MISMATCH).
    3) no total: a healed receipt with merchant+date but no amount and one same-day row whose merchant overlaps -> review suggestion."""
    links, review = dict(links), dict(review)
    taken = {r for v in links.values() for r in _refs(v)} | {r for c in review.values() for r, _ in c}
    left_rows = [r for r in rows if r["kind"] == "purchase" and r["ref"] not in taken]
    left = [g for g in groups if not links.get(g["id"]) and g["id"] not in review]
    same_day = lambda g, r: r["date"] in _dates(g)
    for g in left:
        for T in receipt_amounts(g):
            c = [r for r in left_rows if same_day(g, r)]
            pairs = [(a, b) for i, a in enumerate(c) for b in c[i + 1:] if a["merchant"] == b["merchant"] and abs(_r2(a["amount"] + b["amount"]) - T) <= 0.05]
            if len(pairs) == 1:
                a, b = pairs[0]; links[g["id"]] = [a["ref"], b["ref"]]; left_rows = [r for r in left_rows if r not in (a, b)]; break
    left = [g for g in left if not links.get(g["id"])]
    real = lambda s: norm_merchant(s) - GENERIC - {"اسواق"}   # "markets" is generic here: the ASDAF alias maps to it
    close = lambda g, r: same_day(g, r) and _amount_diff(g, r) <= tol   # ambiguity is judged on this alone, support or not
    def near(g, r):   # a candidate link: close, within 10% of the row, and the merchant overlaps or the healer was confident
        if not (close(g, r) and _amount_diff(g, r) <= 0.10 * r["amount"]): return False
        A, B = real_merchant_tokens(g), real(r["merchant"])
        return bool(A & B or _prefixes(A) & _prefixes(B) or (g.get("confidence") or 0) >= 0.7)
    all_rows = [r for r in rows if r["kind"] == "purchase"]
    for g in left:   # unique both ways against EVERY same-day row/group, not only leftovers: a taken near-twin means ambiguity
        c = [r for r in left_rows if close(g, r) and _amount_diff(g, r) <= 0.10 * r["amount"]]
        if len(c) == 1 and sum(close(g, r) for r in all_rows) == 1 and sum(close(h, c[0]) for h in groups) == 1:
            if near(g, c[0]): links[g["id"]] = c[0]["ref"]
            else: review[g["id"]] = [(c[0]["ref"], 0)]   # unique but unsupported: a human decides, never a silent miss
            left_rows.remove(c[0])
    left = [g for g in left if not links.get(g["id"]) and g["id"] not in review]
    for g in left:
        f = g.get("fields") or {}
        has_total = any(a["total_candidate"] for a in g["amounts"]) or any(isinstance(f.get(k), (int, float)) for k in ("total", "card_slip_amount"))
        if has_total or not (f.get("merchant") and f.get("date")): continue   # "no total was read", not "no amount at all": stray amounts must not block the suggestion
        toks = real(" ".join(_merchants(g)))   # healer merchant plus derived candidates, like score() does
        c = [r for r in left_rows if r["date"] == f["date"] and (toks & real(r["merchant"]) or _prefixes(toks) & _prefixes(real(r["merchant"])))]
        if len(c) == 1: review[g["id"]] = [(c[0]["ref"], 0)]; left_rows.remove(c[0])
    return links, review

def tie_out_ledger(statement, ledger, month="2026-09"):
    led = [l for l in ledger if l["month"] == month]
    loads = [r for r in statement if r["kind"] == "load"]; atm = [r for r in statement if r["kind"] == "atm"]; purch = [r for r in statement if r["kind"] == "purchase"]
    topups = [l for l in led if l["debit"] and re.search(r"top ?up|payment to|reconciliation - top", l["text"], re.I)]
    withdrawals = [l for l in led if l["credit"] and re.search(r"cash withdrawal", l["text"], re.I)]
    rollup = [l for l in led if l["credit"] and re.search(r"petty cash for|petty cash expenses", l["text"], re.I) and l["credit"] > 1000]
    small = [l for l in led if l["credit"] and l not in rollup and l not in withdrawals]
    status = {f"{l['code']}|{l['text']}": "UNEXPLAINED" for l in led}   # every month line gets a status; the classifiers below upgrade it
    used = set()
    row_status = {r["ref"]: "UNEXPLAINED" for r in loads + atm}
    row_ledger = {}
    for l in topups:
        hit = next((r for r in loads if r["ref"] not in used and r["amount"] == l["debit"] and _days(r["date"], l["date"]) <= 2), None)
        if hit: used.add(hit["ref"]); row_status[hit["ref"]] = "TIED"; row_ledger[hit["ref"]] = l["code"]
        status[f"{l['code']}|{l['text']}"] = "TIED" if hit else "UNEXPLAINED"
    atm_used = set()
    for l in withdrawals:
        hit = next((r for r in atm if r["ref"] not in atm_used and r["amount"] == l["credit"] and _days(r["date"], l["date"]) <= 2), None)
        if hit: atm_used.add(hit["ref"]); row_status[hit["ref"]] = "TIED"; row_ledger[hit["ref"]] = l["code"]
        status[f"{l['code']}|{l['text']}"] = "TIED" if hit else "UNEXPLAINED"
    for l in rollup:
        status[f"{l['code']}|{l['text']}"] = "TIED" if _r2(sum(r["amount"] for r in purch + atm)) == _r2(l["credit"]) else "UNEXPLAINED"
    small_credits = []
    for l in small:
        hit = next((r for r in purch if r["amount"] == l["credit"]), None)
        small_credits.append({"code": l["code"], "text": l["text"], "credit": l["credit"], "ref": hit["ref"] if hit else None})
        status[f"{l['code']}|{l['text']}"] = "TIED" if hit else "UNEXPLAINED"
    S = lambda rows, k: _r2(sum(r[k] or 0 for r in rows))
    return {
        "loads_vs_topups": {"statement": S(loads, "amount"), "ledger": S(topups, "debit"), "diff": _r2(S(loads, "amount") - S(topups, "debit")), "n_statement": len(loads), "n_ledger": len(topups)},
        "atm_vs_withdrawals": {"statement": S(atm, "amount"), "ledger": S(withdrawals, "credit"), "diff": _r2(S(atm, "amount") - S(withdrawals, "credit"))},
        "purchases_vs_rollup": {"statement": S(purch + atm, "amount"), "purchases_only": S(purch, "amount"), "ledger": S(rollup, "credit"), "diff": _r2(S(purch + atm, "amount") - S(rollup, "credit")), "rollup_codes": [l["code"] for l in rollup]},
        "small_credits": small_credits, "ledger_status": status, "row_status": row_status, "row_ledger": row_ledger,
    }

# file names cited in the report; main() replaces them with config()["names"] (git-ignored client data)
STATEMENT_FILE, RECEIPTS_FILE, LEDGER_FILE = "statement.pdf", "receipts.pdf", "ledger.xlsx"

def _receipt_cites(g):
    # a collapsed record carries one (page, box) per crop id (ids[k] <-> boxes[k])
    return [{"file": RECEIPTS_FILE, "page": p, "group_id": gid, "box": box, "crop": f"crops/{gid}.png"}
            for gid, (p, box) in zip(g.get("ids") or [g["id"]], g.get("boxes") or [(g["page"], g.get("box"))])]

def assign_statuses(statement, groups, links, review, tieout, ledger, other_month=(), month=None):
    led = {l["code"]: l for l in ledger}
    rollup = (tieout["purchases_vs_rollup"]["rollup_codes"] or [None])[0]
    def ledger_cite(code, relation):
        l = led.get(code)
        return l and {"file": LEDGER_FILE, "sheet": l["sheet"], "row": l["row"], "cell": l["cell"], "code": code, "date": l["date"],
                      "amount": l["debit"] or l["credit"], "relation": relation}
    by_id = {g["id"]: g for g in groups}
    by_ref = {}
    for gid, v in links.items():
        for ref in _refs(v): by_ref.setdefault(ref, []).append(gid)
    review_refs = {r for cands in review.values() for r, _ in cands}
    rows = []
    for r in statement:
        row = {**r, "receipt_ids": by_ref.get(r["ref"], []), "status": None, "reason": ""}
        if r["kind"] != "purchase":
            row["status"] = tieout["row_status"].get(r["ref"], "UNEXPLAINED")
            row["ledger_code"] = tieout["row_ledger"].get(r["ref"]) if row["status"] == "TIED" else None
            row["reason"] = f"tied to ledger {row['ledger_code']}" if row["ledger_code"] else "no ledger top-up/withdrawal matches this row"
        elif row["receipt_ids"] and isinstance(links.get(row["receipt_ids"][0]), list):
            g = by_id[row["receipt_ids"][0]]; parts = [next(x for x in statement if x["ref"] == ref)["amount"] for ref in links[g["id"]]]
            row["status"] = "MATCHED"; row["reason"] = f"receipt {g['id']} p{g['page']} (split payment: {' + '.join(f'{p:.2f}' for p in parts)})"
        elif row["receipt_ids"]:
            g = next(g for g in groups if g["id"] == row["receipt_ids"][0])
            diff = _amount_diff(g, r)
            row["status"] = "AMOUNT_MISMATCH" if diff > 0.05 else "MATCHED"; row["reason"] = f"receipt {row['receipt_ids'][0]} p{g['page']}" + (f" (total differs by {diff:.2f})" if diff > 0 else "")
        elif r["ref"] in review_refs:
            row["status"] = "REVIEW"; row["reason"] = "candidate receipts need a human pick"
        else:
            row["status"] = "MISSING_RECEIPT"; row["reason"] = "no receipt with this amount (±0.05 needs date/merchant support) within ±1 day"
        row["citations"] = {
            "statement": {"file": STATEMENT_FILE, "page": 1, "ref": r["ref"], "y": r.get("y"), "orange": r.get("orange"), "crop": r.get("crop"), "box": r.get("box")},
            "receipts": [c for i in row["receipt_ids"] for c in _receipt_cites(by_id[i])],
            "ledger": ledger_cite(rollup, "rolled-up") if r["kind"] == "purchase" else ledger_cite(row.get("ledger_code"), "tied")}
        rows.append(row)
    cite_by_ref = {row["ref"]: row["citations"] for row in rows}
    receipts = []
    for g in groups:
        refs = _refs(links.get(g["id"])); ref = refs[0] if refs else None
        st = "LINKED" if ref else "REVIEW" if g["id"] in review else "ORPHAN"
        rc = cite_by_ref.get(ref) or {}
        receipts.append({**g, "ref": ref, "refs": refs, "status": st, "review": review.get(g["id"], []),
                         "citations": {"receipt": _receipt_cites(g), "statement": rc.get("statement"), "ledger": rc.get("ledger")},
                         "reason": "linked" if ref else "ambiguous or weak candidates" if st == "REVIEW" else "no statement row with this amount (cash purchase? wrong total?)"})
    from datetime import datetime
    month = month or (statement[0]["date"][:7] if statement else None)   # the statement is the period
    label = datetime.strptime(month, "%Y-%m").strftime("%B %Y") if month else "the period"
    for g in other_month:
        f = g.get("fields") or {}
        d = f.get("date") or (g["dates"][0] if g["dates"] else "?")
        receipts.append({**g, "ref": None, "refs": [], "status": "OTHER_MONTH", "review": [],
                         "citations": {"receipt": _receipt_cites(g), "statement": None, "ledger": None},
                         "reason": f"dated {d}, outside {label}: another month's pack, or a wrong date on the receipt"})
    return rows, receipts

def main():
    global STATEMENT_FILE, RECEIPTS_FILE, LEDGER_FILE
    ap = argparse.ArgumentParser(); ap.add_argument("--data", default="data/abujhd"); a = ap.parse_args(); common.set_data(a.data)
    cfg = common.config(); STATEMENT_FILE, RECEIPTS_FILE, LEDGER_FILE = (cfg["names"][k] for k in ("statement", "receipts", "ledger"))
    statement = load_json(common.DATA / "statement.json"); ledger = load_json(common.DATA / "ledger.json"); groups = load_json(common.DATA / "groups.json")
    overrides = load_json(common.DATA / "overrides.json") if (common.DATA / "overrides.json").exists() else {}
    groups = collapse_fragments(collapse_card_slips(groups))
    groups, other_month = split_other_month(groups, cfg["month"], statement)
    links, review = match_receipts(groups, statement, overrides)
    links, review = second_pass(groups, statement, links, review)
    tieout = tie_out_ledger(statement, ledger, cfg["month"])
    rows, receipts = assign_statuses(statement, groups, links, review, tieout, ledger, other_month=other_month, month=cfg["month"])
    import collections
    ovs = collections.Counter((r["orange"], r["status"]) for r in rows if r["kind"] == "purchase")
    summary = {"rows": dict(collections.Counter(r["status"] for r in rows)), "receipts": dict(collections.Counter(r["status"] for r in receipts))}
    save_json(common.DATA / "matches.json", {"rows": rows, "receipts": receipts, "ledger": ledger, "tieout": tieout,
                                              "orange_vs_status": {f"{'orange' if o else 'plain'}|{s}": n for (o, s), n in ovs.items()}, "summary": summary})
    print("rows:", summary["rows"]); print("receipts:", summary["receipts"]); print("tieout:", {k: v for k, v in tieout.items() if k != "ledger_status" and k != "small_credits"})
    for gid, cands in review.items(): print("REVIEW", gid, cands)
    for g in other_month: print("OTHER_MONTH", g["id"], (g.get("fields") or {}).get("date") or g["dates"][:1])

if __name__ == "__main__":
    main()
