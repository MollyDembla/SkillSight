"""Unified Labour Demand Index (ULDI): fuse heterogeneous demand sources into one openings estimate.

Steps (see docs/METHODOLOGY.md for formulas):
1. Align each source: de-duplicate portal counts, shift NCS back by its publication lag, apportion
   sector-level EPFO payroll to trades.
2. Benchmark each source to annual state x sector hiring totals -> source-specific coverage rates.
3. Coverage-corrected source estimates are combined with precision weights learned from leave-one-out
   disagreement (inverse error variance x freshness), separately for each sector.
4. Trust score per cell from source count, agreement, volume and recency.
"""
from __future__ import annotations
import warnings
import numpy as np
from ..db import PERIODS, fiscal_year

SOURCES = ["portal", "ncs", "epfo"]
FRESHNESS = {"portal": 1.0, "ncs": 0.92, "epfo": 0.85}


class Frame:
    """Dense arrays of the reference universe: districts x trades x months."""

    def __init__(self, c):
        self.districts = [dict(r) for r in c.execute("SELECT * FROM districts ORDER BY state, district")]
        self.trades = [dict(r) for r in c.execute("SELECT * FROM trades ORDER BY sector, code")]
        self.d_ix = {d["lgd"]: i for i, d in enumerate(self.districts)}
        self.t_ix = {t["code"]: j for j, t in enumerate(self.trades)}
        self.p_ix = {p: m for m, p in enumerate(PERIODS)}
        self.sectors = sorted({t["sector"] for t in self.trades})
        self.sector_of = np.array([t["sector"] for t in self.trades])
        self.states = sorted({d["state"] for d in self.districts})
        self.state_of = np.array([d["state"] for d in self.districts])
        self.shape = (len(self.districts), len(self.trades), len(PERIODS))

    def trade_signal(self, c, key) -> np.ndarray:
        arr = np.full(self.shape, np.nan)
        q = "SELECT s.period, s.lgd, s.trade_code, s.value FROM signals s JOIN sources so ON so.id = s.source_id WHERE so.key = ? AND s.trade_code != ''"
        for p, lgd, code, v in c.execute(q, (key,)):
            if p in self.p_ix and lgd in self.d_ix and code in self.t_ix:
                arr[self.d_ix[lgd], self.t_ix[code], self.p_ix[p]] = v
        return arr

    def sector_signal(self, c, key) -> dict[str, np.ndarray]:
        out = {s: np.full((self.shape[0], self.shape[2]), np.nan) for s in self.sectors}
        q = "SELECT s.period, s.lgd, s.sector, s.value FROM signals s JOIN sources so ON so.id = s.source_id WHERE so.key = ? AND s.trade_code = ''"
        for p, lgd, sec, v in c.execute(q, (key,)):
            if p in self.p_ix and lgd in self.d_ix and sec in out:
                out[sec][self.d_ix[lgd], self.p_ix[p]] = v
        return out


def _interp_months(a: np.ndarray) -> np.ndarray:
    """Fill isolated interior gaps along the month axis (used only to build the coverage frame)."""
    out = a.copy()
    flat = out.reshape(-1, out.shape[-1])
    x = np.arange(flat.shape[1])
    for row in flat:
        ok = ~np.isnan(row)
        if ok.sum() >= 2 and (~ok).any():
            row[~ok] = np.interp(x[~ok], x[ok], row[ok])
    return out


