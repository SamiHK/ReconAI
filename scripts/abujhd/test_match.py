# scripts/abujhd/test_match.py
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from b_match import norm_merchant, receipt_amounts, collapse_card_slips, score, match_receipts

def G(id, page, amounts, dates, merchant, kind="receipt", fields=None, notes=None):
    return {"id": id, "page": page, "pages": [page], "amounts": [{"value": a, "total_candidate": True} for a in amounts],
            "dates": dates, "merchant_candidates": [merchant], "fields": fields, "kind": kind, "notes": notes, "candidates": []}

def R(ref, amount, date, merchant, kind="purchase"):
    return {"ref": ref, "amount": amount, "date": date, "merchant": merchant, "kind": kind}

ROWS = [R("r1", 41.0, "2026-09-01", "MAZA RESTALAYOUNAL AHSASAU"),
        R("r2", 218.5, "2026-09-02", "AL FARES HOLDING COH alhazmMUBARRASAU"),
        R("r3", 50.0, "2026-09-10", "GREEN STAR FUEL STATIONALHASA"),
        R("r4", 50.0, "2026-09-10", "GREEN STAR FUEL STATIONALHASA"),
        R("r5", 9.0, "2026-09-20", "ASDAF ALMUHITAl Oyoun"),
        R("l1", 3000.0, "2026-09-01", "FROM0000", kind="load")]

def test_scoring_and_greedy():
    assert norm_merchant("Ibrahim A. Al-Fares & Bros.") >= {"ibrahim", "fares", "bros"}
    assert "ajmi" in norm_merchant("AJMY COMPANY")
    exact = G("g1", 1, [41.0], ["2026-09-01"], "MAZA REST")              # exact + same day + merchant → MATCHED
    near = G("g2", 2, [218.5], ["2026-09-01"], "Ibrahim A. Al-Fares")    # ±1 day
    tie_a = G("g3", 3, [50.0], ["2026-09-10"], "Green Star")             # two identical rows → REVIEW
    orphan = G("g4", 4, [99.0], ["2026-09-03"], "Nobody")                # no row
    weak = G("g5", 5, [9.0], [], "xyz")                                  # amount only → score 3 → REVIEW
    assert score(exact, ROWS[0]) >= 6 and score(near, ROWS[1]) >= 4 and score(weak, ROWS[4]) == 3
    links, review = match_receipts([exact, near, tie_a, orphan, weak], ROWS, {})
    assert links["g1"] == "r1" and links["g2"] == "r2" and links["g4"] is None
    assert "g3" in review and {r for r, _ in review["g3"]} == {"r3", "r4"} and links["g3"] is None
    assert "g5" in review
    links2, _ = match_receipts([exact, near, tie_a, orphan, weak], ROWS, {"links": {"g3": "r4", "g1": None}})
    assert links2["g3"] == "r4" and links2["g1"] is None

def test_collapse_and_amounts():
    inv = G("g1", 2, [218.5, 190.0], ["2026-09-01"], "Al-Fares", kind="invoice")
    slip = G("g2", 2, [218.5], ["2026-09-01"], "Al-Fares", kind="card_slip")
    out = collapse_card_slips([inv, slip])
    assert len(out) == 1 and out[0]["ids"] == ["g1", "g2"]
    healed = G("g9", 9, [1.0, 2.0], [], "x", fields={"total": 773.0, "card_slip_amount": None})
    assert receipt_amounts(healed) == {773.0}
    assert receipt_amounts(G("g8", 8, [5.0], [], "x")) == {5.0}

