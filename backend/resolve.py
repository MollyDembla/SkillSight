"""Fuzzy resolution of free-text place / occupation names (geo harmonisation for imports and the copilot)."""
from __future__ import annotations
from functools import lru_cache
from rapidfuzz import fuzz, process
from . import catalog
from .db import connect

ALIASES = {"bangalore": "Bengaluru Urban", "bengaluru": "Bengaluru Urban", "bombay": "Mumbai", "noida": "Gautam Buddha Nagar", "greater noida": "Gautam Buddha Nagar",
           "bhubaneswar": "Khordha", "khurda": "Khordha", "allahabad": "Prayagraj", "faizabad": "Ayodhya", "gulbarga": "Kalaburagi", "mysore": "Mysuru",
           "belgaum": "Belagavi", "bellary": "Ballari", "shimoga": "Shivamogga", "tumkur": "Tumakuru", "navi mumbai": "Thane", "berhampur": "Ganjam",
           "rourkela": "Sundargarh", "keonjhar": "Kendujhar", "bolangir": "Balangir", "aurangabad mh": "Aurangabad"}
STATE_ALIASES = {"up": "Uttar Pradesh", "u.p.": "Uttar Pradesh", "uttar pradesh": "Uttar Pradesh", "karnataka": "Karnataka", "maharashtra": "Maharashtra",
                 "odisha": "Odisha", "orissa": "Odisha", "mh": "Maharashtra", "ka": "Karnataka", "कर्नाटक": "Karnataka", "महाराष्ट्र": "Maharashtra",
                 "ओडिशा": "Odisha", "उत्तर प्रदेश": "Uttar Pradesh"}


@lru_cache(maxsize=1)
def _districts() -> tuple:
    c = connect()
    out = tuple((r["lgd"], r["district"], r["state"]) for r in c.execute("SELECT lgd, district, state FROM districts"))
    c.close()
    return out


def district(name: str, state: str | None = None, cutoff: int = 82) -> dict | None:
    if not name:
        return None
    name = name.strip()
    target = ALIASES.get(name.lower(), name)
    pool = [d for d in _districts() if not state or d[2] == state]
    hit = process.extractOne(target, [d[1] for d in pool], scorer=fuzz.WRatio, score_cutoff=cutoff)
    if not hit:
        return None
    lgd, dist, st = pool[hit[2]]
    return {"lgd": lgd, "district": dist, "state": st, "score": round(hit[1], 1)}


def state(name: str | None) -> str | None:
    if not name:
        return None
    s = STATE_ALIASES.get(name.strip().lower())
    if s:
        return s
    hit = process.extractOne(name, catalog.PILOT_STATES, scorer=fuzz.WRatio, score_cutoff=80)
    return hit[0] if hit else None


def trade(text: str, cutoff: int = 70) -> dict | None:
    if not text:
        return None
    choices = {}
    for t in catalog.trades():
        choices[t["title"]] = t
        choices[t["code"]] = t
        for v in catalog.TITLE_VARIANTS[t["code"]]:
            choices[v] = t
    hit = process.extractOne(text, list(choices), scorer=fuzz.WRatio, score_cutoff=cutoff)
    return {"code": choices[hit[0]]["code"], "title": choices[hit[0]]["title"], "score": round(hit[1], 1)} if hit else None


def find_in_text(text: str) -> dict:
    """Spot states, districts and trades mentioned anywhere in a question."""
    low = text.lower()
    st = next((v for k, v in STATE_ALIASES.items() if (f" {k} " in f" {low} " if len(k) <= 3 else k in low)), None)
    dist = None
    for lgd, name, s in _districts():
        if name.lower() in low:
            dist = {"lgd": lgd, "district": name, "state": s}
            break
    if not dist:
        for alias, name in ALIASES.items():
            if alias in low:
                dist = district(name)
                break
    tr = None
    best = (0, 0.0)
    generic = {"technician", "operator", "executive", "assistant", "associate", "general", "helper", "service", "engineer", "junior", "plant"}
    for t in catalog.trades():
        for v in [t["title"]] + catalog.TITLE_VARIANTS[t["code"]]:
            words = [w for w in v.lower().replace("(", " ").replace(")", " ").replace("-", " ").split() if len(w) > 2 and w not in generic]
            hits = sum(w in low for w in words)
            score = (hits, hits / max(1, len(words)))
            if hits and score[1] >= 0.5 and score > best:
                best, tr = score, {"code": t["code"], "title": t["title"]}
    sector = next((k for k, v in catalog.SECTORS.items() if v.split()[0].lower() in low), None)
    return {"state": st, "district": dist, "trade": tr, "sector": sector}
