"""Demand forecasting ensemble with leading investment indicators and conformal intervals.

Members (all vectorised across every district x trade series):
  * seasonal-growth   - deseasonalised level x damped year-on-year growth x pooled seasonal index
  * damped-holt       - damped-trend exponential smoothing on the deseasonalised series
  * global-gbm        - one gradient-boosted model across all series (M5-style), direct multi-horizon,
                        using lag ratios, calendar, trade/sector and the announced-investment pipeline
Statistical members receive the GBM-estimated *investment uplift* (counterfactual: pipeline frozen at origin),
so announced projects move every member. Ensemble weights = inverse rolling-origin WAPE per trade.
Prediction intervals: split-conformal on backtest residual ratios by sector x horizon bucket.
"""
from __future__ import annotations
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from .. import catalog
from ..db import PERIODS, HORIZON, month_index

MEMBERS = ["seasonal_growth", "damped_holt", "global_gbm"]
TRAIN_H = [1, 2, 3, 4, 6, 8, 10, 12, 15, 18]
BACKTEST_ORIGINS = [17, 23, 29]


def pipeline_hiring(investments: list[dict], frame, n_total: int, origin: int) -> np.ndarray:
    """Expected monthly hiring implied by projects announced on or before `origin` (no look-ahead)."""
    out = np.zeros((frame.shape[0], frame.shape[1], n_total))
    for inv in investments:
        if month_index(inv["announced"]) > origin or inv["lgd"] not in frame.d_ix:
            continue
        d = frame.d_ix[inv["lgd"]]
        b0, o0 = month_index(inv["build_start"]), month_index(inv["ops_start"])
        build_len = max(3, o0 - b0)
        for code, share in catalog.CONSTRUCTION_SHARES.items():
            j = frame.t_ix[code]
            for m in range(max(0, b0), min(n_total, b0 + build_len)):
                out[d, j, m] += inv["jobs_build"] * share / build_len
        ramp = max(1, inv["ramp_months"])
        for code, share in catalog.staffing_shares(inv["sector"]).items():
            j = frame.t_ix[code]
            for m in range(max(0, o0), n_total):
                k = m - o0
                out[d, j, m] += inv["jobs_ops"] * share * (1 / ramp if k < ramp else 0.015)
    return out


def seasonal_index(Y: np.ndarray, frame, upto: int) -> np.ndarray:
    """Pooled multiplicative month-of-year index per trade, estimated on data <= upto. Shape (nt, 12)."""
    months = np.array([int(p[5:]) for p in PERIODS[: upto + 1]]) - 1
    tot = Y[:, :, : upto + 1].sum(axis=0)                          # (nt, T)
    T = tot.shape[1]
    idx = np.ones((tot.shape[0], 12))
    if T < 24:
        return idx
    ratios = [[] for _ in range(12)]
    for t in range(6, T - 6):
        ma = 0.5 * tot[:, t - 6] / 12 + tot[:, t - 5: t + 6].sum(axis=1) / 12 + 0.5 * tot[:, t + 6] / 12
        ratios[months[t]].append(tot[:, t] / np.maximum(ma, 1e-6))
    for mo in range(12):
        if ratios[mo]:
            idx[:, mo] = np.mean(ratios[mo], axis=0)
    return idx / idx.mean(axis=1, keepdims=True)


def _month_of(m: int) -> int:
    y0, m0 = map(int, PERIODS[0].split("-"))
    return (m0 - 1 + m) % 12


def _deseason(Y, sidx, upto):
    mo = np.array([_month_of(m) for m in range(upto + 1)])
    return Y[:, :, : upto + 1] / sidx[None, :, mo]


def seasonal_growth(Y, sidx, origin, H):
    ds = _deseason(Y, sidx, origin)
    level = ds[:, :, -3:].mean(axis=2)
    if origin >= 23:
        g = ds[:, :, -12:].mean(axis=2) / np.maximum(ds[:, :, -24:-12].mean(axis=2), 1e-6) - 1
    else:
        g = (ds[:, :, -6:].mean(axis=2) / np.maximum(ds[:, :, -12:-6].mean(axis=2), 1e-6)) ** 2 - 1
    g = np.clip(g, -0.3, 0.6)
    out = np.empty(Y.shape[:2] + (H,))
    for h in range(1, H + 1):
        damp = sum(0.92 ** k for k in range(1, h + 1)) / 12
        out[:, :, h - 1] = level * (1 + g) ** damp * sidx[None, :, _month_of(origin + h)]
    return out


def damped_holt(Y, sidx, origin, H, alpha=0.35, beta=0.08, phi=0.9):
    ds = _deseason(Y, sidx, origin)
    level = ds[:, :, :3].mean(axis=2)
    trend = np.zeros_like(level)
    for t in range(3, ds.shape[2]):
        prev = level
        level = alpha * ds[:, :, t] + (1 - alpha) * (level + phi * trend)
        trend = beta * (level - prev) + (1 - beta) * phi * trend
    out = np.empty(Y.shape[:2] + (H,))
    for h in range(1, H + 1):
        damp = sum(phi ** k for k in range(1, h + 1))
        out[:, :, h - 1] = np.maximum(level + damp * trend, 0) * sidx[None, :, _month_of(origin + h)]
    return out