def test_greedy_contention_and_collapse_order():
    # (a) slip listed before its receipt still collapses; ids in receipt-then-slip order
    inv = G("g1", 2, [218.5, 190.0], ["2026-09-01"], "Al-Fares", kind="invoice")
    slip = G("g2", 2, [218.5], ["2026-09-01"], "Al-Fares", kind="card_slip")
    out = collapse_card_slips([slip, inv])
    assert len(out) == 1 and out[0]["ids"] == ["g1", "g2"], out
    # (b) X and Y both score 5 for rB, but X can take rA at 7 -> X gets rA, Y gets rB, no tie
    rA = R("rA", 10.0, "2026-09-01", "ALPHA STORE")
    rB = R("rB", 10.0, "2026-09-03", "BETA SHOP")
    X = G("X", 1, [10.0], ["2026-09-01", "2026-09-03"], "Alpha Store")
    Y = G("Y", 2, [10.0], ["2026-09-03"], "Gamma")
    links, review = match_receipts([X, Y], [rA, rB], {})
    assert links["X"] == "rA" and links["Y"] == "rB" and "X" not in review and "Y" not in review, (links, review)
    # (c) two groups score identically for the SAME single row -> both review, neither linked
    rC = R("rC", 10.0, "2026-09-01", "FOO")
    P = G("P", 1, [10.0], ["2026-09-01"], "Foo")
    Q = G("Q", 2, [10.0], ["2026-09-01"], "Foo")
    links, review = match_receipts([P, Q], [rC], {})
    assert links["P"] is None and links["Q"] is None and "P" in review and "Q" in review, (links, review)
    # (d) only candidate row forced to another group -> None and review entry with empty list
    rA = R("rA", 10.0, "2026-09-01", "ALPHA")
    other = G("other", 1, [10.0], ["2026-09-01"], "Alpha")
    Z = G("Z", 2, [10.0], ["2026-09-01"], "Alpha")
    links, review = match_receipts([other, Z], [rA], {"links": {"other": "rA"}})
    assert links["other"] == "rA" and links["Z"] is None and review["Z"] == [], (links, review)
    # (e) full-token overlap counts once: 3 (amount) + 1 (merchant) = 4, not 5
    g = G("g", 1, [10.0], [], "SUPERMARKET")
    assert score(g, R("rS", 10.0, "2026-09-01", "supermarket")) == 4

from b_match import tie_out_ledger, assign_statuses