def build(c, dup_factors: dict[str, float]) -> dict:
    f = Frame(c)
    nd, nt, nm = f.shape
    fy_of = np.array([fiscal_year(p) for p in PERIODS])

    # 1. alignment
    portal = f.trade_signal(c, "portal")
    dup = np.array([dup_factors.get(s, 1.25) for s in f.sector_of])
    portal = portal / dup[None, :, None]
    ncs_raw = f.trade_signal(c, "ncs")
    ncs = np.full(f.shape, np.nan)
    ncs[:, :, :-1] = ncs_raw[:, :, 1:]                      # value published in m describes m-1
    epfo_sec = f.sector_signal(c, "epfo")
    # Trade shares within sector per district from the trailing-12-month mean of portal+NCS (fallback: state shares).
    blend = np.where(np.isnan(portal), ncs, np.where(np.isnan(ncs), portal, (portal + ncs) / 2))
    with np.errstate(all="ignore"):
        blend12 = np.nanmean(np.where(np.isnan(blend[:, :, -15:-3]), 0, blend[:, :, -15:-3]), axis=2)
    epfo = np.full(f.shape, np.nan)
    for s in f.sectors:
        cols = np.where(f.sector_of == s)[0]
        local = blend12[:, cols]
        state_share = np.zeros_like(local)
        for st in f.states:
            rows_ = f.state_of == st
            tot = np.nansum(local[rows_], axis=0)
            state_share[rows_] = tot / max(1e-9, tot.sum())
        sums = np.nansum(local, axis=1, keepdims=True)
        share = np.where((sums > 5) & ~np.isnan(local), np.nan_to_num(local) / np.maximum(sums, 1e-9), state_share)
        share = share / share.sum(axis=1, keepdims=True)
        epfo[:, cols, :] = epfo_sec[s][:, None, :] * share[:, :, None]
    raw = {"portal": portal, "ncs": ncs, "epfo": epfo}

    # 2. benchmark coverage per source x state x sector x FY
    bench = {(r["state"], r["sector"], r["fy"]): r["hires"] for r in c.execute("SELECT * FROM benchmarks")}
    bench_fys = sorted({k[2] for k in bench})
    frame = _interp_months(epfo)
    frame = np.where(np.isnan(frame), np.nanmean(frame[:, :, -6:], axis=2, keepdims=True), frame)
    coverage = {}
    est = {}
    for key, a in raw.items():
        cov_arr = np.ones(f.shape)
        for st in f.states:
            ri = np.where(f.state_of == st)[0]
            for s in f.sectors:
                ci = np.where(f.sector_of == s)[0]
                covs = {}
                for fy in bench_fys:
                    mi = np.where(fy_of == fy)[0]
                    block = a[np.ix_(ri, ci, mi)]
                    fr = frame[np.ix_(ri, ci, mi)]
                    present = ~np.isnan(block)
                    frac = fr[present].sum() / max(1e-9, fr.sum())
                    covs[fy] = np.nansum(block) / max(1e-9, bench[(st, s, fy)] * frac)
                for fy in set(fy_of):
                    mi = np.where(fy_of == fy)[0]
                    use = covs.get(fy) or covs[min(bench_fys, key=lambda b: abs(int(b[:4]) - int(fy[:4])))]
                    cov_arr[np.ix_(ri, ci, mi)] = use
                coverage[(key, st, s)] = float(np.mean(list(covs.values())))
        est[key] = a / np.maximum(cov_arr, 1e-6)

    # 2b. small-area bias correction: portal/NCS coverage varies by district (urban/rural reach), so each
    #     is cross-calibrated to EPFO (complete district coverage) per district x sector, with
    #     empirical-Bayes shrinkage toward 1 for thin cells.
    small_area = {}
    for key in ("portal", "ncs"):
        for s in f.sectors:
            ci = np.where(f.sector_of == s)[0]
            a, b = est[key][:, ci, :], est["epfo"][:, ci, :]
            both = ~np.isnan(a) & ~np.isnan(b)
            num = np.where(both, a, 0).sum(axis=(1, 2))
            den = np.where(both, b, 0).sum(axis=(1, 2))
            ratio = num / np.maximum(den, 1e-9)
            k = den / (den + 200.0)
            factor = np.where(den > 0, k * ratio + (1 - k), 1.0)
            est[key][:, ci, :] /= np.maximum(factor, 0.05)[:, None, None]
            small_area[(key, s)] = float(np.std(factor))

    # 3. precision weights: structural error variance per source x sector by triple collocation
    #    (pairwise-difference identity, no ground truth needed) + per-cell Poisson sampling variance.
    counts = {"portal": raw["portal"] * dup[None, :, None], "ncs": ncs}
    sector_counts = np.zeros(f.shape)
    for s in f.sectors:
        sector_counts[:, f.sector_of == s, :] = epfo_sec[s][:, None, :]
    counts["epfo"] = sector_counts
    stack = np.stack([est[k] for k in SOURCES])           # (3, nd, nt, nm)
    samp = np.stack([1 / np.maximum(np.nan_to_num(counts[k], nan=0.0), 1.0) for k in SOURCES])
    weights = {}
    struct = np.zeros((3, nt))
    for s in f.sectors:
        ci = f.sector_of == s
        x = stack[:, :, ci, :]
        all3 = (~np.isnan(x)).all(axis=0)
        mean = np.where(all3, x.mean(axis=0), np.nan)
        rel = x / np.maximum(mean, 1e-6) - 1                  # relative deviations, comparable across cell sizes
        big = all3 & (mean > 20)
        v = {}
        for a in range(3):
            for b in range(a + 1, 3):
                v[(a, b)] = float(np.nanvar((rel[a] - rel[b])[big]))
        tc = [max(1e-3, (v[tuple(sorted((k, o1)))] + v[tuple(sorted((k, o2)))] - v[tuple(sorted((o1, o2)))]) / 2 - float(np.nanmean(samp[k][:, ci, :][big])))
              for k, (o1, o2) in zip(range(3), [(1, 2), (0, 2), (0, 1)])]
        struct[:, ci] = np.array(tc)[:, None]
        cellw = np.stack([FRESHNESS[k] / (tc[i] + samp[i][:, ci, :]) for i, k in enumerate(SOURCES)])
        cellw = np.where(np.isnan(x), 0, cellw)
        share = cellw.sum(axis=(1, 2, 3)) / max(1e-9, cellw.sum())
        weights[s] = {k: {"weight": float(share[i]), "error_var": tc[i], "coverage": float(np.mean([coverage[(k, st, s)] for st in f.states]))} for i, k in enumerate(SOURCES)}
    present = ~np.isnan(stack)
    w = np.where(present, np.array([FRESHNESS[k] for k in SOURCES])[:, None, None, None] / (struct[:, None, :, None] + samp), 0.0)
    wsum = w.sum(axis=0)
    openings = (np.nan_to_num(stack) * w).sum(axis=0) / np.maximum(wsum, 1e-9)
    n_sources = present.sum(axis=0)
    # carry forward any cell with no source at all
    for m in range(1, nm):
        hole = n_sources[:, :, m] == 0
        openings[:, :, m][hole] = openings[:, :, m - 1][hole]

    # 4. trust
    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        spread = np.nanstd(stack, axis=0) / np.maximum(np.nanmean(stack, axis=0), 1e-6)
    agree = 1 - np.clip(np.nan_to_num(spread, nan=0.5), 0, 1)
    volume = np.clip(np.log10(1 + openings) / 2.3, 0, 1)
    cell_trust = 0.45 * n_sources / 3 + 0.35 * agree + 0.2 * volume
    series_trust = (0.35 * n_sources[:, :, -12:].mean(axis=2) / 3 + 0.3 * agree[:, :, -12:].mean(axis=2)
                    + 0.2 * volume[:, :, -12:].mean(axis=2) + 0.15 * (n_sources[:, :, -3:] >= 2).mean(axis=2))

    base = np.maximum(openings[:, :, :12].mean(axis=2, keepdims=True), 0.5)
    index = 100 * openings / base
    c.execute("DELETE FROM uldi")
    c.executemany("INSERT INTO uldi VALUES(?,?,?,?,?,?,?)", [
        (PERIODS[m], f.districts[i]["lgd"], f.trades[j]["code"], round(float(openings[i, j, m]), 2), round(float(index[i, j, m]), 1), int(n_sources[i, j, m]), round(float(cell_trust[i, j, m]), 3))
        for i in range(nd) for j in range(nt) for m in range(nm)])
    c.execute("DELETE FROM source_weights")
    c.executemany("INSERT INTO source_weights VALUES(?,?,?,?,?)", [(s, k, round(v["weight"], 4), round(v["error_var"], 4), round(v["coverage"], 4)) for s, d in weights.items() for k, v in d.items()])

    validation = validate(c, f, openings, est)
    return {"frame": f, "openings": openings, "n_sources": n_sources, "trust": series_trust, "weights": weights, "validation": validation}


def validate(c, f, openings, est) -> dict:
    """Compare the fused index and each single source to simulation ground truth (synthetic data only)."""
    truth = np.full(f.shape, np.nan)
    for p, lgd, code, v in c.execute("SELECT period, lgd, trade_code, openings FROM synthetic_truth"):
        truth[f.d_ix[lgd], f.t_ix[code], f.p_ix[p]] = v
    if np.isnan(truth).all():
        return {}
    window = slice(12, 33)  # months with all sources published

    def wape(a):
        t = truth[:, :, window]
        x = a[:, :, window]
        ok = ~np.isnan(x)
        return round(float(np.abs(x[ok] - t[ok]).sum() / t[ok].sum()), 4)

    def quarterly(a):
        return a[:, :, 12:33].reshape(a.shape[0], a.shape[1], 7, 3).sum(axis=-1)

    tq, oq = quarterly(truth), quarterly(openings)
    return {"uldi_wape": wape(openings), **{f"{k}_only_wape": wape(v) for k, v in est.items()},
            "uldi_quarterly_wape": round(float(np.abs(oq - tq).sum() / tq.sum()), 4),
            "note": "District x trade error vs. synthetic ground truth (monthly unless stated); lower is better."}
