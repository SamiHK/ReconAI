# scripts/abujhd/b_match.py
"""Step B: key relation + gap analysis. Pure functions over Step A's JSON. No network."""
import argparse, re, sys, pathlib, unicodedata
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
        ok = [A for A in out if abs(A["page"] - B["page"]) <= 1 and receipt_amounts(A) & receipt_amounts(B) and (not A["_rm"] or not tb or A["_rm"] & tb)]
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

def _amount_diff(g, row):
    return min((round(abs(a - row["amount"]), 2) for a in receipt_amounts(g)), default=99)

def score(g, row):
    if row["kind"] != "purchase": return 0
    diff = _amount_diff(g, row)
    if diff > 0.05: return 0
    s = 3 if diff == 0 else 2
    ds = [_days(d, row["date"]) for d in _dates(g)]
    support = 2 if 0 in ds else 1 if 1 in ds else 0
    A = norm_merchant(" ".join(_merchants(g)))
    B = norm_merchant(row["merchant"])
    overlap = A & B or _prefixes(A) & _prefixes(B)
    support += min(2, len(overlap))
    return s + support if s == 3 or support else 0  # a 5-halala drift alone is not a candidate: needs date or merchant support

_MULTI_DOC = re.compile(r"more than one|multiple documents|two documents", re.I)

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
        if top < 4 or tie or rival or row_ref in contested or _MULTI_DOC.search(g.get("notes") or ""):
            links[gid] = None; review[gid] = [(r, s) for s, r in scored[:3]]
        else:
            links[gid] = row_ref; taken.add(row_ref)
    return links, review

def _r2(x): return round(x, 2)

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
    near = lambda g, r: same_day(g, r) and _amount_diff(g, r) <= tol
    all_rows = [r for r in rows if r["kind"] == "purchase"]
    for g in left:   # unique both ways against EVERY same-day row/group, not only leftovers: a taken near-twin means ambiguity
        c = [r for r in left_rows if near(g, r)]
        if len(c) == 1 and sum(near(g, r) for r in all_rows) == 1 and sum(near(h, c[0]) for h in groups) == 1:
            links[g["id"]] = c[0]["ref"]; left_rows.remove(c[0])
    left = [g for g in left if not links.get(g["id"])]
    for g in left:
        f = g.get("fields") or {}
        if receipt_amounts(g) or not (f.get("merchant") and f.get("date")): continue
        real = lambda s: norm_merchant(s) - GENERIC - {"اسواق"}   # "markets" is generic here: the ASDAF alias maps to it
        toks = real(f["merchant"])
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

def assign_statuses(statement, groups, links, review, tieout, ledger):
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
            row["status"] = "AMOUNT_MISMATCH" if diff > 0.05 else "MATCHED"; row["reason"] = f"receipt {row['receipt_ids'][0]} p{g['page']}" + (f" (total differs by {diff:.2f})" if 0 < diff <= 0.05 else "")
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
    return rows, receipts

def main():
    global STATEMENT_FILE, RECEIPTS_FILE, LEDGER_FILE
    ap = argparse.ArgumentParser(); ap.add_argument("--data", default="data/abujhd"); a = ap.parse_args(); common.set_data(a.data)
    cfg = common.config(); STATEMENT_FILE, RECEIPTS_FILE, LEDGER_FILE = (cfg["names"][k] for k in ("statement", "receipts", "ledger"))
    statement = load_json(common.DATA / "statement.json"); ledger = load_json(common.DATA / "ledger.json"); groups = load_json(common.DATA / "groups.json")
    overrides = load_json(common.DATA / "overrides.json") if (common.DATA / "overrides.json").exists() else {}
    groups = collapse_fragments(collapse_card_slips(groups))
    links, review = match_receipts(groups, statement, overrides)
    links, review = second_pass(groups, statement, links, review)
    tieout = tie_out_ledger(statement, ledger, cfg["month"])
    rows, receipts = assign_statuses(statement, groups, links, review, tieout, ledger)
    import collections
    ovs = collections.Counter((r["orange"], r["status"]) for r in rows if r["kind"] == "purchase")
    summary = {"rows": dict(collections.Counter(r["status"] for r in rows)), "receipts": dict(collections.Counter(r["status"] for r in receipts))}
    save_json(common.DATA / "matches.json", {"rows": rows, "receipts": receipts, "ledger": ledger, "tieout": tieout,
                                              "orange_vs_status": {f"{'orange' if o else 'plain'}|{s}": n for (o, s), n in ovs.items()}, "summary": summary})
    print("rows:", summary["rows"]); print("receipts:", summary["receipts"]); print("tieout:", {k: v for k, v in tieout.items() if k != "ledger_status" and k != "small_credits"})
    for gid, cands in review.items(): print("REVIEW", gid, cands)

if __name__ == "__main__":
    main()