def test_tieout_and_statuses():
    stmt = [R("p1", 41.0, "2026-09-01", "MAZA"), R("p2", 9.0, "2026-09-02", "ASDAF"), R("a1", 500.0, "2026-09-03", "BANKX", kind="atm"), R("l1", 3000.0, "2026-09-01", "FROM", kind="load")]
    for r in stmt: r["orange"] = r["ref"] == "p2"
    ledger = [{"code": "MISC/2026/09/0020", "date": "2026-09-01", "text": "Top up", "debit": 3000.0, "credit": None, "month": "2026-09"},
              {"code": "MISC/2026/09/0008", "date": "2026-09-13", "text": "Top up", "debit": 3000.0, "credit": None, "month": "2026-09"},
              {"code": "MISC/2026/09/0031", "date": "2026-09-30", "text": "Petty Cash for SEP", "debit": None, "credit": 1600.0, "month": "2026-09"},
              {"code": "MISC/2026/09/0034", "date": "2026-09-01", "text": "against INV", "debit": None, "credit": 9.0, "month": "2026-09"}]
    for l, n in zip(ledger, (74, 60, 83, 84)): l.update(sheet="General Ledger", row=n, cell=f"B{n}")
    t = tie_out_ledger(stmt, ledger)
    assert t["loads_vs_topups"]["statement"] == 3000.0 and t["loads_vs_topups"]["ledger"] == 6000.0 and t["loads_vs_topups"]["diff"] == -3000.0
    assert t["purchases_vs_rollup"]["statement"] == 550.0 and t["purchases_vs_rollup"]["ledger"] == 1600.0 and t["purchases_vs_rollup"]["diff"] == -1050.0
    assert t["ledger_status"]["MISC/2026/09/0020|Top up"] == "TIED" and t["ledger_status"]["MISC/2026/09/0008|Top up"] == "UNEXPLAINED"
    assert t["small_credits"][0]["ref"] == "p2"
    groups = [G("g1", 1, [41.0], ["2026-09-01"], "MAZA"), G("g2", 2, [77.0], [], "x"), G("g3", 3, [9.0], [], "y")]
    assert t["row_status"]["l1"] == "TIED" and t["row_ledger"]["l1"] == "MISC/2026/09/0020"
    rows, receipts = assign_statuses(stmt, groups, {"g1": "p1", "g2": None, "g3": None}, {"g3": [("p2", 3)]}, t, ledger)
    st = {r["ref"]: r["status"] for r in rows}
    assert st == {"p1": "MATCHED", "p2": "REVIEW", "a1": "UNEXPLAINED", "l1": "TIED"}, st
    assert {r["ref"]: r.get("ledger_code") for r in rows}["l1"] == t["row_ledger"]["l1"] == "MISC/2026/09/0020"
    rc = {r["id"]: r["status"] for r in receipts}
    assert rc == {"g1": "LINKED", "g2": "ORPHAN", "g3": "REVIEW"}
    # a withdrawal line 1:1 with the ATM row (same amount, <=2 days) ties it
    wd = {"code": "MISC/2026/09/0064", "date": "2026-09-03", "text": "Reconciliation - Cash Withdrawal", "debit": None, "credit": 500.0, "month": "2026-09", "sheet": "General Ledger", "row": 70, "cell": "B70"}
    t2 = tie_out_ledger(stmt, ledger + [wd])
    assert t2["row_status"]["a1"] == "TIED" and t2["ledger_status"]["MISC/2026/09/0064|Reconciliation - Cash Withdrawal"] == "TIED"
    rows2, _ = assign_statuses(stmt, groups, {"g1": "p1", "g2": None, "g3": None}, {"g3": [("p2", 3)]}, t2, ledger + [wd])
    assert {r["ref"]: r["status"] for r in rows2}["a1"] == "TIED"

def test_citations():
    stmt = [R("p1", 41.0, "2026-09-01", "MAZA"), R("p2", 9.0, "2026-09-02", "ASDAF"), R("a1", 500.0, "2026-09-03", "BANKX", kind="atm"), R("l1", 3000.0, "2026-09-01", "FROM", kind="load")]
    for r in stmt: r.update(orange=False, y=100.0, crop=f"crops/stmt-{r['ref']}.png", box=[0, 118, 1000, 123])
    ledger = [{"code": "MISC/2026/09/0020", "date": "2026-09-01", "text": "Top up", "debit": 3000.0, "credit": None, "month": "2026-09", "sheet": "General Ledger", "row": 74, "cell": "B74"},
              {"code": "MISC/2026/09/0031", "date": "2026-09-30", "text": "Petty Cash for SEP", "debit": None, "credit": 1600.0, "month": "2026-09", "sheet": "General Ledger", "row": 83, "cell": "B83"}]
    t = tie_out_ledger(stmt, ledger)
    g1 = G("g1", 7, [41.0], ["2026-09-01"], "MAZA"); g1["box"] = [10, 20, 300, 400]
    rows, receipts = assign_statuses(stmt, [g1], {"g1": "p1"}, {}, t, ledger)
    by = {r["ref"]: r["citations"] for r in rows}
    assert {r["ref"]: r["status"] for r in rows} == {"p1": "MATCHED", "p2": "MISSING_RECEIPT", "a1": "UNEXPLAINED", "l1": "TIED"}
    led = by["p1"]["ledger"]
    assert led["code"] == "MISC/2026/09/0031" and led["relation"] == "rolled-up" and led["cell"] == "B83" and led["amount"] == 1600.0
    assert len(by["p1"]["receipts"]) == 1 and by["p1"]["receipts"][0]["crop"] == "crops/g1.png" and by["p1"]["receipts"][0]["page"] == 7
    assert by["l1"]["ledger"]["relation"] == "tied" and by["l1"]["ledger"]["code"] == "MISC/2026/09/0020" and by["l1"]["ledger"]["cell"] == "B74"
    assert by["a1"]["ledger"] is None
    assert by["p2"]["receipts"] == [] and by["p2"]["statement"]["page"] == 1 and by["p2"]["statement"]["crop"] == "crops/stmt-p2.png"
    assert by["p2"]["ledger"]["relation"] == "rolled-up"   # a MISSING purchase is still inside the month's roll-up
    assert receipts[0]["citations"]["statement"]["ref"] == "p1" and receipts[0]["citations"]["ledger"]["cell"] == "B83"

