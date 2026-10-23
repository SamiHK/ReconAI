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

from b_match import second_pass

def _left(gs):
    for g in gs: g.setdefault("ids", [g["id"]]); g.setdefault("boxes", [(g["page"], None)])
    return gs

def test_second_pass_split_payment():
    rows = [R("a", 33.0, "2026-09-01", "QALAT REST"), R("b", 8.0, "2026-09-01", "QALAT REST"), R("c", 8.0, "2026-09-01", "OTHER SHOP")]
    g = _left([G("g1", 1, [41.0], ["2026-09-01"], "Qalat")])[0]
    links, review = second_pass([g], rows, {"g1": None}, {})
    assert links["g1"] == ["a", "b"], links          # same merchant string, same day, exact sum
    # a leftover row already named in a review list, or already linked, is never consumed
    links, review = second_pass([g], rows, {"g1": None}, {"zz": [("b", 3)]})
    assert links["g1"] is None, links
    links, review = second_pass([g], rows, {"g1": None, "g2": "a"}, {})
    assert links["g1"] is None, links
    rows4 = [R("a", 25.0, "2026-09-19", "PURE OIL"), R("b", 45.0, "2026-09-19", "PURE OIL")]
    g4 = _left([G("g4", 54, [70.02], ["2026-09-19"], "Purein")])[0]
    assert second_pass([g4], rows4, {"g4": None}, {})[0]["g4"] == ["a", "b"]     # sum within 0.05 of the total, like pass 1

def test_second_pass_amount_tolerance():
    rows = [R("a", 172.0, "2026-09-09", "ALMAQHAWI IND"), R("b", 500.0, "2026-09-09", "X")]
    g = _left([G("g1", 1, [172.5], ["2026-09-09"], "Ibrahim Al-Mughawi")])[0]; g["confidence"] = 0.9   # no merchant overlap: the healer's confidence carries it
    links, _ = second_pass([g], rows, {"g1": None}, {})
    assert links["g1"] == "a", links                  # same day, 0.50 apart, unique both ways
    rows2, _ = assign_statuses(rows, [g], links, {}, tie_out_ledger(rows, []), [])
    assert {r["ref"]: r["status"] for r in rows2}["a"] == "AMOUNT_MISMATCH"   # flagged, not promoted
    for bad in ([R("a", 175.51, "2026-09-09", "Y")],                          # 3.01 apart
                [R("a", 172.0, "2026-09-10", "Y")],                           # other day
                [R("a", 172.0, "2026-09-09", "Y"), R("a2", 171.0, "2026-09-09", "Z")]):   # two rows within 3.00: ambiguous
        assert second_pass([g], bad, {"g1": None}, {})[0]["g1"] is None, bad
    # two leftover receipts within 3.00 of the same row: ambiguous the other way
    g2 = _left([G("g2", 2, [171.0], ["2026-09-09"], "Other")])[0]
    assert second_pass([g, g2], rows, {"g1": None, "g2": None}, {})[0]["g1"] is None
    # a NON-leftover row (linked or in review) within tolerance on the same day still makes the receipt ambiguous
    rows3 = [R("a", 172.0, "2026-09-09", "Y"), R("z", 171.5, "2026-09-09", "Z")]
    assert second_pass([g], rows3, {"g1": None, "gz": "z"}, {})[0]["g1"] is None
    assert second_pass([g], rows3, {"g1": None}, {"gq": [("z", 3)]})[0]["g1"] is None

