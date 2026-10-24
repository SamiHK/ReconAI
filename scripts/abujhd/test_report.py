# scripts/abujhd/test_report.py
import sys, pathlib
from datetime import datetime
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from c_report import build_report


def cite_s(ref):
    return {"file": "s.pdf", "page": 1, "ref": ref, "y": 1.0, "orange": False, "crop": f"crops/stmt-{ref}.png", "box": [0, 10, 1000, 15]}


def cite_r(gid, page):
    return {"file": "r.pdf", "page": page, "group_id": gid, "box": [100, 100, 500, 900], "crop": f"crops/{gid}.png"}


LEDGER_CITE = {"file": "l.xlsx", "sheet": "GL", "row": 9, "cell": "B9", "code": "ROLL", "date": "2026-09-30", "amount": 300.0, "relation": "rolled-up"}


def row(ref, amount, kind, status, receipts=(), ledger=LEDGER_CITE):
    return {"ref": ref, "amount": amount, "date": "2026-09-05", "time": "10:00:00", "balance": 1.0, "type": "Financial",
            "merchant": "SHOP", "txn_code": "0", "load_type": "Unknown", "kind": kind, "y": 1.0, "orange": True,
            "crop": "x.png", "box": [0, 0, 1, 1], "receipt_ids": [c["group_id"] for c in receipts], "status": status, "reason": "why",
            "citations": {"statement": cite_s(ref), "receipts": list(receipts), "ledger": ledger}}


def group(gid, page, status, fields=None, amounts=(), refs=(), review=()):
    return {"id": gid, "page": page, "pages": [page], "box": [100, 100, 500, 900], "segment_ids": ["x"], "text": "long healer text",
            "amounts": [{"value": v, "total_candidate": t} for v, t in amounts], "dates": ["2026-09-04"],
            "merchant_candidates": ["CAND"], "candidates": [], "linkable": True, "broken": [], "fields": fields,
            "confidence": 0.9, "notes": None, "kind": "receipt", "crop": f"crops/{gid}.png", "ids": [gid], "boxes": [],
            "ref": None, "refs": list(refs), "status": status, "review": list(review), "reason": "r",
            "citations": {"receipt": [cite_r(gid, page)], "statement": None, "ledger": None}}


MATCHES = {
    "rows": [row("r1", 100.0, "purchase", "MATCHED", receipts=[cite_r("p1-g1", 1)]),
             row("r2", 50.0, "purchase", "MISSING_RECEIPT"),
             row("a1", 200.0, "atm", "UNEXPLAINED", ledger=None)],
    "receipts": [group("p1-g1", 1, "LINKED", fields={"merchant": "Healed Shop", "date": "2026-09-05", "total": 100.0},
                       amounts=[(100.0, True), (13.04, False), (100.0, True)], refs=["r1"]),
                 group("p2-g1", 2, "REVIEW", amounts=[(20.0, True), (10.0, True), (2.61, False)], review=[["r2", 6]])],
    "ledger": [{"code": "TOP", "date": "2026-09-01", "text": "Top up", "debit": 3000.0, "credit": None, "balance": 3000.0, "month": "2026-09", "sheet": "GL", "row": 2, "cell": "B2"},
               {"code": "ROLL", "date": "2026-09-30", "text": "Roll-up", "debit": None, "credit": 300.0, "balance": 2700.0, "month": "2026-09", "sheet": "GL", "row": 9, "cell": "B9"},
               {"code": "OLD", "date": "2026-08-01", "text": "Old", "debit": 10.0, "credit": None, "balance": 10.0, "month": "2026-08", "sheet": "GL", "row": 1, "cell": "B1"},
               {"code": "X", "date": "2026-09-10", "text": "Stray credit", "debit": None, "credit": 54.37, "balance": 0.0, "month": "2026-09", "sheet": "GL", "row": 5, "cell": "B5"}],
    "tieout": {"loads_vs_topups": {"statement": 3000.0, "ledger": 3000.0, "diff": 0.0, "n_statement": 1, "n_ledger": 1},
               "atm_vs_withdrawals": {"statement": 200.0, "ledger": 0, "diff": 200.0},
               "purchases_vs_rollup": {"statement": 350.0, "purchases_only": 150.0, "ledger": 300.0, "diff": -50.0, "rollup_codes": ["ROLL"]},
               "small_credits": [], "ledger_status": {"TOP|Top up": "TIED", "X|Stray credit": "UNEXPLAINED"}},
    "orange_vs_status": {},
    "summary": {"rows": {"MATCHED": 1, "MISSING_RECEIPT": 1, "UNEXPLAINED": 1}, "receipts": {"LINKED": 1, "REVIEW": 1}},
}
CFG = {"month": "2026-09", "sheet": "GL", "names": {"receipts": "r.pdf", "statement": "s.pdf", "ledger": "l.xlsx"}}
PAGES = ["statement-200.png", "page-02.png", "page-01.png", "notes.txt"]