from b_match import collapse_fragments, real_merchant_tokens, assign_statuses, tie_out_ledger

def test_fragments_and_tolerance():
    a = G("g1", 19, [313.95], ["2026-09-24"], "ALWAN PAINT COMPANY", kind="invoice")
    b = G("g2", 19, [313.95], [], "Total Invoice", kind=None)
    c = G("g3", 20, [313.95], [], "Amount in Words :", kind=None)
    d1 = G("g4", 10, [10.0], ["2026-09-03"], "ASDAF ALMUHIT")
    d2 = G("g5", 10, [10.0], ["2026-09-03"], "مؤسسة درة البندقية للمواد الغذائية")
    e = G("g6", 40, [313.95], [], "ALWAN PAINT COMPANY")          # far page: not merged
    for g in (a, b, c, d1, d2, e):
        g["ids"] = [g["id"]]; g["boxes"] = [(g["page"], None)]
    out = collapse_fragments([a, b, c, d1, d2, e])
    byid = {o["ids"][0]: o for o in out}
    assert byid["g1"]["ids"] == ["g1", "g2", "g3"] and byid["g1"]["pages"] == [19, 20]
    assert "g4" in byid and "g5" in byid and len(out) == 4          # different real merchants stay apart; g6 stays apart
    assert real_merchant_tokens(b) == set() and "alwan" in real_merchant_tokens(a)
    row = R("r1", 10.0, "2026-09-03", "AJMY COMPANY")
    assert score(G("h1", 1, [10.01], ["2026-09-03"], "Ajmi Trading"), row) == 2 + 2 + 1
    assert score(G("h2", 1, [10.06], ["2026-09-03"], "Ajmi Trading"), row) == 0
    assert score(G("h3", 1, [10.0], ["2026-09-03"], "Ajmi Trading"), row) == 3 + 2 + 1
    # order-independence: a merchant-less piece first must not swallow two different shops
    def rec(id, m):
        g = G(id, 10, [10.0], [], m); g["ids"] = [id]; g["boxes"] = [(10, None)]; return g
    gen, asd, dur = rec("x1", "Total Invoice"), rec("x2", "ASDAF ALMUHIT"), rec("x3", "مؤسسة درة البندقية للمواد الغذائية")
    out = collapse_fragments([gen, asd, dur])
    assert [o["ids"] for o in out] == [["x1"], ["x2"], ["x3"]] and all("_rm" not in o for o in out), out
    merged = collapse_fragments([rec("x1", "Total Invoice"), rec("x2", "ASDAF ALMUHIT")])
    assert len(merged) == 1 and sorted(merged[0]["ids"]) == ["x1", "x2"]
    assert len(collapse_fragments(merged + [rec("x3", "مؤسسة درة البندقية للمواد الغذائية")])) == 2   # a later shop does not join the merged record
    assert real_merchant_tokens(G("k", 1, [1.0], [], "الإجمالي إجمالي Total")) == set()
    # tolerance needs support; assign_statuses reasons
    assert score(G("t1", 1, [10.01], [], "xyz"), row) == 0 and score(G("t2", 1, [10.01], ["2026-09-03"], "xyz"), row) == 4
    assert score(G("t3", 1, [10.0], [], "xyz"), row) == 3
    stmt = [R("s1", 10.0, "2026-09-03", "AJMY COMPANY")]
    ok, bad = G("o1", 1, [10.01], ["2026-09-03"], "Ajmi"), G("o2", 2, [10.1], [], "zzz")
    links, rev = match_receipts([ok], stmt, {})
    rows, _ = assign_statuses(stmt, [ok], links, rev, tie_out_ledger(stmt, []), [])
    assert rows[0]["status"] == "MATCHED" and "differs by 0.01" in rows[0]["reason"], rows
    links, rev = match_receipts([bad], stmt, {"links": {"o2": "s1"}})
    rows, _ = assign_statuses(stmt, [bad], links, rev, tie_out_ledger(stmt, []), [])
    assert rows[0]["status"] == "AMOUNT_MISMATCH", rows

