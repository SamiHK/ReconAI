# scripts/abujhd/c_report.py
"""Step C: report.json, the UI-shaped copy of matches.json that the app's Report tab renders
(src/components/petty-cash/). Nothing here is styled; coordinates stay in the matcher's 0-1000 page space.
Spec: docs/superpowers/specs/2026-10-23-petty-cash-report-ui-design.md.
"""
import argparse, sys, pathlib
from datetime import datetime
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import common
from common import load_json, save_json

ROW_KEYS = ("ref", "amount", "date", "time", "merchant", "kind", "orange", "status", "reason", "receipt_ids")
LEDGER_KEYS = ("code", "date", "text", "debit", "credit", "balance", "month", "row", "cell")
TIEOUT_KEYS = ("loads_vs_topups", "atm_vs_withdrawals", "purchases_vs_rollup")


def _cite(c):
    """A citation without its `file` key; meta.files names the sources."""
    return {k: v for k, v in c.items() if k != "file"} if c else None


def _row(r):
    c = r["citations"]
    out = {k: r.get(k) for k in ROW_KEYS}
    out["citations"] = {"statement": _cite(c["statement"]), "receipts": [_cite(x) for x in c.get("receipts") or []], "ledger": _cite(c.get("ledger"))}
    return out


def _receipt(g):
    f = g.get("fields") or {}
    totals = sorted({a["value"] for a in g.get("amounts", []) if a.get("total_candidate")})
    others = sorted({a["value"] for a in g.get("amounts", []) if not a.get("total_candidate")} - set(totals))
    return {"id": g["id"], "page": g["page"], "pages": g["pages"], "box": g["box"], "crop": g.get("crop"),
            "status": g["status"], "reason": g.get("reason"),
            "merchant": f.get("merchant") or (g.get("merchant_candidates") or [None])[0],
            "date": f.get("date") or (g.get("dates") or [None])[0],
            "total": f.get("total"), "amounts": totals + others,
            "confidence": g.get("confidence"), "notes": g.get("notes"),
            "refs": g.get("refs") or [], "review": g.get("review") or [],
            "citations": [_cite(c) for c in g["citations"]["receipt"]]}


def _ledger(lines, tieout):
    status = tieout["ledger_status"]; rollup = set(tieout["purchases_vs_rollup"]["rollup_codes"])
    out = []
    for l in lines:
        s = "ROLLUP" if l["code"] in rollup else status.get(f'{l["code"]}|{l["text"]}')
        out.append({**{k: l.get(k) for k in LEDGER_KEYS}, "status": "NO_CARD_TXN" if s == "UNEXPLAINED" else s})
    return out


def _kpis(rows, tieout):
    pr = tieout["purchases_vs_rollup"]
    purchases = [r for r in rows if r["kind"] == "purchase"]
    missing = [r for r in rows if r["status"] == "MISSING_RECEIPT"]
    return {"card_spend": pr["statement"], "purchase_count": len(purchases), "atm_count": sum(1 for r in rows if r["kind"] == "atm"),
            "purchases_amount": pr["purchases_only"],
            "evidenced_amount": round(sum(r["amount"] for r in purchases if r["status"] == "MATCHED"), 2),
            "rollup": pr["ledger"], "open_gap": round(pr["ledger"] - pr["statement"], 2),
            "missing_count": len(missing), "missing_amount": round(sum(r["amount"] for r in missing), 2)}


def build_report(matches, cfg, page_files, now=None):
    """The UI-shaped report. page_files: file names in the pages/ folder, any order."""
    month = cfg["month"]
    return {
        "meta": {"client": cfg.get("client", "ABUJHD"), "month": month,
                 "month_label": datetime.strptime(month, "%Y-%m").strftime("%B %Y"),
                 "built_at": (now or datetime.now()).isoformat(timespec="seconds"),
                 "sheet": cfg.get("sheet"), "files": cfg.get("names", {}),
                 "page_images": {"receipts": sorted(f"pages/{n}" for n in page_files if n.startswith("page-") and n.endswith(".png")),
                                 "statement": ["pages/statement-200.png"]}},
        "kpis": _kpis(matches["rows"], matches["tieout"]),
        "counts": matches["summary"],
        "rows": [_row(r) for r in matches["rows"]],
        "receipts": [_receipt(g) for g in matches["receipts"]],
        "ledger": _ledger(matches["ledger"], matches["tieout"]),
        "tieout": {k: matches["tieout"][k] for k in TIEOUT_KEYS},
    }


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--data", default="data/abujhd"); a = ap.parse_args(); common.set_data(a.data)
    report = build_report(load_json(common.DATA / "matches.json"), common.config(), [p.name for p in common.PAGES.iterdir()])
    save_json(common.DATA / "report.json", report)
    print("wrote", common.DATA / "report.json", f'({len(report["rows"])} rows, {len(report["receipts"])} receipts, {len(report["ledger"])} ledger lines)')


if __name__ == "__main__":
    main()