def test_second_pass_near_amount_guard():
    day = "2026-09-08"
    weak = _left([G("g1", 1, [37.99], [day], "Othaim")])[0]; weak["confidence"] = 0.42
    assert second_pass([weak], [R("a", 40.0, day, "AJMY COMPANY")], {"g1": None}, {})[0]["g1"] is None   # no merchant overlap, low confidence
    assert second_pass([weak], [R("a", 40.0, day, "AL OTHAIM MARKETS")], {"g1": None}, {})[0]["g1"] == "a"   # merchant overlap carries it
    sure = _left([G("g2", 2, [30.0], [day], "Nobody Alike")])[0]; sure["confidence"] = 0.95
    rows = [R("a", 31.5, day, "ZZZ")]
    links, _ = second_pass([sure], rows, {"g2": None}, {})
    assert links["g2"] == "a", links                  # confident healer: 1.50 <= min(3.00, 10% of 31.50)
    rows2, _ = assign_statuses(rows, [sure], links, {}, tie_out_ledger(rows, []), [])
    assert "differs by 1.50" in rows2[0]["reason"] and rows2[0]["status"] == "AMOUNT_MISMATCH", rows2[0]
    rows3 = [R("c", 32.5, day, "ZZZ")]
    l3, _ = second_pass([sure], rows3, {"g2": None}, {})
    assert "differs by 2.50" in assign_statuses(rows3, [sure], l3, {}, tie_out_ledger(rows3, []), [])[0][0]["reason"]
    small = _left([G("g3", 3, [7.5], [day], "Nobody Alike")])[0]; small["confidence"] = 0.95
    assert second_pass([small], [R("b", 5.0, day, "ZZZ")], {"g3": None}, {})[0]["g3"] is None   # 2.50 > 10% of 5.00

def test_second_pass_no_total_to_review():
    rows = [R("a", 93.0, "2026-09-08", "AL OTHAIM MARKETS COMPANY"), R("b", 6.0, "2026-09-08", "ASDAF")]
    g = _left([G("g1", 26, [], ["2026-09-08"], "Othaim", fields={"merchant": "أسواق العثيم / Othaim", "date": "2026-09-08", "total": None, "card_slip_amount": None})])[0]
    links, review = second_pass([g], rows, {"g1": None}, {})
    assert links["g1"] is None and review["g1"] == [("a", 0)], (links, review)   # a suggestion for the human, not a match
    rows2, rc = assign_statuses(rows, [g], links, review, tie_out_ledger(rows, []), [])
    assert {r["ref"]: r["status"] for r in rows2}["a"] == "REVIEW" and rc[0]["status"] == "REVIEW"
    # two same-merchant rows that day: no suggestion
    assert "g1" not in second_pass([g], rows + [R("c", 20.0, "2026-09-08", "AL OTHAIM MARKETS")], {"g1": None}, {})[1]

def test_split_link_statuses():
    rows = [R("a", 33.0, "2026-09-01", "QALAT REST"), R("b", 8.0, "2026-09-01", "QALAT REST")]
    g = _left([G("g1", 1, [41.0], ["2026-09-01"], "Qalat")])[0]; g["box"] = [0, 0, 10, 10]
    rows2, rc = assign_statuses(rows, [g], {"g1": ["a", "b"]}, {}, tie_out_ledger(rows, []), [])
    assert [r["status"] for r in rows2] == ["MATCHED", "MATCHED"] and "split" in rows2[0]["reason"], rows2
    assert rc[0]["status"] == "LINKED" and rc[0]["ref"] == "a" and rc[0]["refs"] == ["a", "b"]

def test_receipt_amounts_reranks_unhealed_totals():
    g = {"id": "u", "page": 1, "pages": [1], "fields": None, "dates": [], "merchant_candidates": [],
         "text": "Amount 560.87 VAT 84.13 Total 645.00",
         "amounts": [{"value": 560.87, "total_candidate": True}, {"value": 645.0, "total_candidate": False}]}
    assert receipt_amounts(g) == {645.0}
    g["text"] = "645.00 SAR\nالمجموع قبل الضريبة\n560.87 SAR"      # no total keyword survives: every amount is a candidate
    assert receipt_amounts(g) == {645.0, 560.87}
    g["ids"] = ["u", "v"]                                            # a merged record keeps its merged flags (head text is partial)
    assert receipt_amounts(g) == {560.87}

def test_no_total_suggestion_despite_stray_amounts():
    # the healer read merchant and date but no total; a stray amount in the text must not block the suggestion
    rows = [R("a", 93.0, "2026-09-08", "AL OTHAIM MARKETS COMPANY"), R("b", 6.0, "2026-09-08", "ASDAF")]
    g = _left([G("g1", 26, [0.0], ["2026-09-08"], "Othaim", fields={"merchant": "أسواق العثيم / Othaim", "date": "2026-09-08", "total": None, "card_slip_amount": None})])[0]
    g["amounts"] = [{"value": 0.0, "total_candidate": False}]
    links, review = second_pass([g], rows, {"g1": None}, {})
    assert links["g1"] is None and review["g1"] == [("a", 0)], (links, review)
    # with a real total candidate the rule stays out of the way
    g2 = _left([G("g2", 27, [52.5], ["2026-09-08"], "Cafe", fields={"merchant": "Cafe", "date": "2026-09-08", "total": None, "card_slip_amount": None})])[0]
    assert "g2" not in second_pass([g2], [R("c", 50.0, "2026-09-08", "CAFE")], {"g2": None}, {})[1]

