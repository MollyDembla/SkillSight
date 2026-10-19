"""End-to-end refresh: code postings -> dedup -> ULDI -> backtest -> forecast -> reconcile -> gaps -> alerts.

Runs on first start, on demand (POST /api/v1/pipeline/run) and on a schedule (SKILLSIGHT_REFRESH_HOURS).
The fitted state (model, pipeline features, gap arrays) is cached in memory for what-if simulation.
"""
from __future__ import annotations
import json, threading, time, warnings
from datetime import datetime, timezone
import numpy as np
from ..db import FUTURE, HORIZON, PERIODS, connect, rows
from ..models import forecast as F, gap as G, reconcile as R
from . import dedup, nco_coder, uldi

STATE: dict = {}
_lock = threading.Lock()


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def run(trigger: str = "manual") -> dict:
    with _lock:
        warnings.simplefilter("ignore", RuntimeWarning)
        c = connect()
        run_id = c.execute("INSERT INTO pipeline_runs(started_at, status, trigger) VALUES(?, 'running', ?)", (_now(), trigger)).lastrowid
        c.commit()
        t0 = time.time()
        steps = {}
        try:
            steps["nco_coding"] = nco_coder.code_postings(c)
            steps["dedup"] = dedup.deduplicate(c)
            u = uldi.build(c, steps["dedup"]["dup_factor_by_sector"])
            frame, Y, trust = u["frame"], u["openings"], u["trust"]
            steps["uldi"] = {"validation": u["validation"], "weights": {s: {k: round(v["weight"], 3) for k, v in d.items()} for s, d in u["weights"].items()}}
            investments = rows(c, "SELECT * FROM investments WHERE hypothetical = 0")
            static = F._static(frame)
            wape, weights, resid, preds = F.backtest(Y, frame, investments, static)
            holdout = wape.pop("holdout")
            q, buckets = F.conformal(resid, frame)
            origin = len(PERIODS) - 1
            members, uplift, ctx = F.run_members(Y, frame, investments, origin, HORIZON, static)
            ens = sum(weights[i][None, :, None] * members[m] for i, m in enumerate(F.MEMBERS))
            # aggregate-level base forecasts for reconciliation (damped Holt on aggregated series + uplift)
            st_idx = [np.where(frame.state_of == s)[0] for s in frame.states]
            Y_states = np.stack([Y[ix].sum(axis=0) for ix in st_idx])
            up_states = np.stack([uplift[ix].sum(axis=0) for ix in st_idx])
            sidx = ctx["sidx"]
            st_fc = F.damped_holt(Y_states, sidx, origin, HORIZON) + up_states
            nat_fc = F.damped_holt(Y.sum(axis=0)[None], sidx, origin, HORIZON)[0] + uplift.sum(axis=0)
            p50 = R.reconcile(ens, st_fc, nat_fc, frame.state_of, frame.states)
            widen = 1 + (1 - trust) * 0.5
            p10 = np.empty_like(p50)
            p90 = np.empty_like(p50)
            for j, s in enumerate(frame.sector_of):
                for h in range(HORIZON):
                    lo, hi = F.interval_factors(q, buckets, s, h + 1)
                    p10[:, j, h] = p50[:, j, h] * (1 - (1 - lo) * widen[:, j])
                    p90[:, j, h] = p50[:, j, h] * (1 + (hi - 1) * widen[:, j])
            p10 = np.maximum(p10, 0)
            fc = {"p10": p10, "p50": p50, "p90": p90}
            write_forecasts(c, frame, fc, uplift)
            write_backtests(c, frame, wape, weights)
            write_ledger(c, frame, preds, weights, Y)
            window = list(range(12))
            g = G.compute(c, frame, Y, fc, uplift, trust, window, investments, ctx["sidx"])
            steps["alerts"] = G.raise_alerts(c, frame, g)
            steps["forecast"] = {
                "wape_by_model": {m: round(float(np.average(v, weights=Y[:, :, -12:].sum(axis=(0, 2)))), 4) for m, v in wape.items()},
                "holdout": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in holdout.items()},
                "interval_coverage_p10_p90": F.empirical_coverage(resid, frame),
                "reconciliation_max_incoherence": R.coherence_error(p50, p50.sum(axis=0)),
                "horizon_months": HORIZON, "first_forecast_period": FUTURE[0],
            }
            statuses, counts = np.unique(g["status"], return_counts=True)
            steps["gaps"] = {str(s): int(n) for s, n in zip(statuses, counts)}
            STATE.update({"frame": frame, "Y": Y, "trust": trust, "fc": fc, "uplift": uplift, "ctx": ctx, "static": static,
                          "weights": weights, "investments": investments, "gap": g, "q": q, "buckets": buckets, "run_id": run_id,
                          "centre_capacity": {r[0]: r[1] for r in c.execute("SELECT lgd, SUM(capacity) FROM centres GROUP BY lgd")}})
            summary = {"duration_s": round(time.time() - t0, 1), **steps}
            c.execute("UPDATE pipeline_runs SET finished_at=?, status='succeeded', summary_json=? WHERE id=?", (_now(), json.dumps(summary), run_id))
            c.commit()
            return {"run_id": run_id, **summary}
        except Exception as e:
            c.rollback()
            c.execute("UPDATE pipeline_runs SET finished_at=?, status='failed', summary_json=? WHERE id=?", (_now(), json.dumps({"error": str(e)}), run_id))
            c.commit()
            raise
        finally:
            c.close()