def _features(Y, pipe, sidx, origin, hs, static, freeze_pipeline=False):
    nd, nt = Y.shape[:2]
    ds = _deseason(Y, sidx, origin)
    level = np.maximum(ds[:, :, -3:].mean(axis=2), 0.5)
    r = [ds[:, :, -1 - k] / level for k in range(3)]
    r35 = ds[:, :, -6:-3].mean(axis=2) / level
    g6 = ds[:, :, -6:].mean(axis=2) / np.maximum(ds[:, :, -12:-6].mean(axis=2), 1e-6)
    blocks = []
    for h in hs:
        tgt = origin + h
        p_now = pipe[:, :, origin] / level
        p_t = pipe[:, :, tgt] / level
        p_t2 = pipe[:, :, min(tgt + 2, pipe.shape[2] - 1)] / level
        if freeze_pipeline:
            p_t = p_t2 = p_now
        cols = [np.full((nd, nt), h), np.full((nd, nt), _month_of(tgt)), static["trade"], static["sector"], static["urban"],
                static["asp"], np.log(level), r[0], r[1], r[2], r35, g6, np.broadcast_to(sidx[:, _month_of(tgt)], (nd, nt)),
                p_now, p_t, p_t2, p_t - p_now]
        blocks.append(np.stack([np.asarray(c, dtype=float) for c in cols], axis=-1).reshape(nd * nt, -1))
    return np.concatenate(blocks), level


def _static(frame):
    nd, nt = frame.shape[:2]
    sec_ix = {s: i for i, s in enumerate(frame.sectors)}
    return {
        "trade": np.broadcast_to(np.arange(nt)[None, :], (nd, nt)),
        "sector": np.broadcast_to(np.array([sec_ix[s] for s in frame.sector_of])[None, :], (nd, nt)),
        "urban": np.broadcast_to(np.array([d["urban"] for d in frame.districts])[:, None], (nd, nt)),
        "asp": np.broadcast_to(np.array([d["aspirational"] for d in frame.districts])[:, None], (nd, nt)),
    }


def fit_gbm(Y, pipe, sidx, upto, static):
    """Train on all origins whose targets are observed by `upto`."""
    X, y = [], []
    for origin in range(11, upto):
        hs = [h for h in TRAIN_H if origin + h <= upto]
        if not hs:
            continue
        feats, level = _features(Y, pipe, sidx, origin, hs, static)
        target = np.concatenate([(Y[:, :, origin + h] / level).ravel() for h in hs])
        X.append(feats)
        y.append(target)
    X, y = np.concatenate(X), np.concatenate(y)
    model = HistGradientBoostingRegressor(max_iter=260, learning_rate=0.06, max_leaf_nodes=31, min_samples_leaf=40,
                                          categorical_features=[2, 3], random_state=0)
    model.fit(X, np.clip(y, 0, 20))
    return model


def gbm_predict(model, Y, pipe, sidx, origin, H, static, freeze_pipeline=False):
    nd, nt = Y.shape[:2]
    hs = list(range(1, H + 1))
    X, level = _features(Y, pipe, sidx, origin, hs, static, freeze_pipeline)
    pred = np.maximum(model.predict(X), 0).reshape(len(hs), nd, nt)
    return np.moveaxis(pred, 0, -1) * level[:, :, None]


def run_members(Y, frame, investments, origin, H, static, model=None):
    n_total = len(PERIODS) + HORIZON + 3
    pipe = pipeline_hiring(investments, frame, n_total, origin)
    sidx = seasonal_index(Y, frame, origin)
    if model is None:
        model = fit_gbm(Y, pipe, sidx, origin, static)
    gbm = gbm_predict(model, Y, pipe, sidx, origin, H, static)
    gbm_cf = gbm_predict(model, Y, pipe, sidx, origin, H, static, freeze_pipeline=True)
    uplift = gbm - gbm_cf                                            # change attributable to announced projects
    members = {
        "seasonal_growth": np.maximum(seasonal_growth(Y, sidx, origin, H) + uplift, 0),
        "damped_holt": np.maximum(damped_holt(Y, sidx, origin, H) + uplift, 0),
        "global_gbm": gbm,
    }
    return members, uplift, {"model": model, "pipe": pipe, "sidx": sidx}


def linear_baseline(Y, origin, H):
    """Legacy straight-line trend (the original prototype's method) for comparison only."""
    hist = Y[:, :, max(0, origin - 23): origin + 1]
    n = hist.shape[2]
    x = np.arange(n) - (n - 1) / 2
    slope = (hist * x).sum(axis=2) / (x ** 2).sum()
    mean = hist.mean(axis=2)
    return np.maximum(np.stack([mean + slope * ((n - 1) / 2 + h) for h in range(1, H + 1)], axis=-1), 0)


