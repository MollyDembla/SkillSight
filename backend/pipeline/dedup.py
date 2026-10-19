"""Near-duplicate and ghost-posting detection for raw job postings (MinHash + LSH, pure NumPy).

Cross-posted vacancies inflate portal counts. Clusters of near-identical postings (Jaccard >= 0.6 on word
3-shingles, same district, posted within 14 days) are counted once. Listings re-posted in 3+ distinct months
by the same employer are flagged as "ghost" postings (likely never filled / evergreen ads).
"""
from __future__ import annotations
import re, zlib
from collections import defaultdict
from datetime import date
import numpy as np

N_HASH, BANDS = 64, 16
ROWS = N_HASH // BANDS
_PRIME = (1 << 61) - 1
_rng = np.random.default_rng(7)
_A = _rng.integers(1, _PRIME, N_HASH, dtype=np.int64)
_B = _rng.integers(0, _PRIME, N_HASH, dtype=np.int64)


def shingles(text: str) -> set[int]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {zlib.crc32(" ".join(words[i:i + 3]).encode()) for i in range(max(1, len(words) - 2))}


def signature(sh: set[int]) -> np.ndarray:
    x = np.fromiter(sh, dtype=np.int64)
    # (a*x + b) mod p using Python ints would be slow; uint64 wraparound is an acceptable universal hash here.
    h = (np.outer(_A.astype(np.uint64), x.astype(np.uint64)) + _B.astype(np.uint64)[:, None]) % np.uint64(_PRIME)
    return h.min(axis=1)


class _UF:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, a):
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        self.p[self.find(a)] = self.find(b)


def _day(s: str) -> date:
    return date.fromisoformat(s)


def deduplicate(c) -> dict:
    rows = c.execute("SELECT p.id, p.posted_on, p.lgd, p.employer, p.raw_title, p.description, t.sector FROM postings p LEFT JOIN trades t ON t.code = p.nco_code ORDER BY p.id").fetchall()
    n = len(rows)
    sh = [shingles(f"{r['employer']} {r['raw_title']} {r['description']}") for r in rows]
    sigs = np.stack([signature(s) for s in sh])
    uf = _UF(n)
    buckets = defaultdict(list)
    for b in range(BANDS):
        band = sigs[:, b * ROWS:(b + 1) * ROWS]
        for i in range(n):
            buckets[(b, rows[i]["lgd"], band[i].tobytes())].append(i)
    checked = set()
    for members in buckets.values():
        if len(members) < 2:
            continue
        for x in range(len(members)):
            for y in range(x + 1, len(members)):
                i, j = members[x], members[y]
                if (i, j) in checked:
                    continue
                checked.add((i, j))
                if abs((_day(rows[i]["posted_on"]) - _day(rows[j]["posted_on"])).days) > 14:
                    continue
                inter = len(sh[i] & sh[j])
                if inter / max(1, len(sh[i] | sh[j])) >= 0.6:
                    uf.union(i, j)
    cluster = [uf.find(i) for i in range(n)]
    # Ghost postings: same employer + normalised title + district appearing in >= 3 distinct months.
    months = defaultdict(set)
    for r in rows:
        months[(r["employer"], re.sub(r"[^a-z]", "", r["raw_title"].lower()), r["lgd"])].add(r["posted_on"][:7])
    ghost = [int(len(months[(r["employer"], re.sub(r"[^a-z]", "", r["raw_title"].lower()), r["lgd"])]) >= 3) for r in rows]
    c.executemany("UPDATE postings SET cluster_id=?, ghost=? WHERE id=?", [(rows[cluster[i]]["id"], ghost[i], rows[i]["id"]) for i in range(n)])
    per_sector = defaultdict(lambda: [0, set()])
    for i, r in enumerate(rows):
        s = r["sector"] or "NA"
        per_sector[s][0] += 1
        per_sector[s][1].add(cluster[i])
    factors = {s: round(v[0] / max(1, len(v[1])), 4) for s, v in per_sector.items()}
    unique = len(set(cluster))
    return {"postings": n, "unique_vacancies": unique, "duplicate_share": round(1 - unique / max(1, n), 4),
            "ghost_postings": int(sum(ghost)), "dup_factor_by_sector": factors}