def write_forecasts(c, frame, fc, uplift):
    out = []
    nd, nt, H = fc["p50"].shape
    for i, d in enumerate(frame.districts):
        for j, t in enumerate(frame.trades):
            for h in range(H):
                out.append((d["lgd"], t["code"], FUTURE[h], round(float(fc["p10"][i, j, h]), 2), round(float(fc["p50"][i, j, h]), 2),
                            round(float(fc["p90"][i, j, h]), 2), round(float(uplift[i, j, h]), 2)))
    # aggregates: half-widths combined assuming moderate (rho = 0.3) correlation between districts
    rho = 0.3
    groups = [("IN", np.arange(nd))] + [(f"ST:{s}", np.where(frame.state_of == s)[0]) for s in frame.states]
    for node, ix in groups:
        for j, t in enumerate(frame.trades):
            for h in range(H):
                p50 = fc["p50"][ix, j, h]
                lo = p50 - fc["p10"][ix, j, h]
                hi = fc["p90"][ix, j, h] - p50

                def agg(w):
                    return float(np.sqrt((w ** 2).sum() + rho * (w.sum() ** 2 - (w ** 2).sum())))
                s50 = float(p50.sum())
                out.append((node, t["code"], FUTURE[h], round(max(0.0, s50 - agg(lo)), 2), round(s50, 2), round(s50 + agg(hi), 2), round(float(uplift[ix, j, h].sum()), 2)))
    c.execute("DELETE FROM forecasts")
    c.executemany("INSERT INTO forecasts VALUES(?,?,?,?,?,?,?)", out)


def write_backtests(c, frame, wape, weights):
    c.execute("DELETE FROM backtests")
    out = []
    for j, t in enumerate(frame.trades):
        for m, v in wape.items():
            w = float(weights[F.MEMBERS.index(m)][j]) if m in F.MEMBERS else (1.0 if m == "ensemble" else 0.0)
            out.append((t["code"], m, round(float(v[j]), 4), round(w, 3)))
    c.executemany("INSERT INTO backtests VALUES(?,?,?,?)", out)


def write_ledger(c, frame, preds, weights, Y):
    """Forecast accountability: what the ensemble said 12 months ago vs. what the index then measured."""
    c.execute("DELETE FROM ledger")
    out = []
    for origin, H, members, actual in preds:
        ens = sum(weights[i][None, :, None] * members[m] for i, m in enumerate(F.MEMBERS))
        groups = [("IN", np.arange(len(frame.districts)))] + [(f"ST:{s}", np.where(frame.state_of == s)[0]) for s in frame.states]
        for node, ix in groups:
            for j, t in enumerate(frame.trades):
                for h in range(H):
                    out.append((node, t["code"], PERIODS[origin], PERIODS[origin + 1 + h], round(float(ens[ix, j, h].sum()), 1), round(float(actual[ix, j, h].sum()), 1)))
    c.executemany("INSERT INTO ledger VALUES(?,?,?,?,?,?)", out)


def ensure_ready():
    """Run the pipeline if it has never succeeded, or reload state if this process has none."""
    if STATE.get("frame") is not None:
        return
    with _lock:  # wait for an in-flight run to finish
        pass
    if STATE.get("frame") is None:
        run("startup")


def last_run(c) -> dict | None:
    r = c.execute("SELECT * FROM pipeline_runs WHERE status='succeeded' ORDER BY id DESC LIMIT 1").fetchone()
    if not r:
        return None
    d = dict(r)
    d["summary"] = json.loads(d.pop("summary_json"))
    return d