def backtest(Y, frame, investments, static):
    """Rolling-origin evaluation. Returns per-trade WAPE per member, ensemble weights and residual ratios."""
    nt = Y.shape[1]
    err = {m: np.zeros(nt) for m in MEMBERS + ["linear_baseline", "ensemble"]}
    tot = np.zeros(nt)
    preds = []
    for origin in BACKTEST_ORIGINS:
        H = min(12, Y.shape[2] - 1 - origin)
        members, _, _ = run_members(Y, frame, investments, origin, H, static)
        actual = Y[:, :, origin + 1: origin + 1 + H]
        members["linear_baseline"] = linear_baseline(Y, origin, H)
        for m, p in members.items():
            err[m] += np.abs(p - actual).sum(axis=(0, 2))
        tot += actual.sum(axis=(0, 2))
        preds.append((origin, H, members, actual))
    wape = {m: err[m] / np.maximum(tot, 1e-9) for m in MEMBERS + ["linear_baseline"]}
    weights = _simplex_weights(preds, nt)
    holdout_w = _simplex_weights(preds[:-1], nt)
    resid = []
    err_ens = np.zeros(nt)
    for origin, H, members, actual in preds:
        ens = sum(weights[i][None, :, None] * members[m] for i, m in enumerate(MEMBERS))
        err_ens += np.abs(ens - actual).sum(axis=(0, 2))
        resid.append((origin, H, ens, actual))
    wape["ensemble"] = err_ens / np.maximum(tot, 1e-9)
    # Honest out-of-sample check: weights chosen on earlier origins, scored on the last origin only.
    origin, H, members, actual = preds[-1]
    ens = sum(holdout_w[i][None, :, None] * members[m] for i, m in enumerate(MEMBERS))
    denom = actual.sum()
    holdout = {"origin": PERIODS[origin], "ensemble": float(np.abs(ens - actual).sum() / denom)}
    holdout.update({m: float(np.abs(members[m] - actual).sum() / denom) for m in MEMBERS + ["linear_baseline"]})
    wape["holdout"] = holdout
    return wape, weights, resid, preds


def _simplex_weights(preds, nt, step=0.1):
    """Per-trade convex weights minimising backtest absolute error (grid over the 3-member simplex)."""
    grid = [(a / 10, b / 10, (10 - a - b) / 10) for a in range(11) for b in range(11 - a)]
    errs = np.zeros((len(grid), nt))
    for origin, H, members, actual in preds:
        for g, w in enumerate(grid):
            ens = sum(w[i] * members[m] for i, m in enumerate(MEMBERS))
            errs[g] += np.abs(ens - actual).sum(axis=(0, 2))
    best = errs.argmin(axis=0)
    return np.array([grid[b] for b in best]).T                       # (3, nt)


def conformal(resid, frame, levels=(0.1, 0.9)):
    """Quantiles of actual/forecast ratio per sector x horizon bucket (calibrated on all backtest origins)."""
    buckets = [(1, 3), (4, 6), (7, 12)]
    q = {}
    for s in frame.sectors:
        ci = frame.sector_of == s
        for lo, hi in buckets:
            ratios = []
            for origin, H, ens, actual in resid:
                sl = slice(lo - 1, min(hi, H))
                e, a = ens[:, ci, sl], actual[:, ci, sl]
                ok = e > 2
                ratios.append(a[ok] / e[ok])
            r = np.concatenate(ratios) if ratios else np.array([1.0])
            q[(s, lo)] = (float(np.quantile(r, levels[0])), float(np.quantile(r, levels[1])))
    return q, buckets


def empirical_coverage(resid, frame):
    """Calibrate on the earlier origins, test on the last: share of actuals inside P10-P90."""
    if len(resid) < 2:
        return None
    q, buckets = conformal(resid[:-1], frame)
    origin, H, ens, actual = resid[-1]
    inside = total = 0
    for j, s in enumerate(frame.sector_of):
        for h in range(H):
            lo_b = next(b for b in buckets if b[0] <= h + 1 <= b[1])[0]
            lo, hi = q[(s, lo_b)]
            e, a = ens[:, j, h], actual[:, j, h]
            ok = e > 2
            inside += ((a[ok] >= e[ok] * lo) & (a[ok] <= e[ok] * hi)).sum()
            total += ok.sum()
    return round(inside / max(1, total), 4)


def interval_factors(q, buckets, sector, h):
    b = next((b for b in buckets if b[0] <= h <= b[1]), None)
    if b is not None:
        return q[(sector, b[0])]
    lo, hi = q[(sector, buckets[-1][0])]
    widen = (h / 12) ** 0.5                                          # beyond the calibrated range: sqrt-time widening
    return 1 - (1 - lo) * widen, 1 + (hi - 1) * widen