def build():
    return build_report(MATCHES, CFG, PAGES, now=datetime(2026, 10, 23, 22, 0, 0))


def test_meta_and_page_list():
    m = build()["meta"]
    assert m["client"] == "ABUJHD" and m["month_label"] == "September 2026" and m["built_at"] == "2026-10-23T22:00:00"
    assert m["files"]["receipts"] == "r.pdf" and m["sheet"] == "GL"
    assert m["page_images"] == {"receipts": ["pages/page-01.png", "pages/page-02.png"], "statement": ["pages/statement-200.png"]}


def test_kpis():
    assert build()["kpis"] == {"card_spend": 350.0, "purchase_count": 2, "atm_count": 1, "purchases_amount": 150.0,
                               "evidenced_amount": 100.0, "rollup": 300.0, "open_gap": -50.0, "missing_count": 1, "missing_amount": 50.0}


def test_rows_are_trimmed_and_cite_without_file():
    rows = build()["rows"]
    r = rows[0]
    assert set(r) == {"ref", "amount", "date", "time", "merchant", "kind", "orange", "status", "reason", "receipt_ids", "citations"}
    assert r["citations"]["statement"] == {"page": 1, "ref": "r1", "y": 1.0, "orange": False, "crop": "crops/stmt-r1.png", "box": [0, 10, 1000, 15]}
    assert r["citations"]["receipts"][0]["group_id"] == "p1-g1" and "file" not in r["citations"]["receipts"][0]
    assert r["citations"]["ledger"]["cell"] == "B9" and "file" not in r["citations"]["ledger"]
    assert rows[2]["citations"]["ledger"] is None and rows[2]["citations"]["receipts"] == []


def test_receipts_drop_bulk_and_fill_fields():
    linked, review = build()["receipts"]
    for key in ("text", "segment_ids", "merchant_candidates", "dates", "ids", "boxes", "broken", "linkable", "candidates"):
        assert key not in linked
    assert linked["merchant"] == "Healed Shop" and linked["date"] == "2026-09-05" and linked["total"] == 100.0
    assert linked["amounts"] == [100.0, 13.04]   # de-duplicated, total candidates first
    assert linked["refs"] == ["r1"]
    assert linked["citations"] == [{"page": 1, "group_id": "p1-g1", "box": [100, 100, 500, 900], "crop": "crops/p1-g1.png"}]
    assert review["merchant"] == "CAND" and review["date"] == "2026-09-04" and review["total"] is None
    assert review["amounts"] == [10.0, 20.0, 2.61] and review["review"] == [["r2", 6]]


def test_ledger_status_rule():
    lines = build()["ledger"]
    assert {l["code"]: l["status"] for l in lines} == {"TOP": "TIED", "ROLL": "ROLLUP", "OLD": None, "X": "NO_CARD_TXN"}
    assert set(lines[0]) == {"code", "date", "text", "debit", "credit", "balance", "month", "row", "cell", "status"}


def test_counts_and_tieout_pass_through():
    r = build()
    assert r["counts"] == MATCHES["summary"]
    assert set(r["tieout"]) == {"loads_vs_topups", "atm_vs_withdrawals", "purchases_vs_rollup"}


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print("ok", name)