def test_override_robustness():
    import io, contextlib
    # a forced link on an id that collapse_fragments merged (not the head) resolves to the head
    a = G("g1", 5, [20.0], ["2026-09-03"], "ALWAN PAINT COMPANY", kind="invoice")
    b = G("g2", 5, [20.0], [], "Total Invoice", kind=None)
    for g in (a, b): g["ids"] = [g["id"]]; g["boxes"] = [(g["page"], None)]
    merged = collapse_fragments([a, b])
    assert len(merged) == 1 and merged[0]["ids"] == ["g1", "g2"]
    rows = [R("r1", 99.0, "2026-09-03", "OTHER"), R("r2", 77.0, "2026-09-04", "ELSE")]
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        links, _ = match_receipts(merged, rows, {"links": {"g2": "r1", "nope": "r2", "g1x": None}})
    assert links["g1"] == "r1" and "g2" not in links and "nope" not in links, links
    assert "unknown group id nope" in err.getvalue() and "unknown group id g1x" in err.getvalue()
    # unknown statement ref: skipped with a warning, the group is matched normally
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        links, _ = match_receipts(merged, rows, {"links": {"g1": "zzz"}})
    assert "unknown statement ref zzz for g1" in err.getvalue() and links["g1"] is None

def test_ledger_status_default():
    stmt = [R("p1", 41.0, "2026-09-01", "MAZA")]
    ledger = [{"code": "MISC/2026/09/0050", "date": "2026-09-05", "text": "Office supplies", "debit": 75.0, "credit": None, "month": "2026-09", "sheet": "General Ledger", "row": 5, "cell": "B5"},
              {"code": "MISC/2026/08/0001", "date": "2026-08-05", "text": "Other month", "debit": 5.0, "credit": None, "month": "2026-08", "sheet": "General Ledger", "row": 6, "cell": "B6"}]
    st = tie_out_ledger(stmt, ledger)["ledger_status"]
    assert st == {"MISC/2026/09/0050|Office supplies": "UNEXPLAINED"}, st

def test_multi_document_notes_go_to_review():
    row = R("r1", 41.0, "2026-09-01", "MAZA REST")
    clean = G("c", 1, [41.0], ["2026-09-01"], "MAZA REST")
    multi = G("m", 1, [41.0], ["2026-09-01"], "MAZA REST", notes="The crop contains more than one document; fields are for the largest.")
    assert match_receipts([clean], [row], {})[0]["c"] == "r1"
    links, review = match_receipts([multi], [row], {})
    assert links["m"] is None and [r for r, _ in review["m"]] == ["r1"]
    # the note survives collapsing into a record
    multi2 = G("m2", 1, [41.0], ["2026-09-01"], "MAZA REST", notes="two documents"); multi2["ids"] = ["m2"]; multi2["boxes"] = [(1, None)]
    clean2 = G("c2", 1, [41.0], [], "MAZA REST"); clean2["ids"] = ["c2"]; clean2["boxes"] = [(1, None)]
    assert "two documents" in collapse_fragments([clean2, multi2])[0]["notes"]

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print("ok", name)
