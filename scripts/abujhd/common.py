# scripts/abujhd/common.py
"""Shared helpers for the ABUJHD petty-cash scripts: paths, env, JSON, raw fetch, normalisers."""
import json, os, re, unicodedata
from datetime import date as _date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "abujhd"
RAW = PAGES = CROPS = CACHE = DATA  # re-bound by set_data()

DOCAI = "http://localhost:8080"


def set_data(path):
    global DATA, RAW, PAGES, CROPS, CACHE
    DATA = Path(path).resolve()
    RAW, PAGES, CROPS, CACHE = DATA / "raw", DATA / "pages", DATA / "crops", DATA / "cache"
    for d in (RAW, PAGES, CROPS, CACHE):
        d.mkdir(parents=True, exist_ok=True)


_env = None
def env(name):
    global _env
    if _env is None:
        _env = {}
        p = ROOT / ".env.local"
        if p.exists():
            for line in p.read_text().splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    k, v = line.split("=", 1)
                    _env[k.strip()] = v.strip()
    return os.environ.get(name) or _env.get(name) or None


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"), strict=False)


def save_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def config():
    """Per-client settings from DATA/config.json (git-ignored): file ids, file names, month, ledger sheet. See config.example.json."""
    return load_json(DATA / "config.json")


def ensure_raw():
    """Fetch bytes + DocAI segments for the three files into RAW if missing."""
    for name, fid in config()["files"].items():
        for suffix, path in (("content", RAW / f"{name}.bin"), ("segments", RAW / f"{name}.segments.json")):
            if path.exists():
                continue
            key = env("DOCAI_API_KEY")
            assert key, "DOCAI_API_KEY missing from .env.local"
            r = requests.get(f"{DOCAI}/v1/files/{fid}/{suffix}", headers={"x-api-key": key}, timeout=120)
            r.raise_for_status()
            path.write_bytes(r.content)


_AR = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
def ascii_digits(s):
    return s.translate(_AR)


def norm_text(s):
    s = unicodedata.normalize("NFKC", ascii_digits(s or ""))
    s = re.sub(r"^\s*#{1,6}\s*", "", s, flags=re.M)
    return re.sub(r"\s+", " ", s).strip()


_AMT = re.compile(r"(?<![\d.])(\d{1,3}(?:,\d{3})+\.\d{2}|\d+\.\d{2})(?!\d)")
def find_amounts(text):
    return [float(m.replace(",", "")) for m in _AMT.findall(ascii_digits(text or ""))]


_MONTHS = {m: i for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split(), 1)}
_DATE_PATTERNS = [
    (re.compile(r"\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b"), lambda m: (m[1], m[2], m[3])),           # yyyy-mm-dd
    (re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b"), lambda m: (m[3], m[2], m[1])),       # dd/mm/yyyy
    (re.compile(r"\b(\d)\s?(\d)\s+([A-Za-z]{3})\s+(\d{4})\b"), lambda m: (m[4], _MONTHS.get(m[3].upper(), 0), m[1] + m[2])),  # 0 1 SEP 2026
    (re.compile(r"\b(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})\b"), lambda m: (m[3], _MONTHS.get(m[2].upper(), 0), m[1])),           # 1 SEP 2026
]
def find_dates(text):
    """Unique ISO dates in order of first appearance."""
    found = []
    t = ascii_digits(text or "")
    for rx, pick in _DATE_PATTERNS:
        for m in rx.finditer(t):
            y, mo, d = pick(m)
            y, mo, d = int(y), int(mo), int(d)
            if 1 <= mo <= 12 and 1 <= d <= 31 and 2000 <= y <= 2100:
                found.append((m.start(), f"{y:04d}-{mo:02d}-{d:02d}"))
    return list(dict.fromkeys(iso for _, iso in sorted(found)))


def _days(a, b):
    try:
        return abs((_date.fromisoformat(a) - _date.fromisoformat(b)).days)
    except (ValueError, TypeError):
        return 99  # unparseable (e.g. 2026-02-31 from find_dates): never matches