def test_attached_card_slip_is_one_document():
    row = R("r1", 900.0, "2026-09-02", "ALANDALUS TRADING CO")
    g = G("g", 8, [900.0], ["2026-09-02"], "ALANDALUS TRADING", notes="The crop contains two documents: a simplified tax invoice and an attached Mada POS/card slip.")
    assert match_receipts([g], [row], {})[0]["g"] == "r1"          # invoice + its own slip is one purchase
    g2 = G("g2", 8, [900.0], ["2026-09-02"], "ALANDALUS TRADING", notes="The crop contains two separate receipts from different shops.")
    links, review = match_receipts([g2], [row], {})
    assert links["g2"] is None and "g2" in review                  # genuinely two documents still goes to a human

from b_match import split_other_month

def test_split_other_month():
    aug = G("a", 1, [10.0], ["2026-08-14"], "Shop")                      # previous month
    oct_ = G("o", 2, [10.0], ["2026-10-02"], "Shop")                     # next month
    edge = G("e", 3, [10.0], ["2026-08-31"], "Shop")                     # one day before: stays (card can post next day)
    mixed = G("m", 4, [10.0], ["2025-09-03", "2026-09-03"], "Shop")      # OCR gave two years, one in month: stays
    far = G("f", 5, [10.0], ["2024-09-20"], "Shop")                      # years off: unreadable date, not another month
    nodate = G("n", 6, [10.0], [], "Shop")
    healed = G("h", 7, [10.0], ["2026-09-05"], "Shop", fields={"merchant": "Shop", "date": "2026-07-05", "total": 10.0, "card_slip_amount": None})  # healer date wins
    yearoff = G("y", 8, [10.0], ["2025-09-02"], "Shop")                  # OCR year off by one: this month
    swapped = G("w", 9, [10.0], ["2026-12-09"], "Shop")                  # day/month swapped (12 Sep): this month
    arabic = G("q", 10, [10.0], ["2026-03-16"], "Shop")                   # ٣ read for ٩: 16 Sep, this month
    keep, other = split_other_month([aug, oct_, edge, mixed, far, nodate, healed, yearoff, swapped, arabic], "2026-09")
    assert [g["id"] for g in other] == ["a", "o", "h"], [g["id"] for g in other]
    assert [g["id"] for g in keep] == ["e", "m", "f", "n", "y", "w", "q"], [g["id"] for g in keep]
    # an amount that matches a purchase row of this statement proves the receipt is this month's, whatever the date says
    keep2, other2 = split_other_month([aug], "2026-09", [R("r", 10.0, "2026-09-14", "SHOP")])
    assert [g["id"] for g in keep2] == ["a"] and other2 == []

def test_other_month_receipts_get_their_own_status():
    rows = [R("r1", 10.0, "2026-09-05", "SHOP")]
    aug = G("a", 1, [10.0], ["2026-08-14"], "Shop"); aug["box"] = [0, 0, 1, 1]
    sep = G("s", 2, [10.0], ["2026-09-05"], "Shop"); sep["box"] = [0, 0, 1, 1]
    keep, other = split_other_month([aug, sep], "2026-09")
    links, review = match_receipts(keep, rows, {})
    rows2, receipts = assign_statuses(rows, keep, links, review, tie_out_ledger(rows, []), [], other_month=other)
    st = {r["id"]: r["status"] for r in receipts}
    assert st == {"s": "LINKED", "a": "OTHER_MONTH"}, st
    a = next(r for r in receipts if r["id"] == "a")
    assert a["ref"] is None and "2026-08-14" in a["reason"] and "September 2026" in a["reason"], a["reason"]
    assert rows2[0]["status"] == "MATCHED"                                # the August receipt never competed for the September row

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print("ok", name)
