"""Read-side query layer shared by the REST API, exports, reports and the AI copilot tools."""
from __future__ import annotations
import json
from collections import defaultdict
from .db import CURRENT_FY, FUTURE, GAP_WINDOW, PERIODS, rows
from .models.gap import ACUTE, OVER, SHORT, SURPLUS, STATUSES

GAP_SELECT = """SELECT g.*, d.state, d.district, d.lat, d.lon, d.aspirational, t.title AS trade, t.sector, t.sector_name, t.qp_code,
                t.emerging, t.cost_per_seat, t.nsqf_level FROM gaps g JOIN districts d USING(lgd) JOIN trades t ON t.code = g.trade_code"""


def _status(gr: float) -> str:
    if gr <= ACUTE:
        return STATUSES[0]
    if gr <= SHORT:
        return STATUSES[1]
    if gr < SURPLUS:
        return STATUSES[2]
    if gr < OVER:
        return STATUSES[3]
    return STATUSES[4]


def gap_rows(c, state=None, lgd=None, sector=None, trade=None, status=None, emerging=None, sort="severity", limit=200, offset=0) -> list[dict]:
    sql, args = GAP_SELECT + " WHERE 1=1", []
    for col, val in [("d.state", state), ("g.lgd", lgd), ("t.sector", sector), ("g.trade_code", trade)]:
        if val:
            sql += f" AND {col} = ?"
            args.append(val)
    if status:
        sts = [s.strip() for s in status.split(",")]
        sql += f" AND g.status IN ({','.join('?' * len(sts))})"
        args += sts
    if emerging is not None:
        sql += " AND t.emerging = ?"
        args.append(int(emerging))
    order = {"severity": "g.severity DESC", "gap": "g.gap ASC", "surplus": "g.gap DESC", "gap_ratio": "g.gap_ratio ASC", "demand": "g.demand_p50 DESC"}.get(sort, "g.severity DESC")
    sql += f" ORDER BY {order} LIMIT ? OFFSET ?"
    args += [limit, offset]
    out = rows(c, sql, args)
    for r in out:
        for k in ("drivers_json", "quarters_json", "history_json"):
            r[k[:-5]] = json.loads(r.pop(k))
    return out


def rollup(c, by: str = "state", state=None, sector=None, trade=None) -> list[dict]:
    """Aggregate gaps: by 'state', 'district', 'trade', 'sector' or 'state_trade'."""
    keys = {"state": ["d.state"], "district": ["d.state", "d.district", "g.lgd", "d.lat", "d.lon", "d.aspirational"], "trade": ["g.trade_code", "t.title", "t.sector", "t.emerging"],
            "sector": ["t.sector", "t.sector_name"], "state_trade": ["d.state", "g.trade_code", "t.title", "t.sector"]}[by]
    sql = f"""SELECT {', '.join(keys)}, SUM(g.demand_p50) demand, SUM(g.demand_p10) demand_p10, SUM(g.demand_p90) demand_p90, SUM(g.demand_last12) demand_last12,
              SUM(g.supply) supply, SUM(g.seats) seats, SUM(MAX(g.invest_effect, 0)) invest_effect,
              SUM(CASE WHEN g.gap < 0 THEN -g.gap ELSE 0 END) shortage, SUM(CASE WHEN g.gap > 0 THEN g.gap ELSE 0 END) surplus,
              SUM(g.severity * g.demand_p50) / MAX(SUM(g.demand_p50), 1) severity, AVG(g.trust) trust,
              SUM(CASE WHEN g.status IN ('Acute shortage','Shortage') THEN 1 ELSE 0 END) shortage_cells,
              SUM(CASE WHEN g.status IN ('Saturating','Oversupplied') THEN 1 ELSE 0 END) surplus_cells, COUNT(*) cells
              FROM gaps g JOIN districts d USING(lgd) JOIN trades t ON t.code = g.trade_code WHERE 1=1"""
    args = []
    for col, val in [("d.state", state), ("t.sector", sector), ("g.trade_code", trade)]:
        if val:
            sql += f" AND {col} = ?"
            args.append(val)
    sql += f" GROUP BY {', '.join(keys)}"
    out = rows(c, sql, args)
    for r in out:
        r["gap"] = round(r["supply"] - r["demand"], 1)
        r["gap_ratio"] = round(r["gap"] / max(r["demand"], 1), 4)
        r["status"] = _status(r["gap_ratio"])
        r["severity"] = round(r["severity"], 1)
        r["trust"] = round(r["trust"], 3)
        r["growth"] = round(r["demand"] / max(r["demand_last12"], 1) - 1, 4)
    return out


def overview(c, state=None, sector=None) -> dict:
    tot = rollup(c, "state", state=state, sector=sector)
    agg = defaultdict(float)
    for r in tot:
        for k in ("demand", "supply", "shortage", "surplus", "seats", "demand_last12", "shortage_cells", "surplus_cells", "cells", "invest_effect"):
            agg[k] += r[k]
    alerts_q = "SELECT a.kind, COUNT(*) n FROM alerts a JOIN districts d USING(lgd) JOIN trades t ON t.code=a.trade_code WHERE a.active=1"
    args = []
    if state:
        alerts_q += " AND d.state=?"
        args.append(state)
    if sector:
        alerts_q += " AND t.sector=?"
        args.append(sector)
    alerts = {r["kind"]: r["n"] for r in rows(c, alerts_q + " GROUP BY a.kind", args)}
    trades = sorted(rollup(c, "trade", state=state, sector=sector), key=lambda r: r["gap_ratio"])
    hist = rows(c, f"""SELECT u.period, SUM(u.openings) v FROM uldi u JOIN districts d USING(lgd) JOIN trades t ON t.code=u.trade_code WHERE 1=1
                    {' AND d.state=?' if state else ''}{' AND t.sector=?' if sector else ''} GROUP BY u.period ORDER BY u.period""", [x for x in (state, sector) if x])
    node = f"ST:{state}" if state else "IN"
    fc = rows(c, f"""SELECT f.period, SUM(f.p10) p10, SUM(f.p50) p50, SUM(f.p90) p90 FROM forecasts f JOIN trades t ON t.code=f.trade_code WHERE f.node=?
                  {' AND t.sector=?' if sector else ''} GROUP BY f.period ORDER BY f.period""", [node] + ([sector] if sector else []))
    return {"scope": {"state": state, "sector": sector}, "data_label": "Synthetic demonstration data - not official government statistics",
            "as_of": PERIODS[-1], "gap_window": f"{GAP_WINDOW[0]} to {GAP_WINDOW[-1]}", "training_cycle": f"FY {CURRENT_FY}",
            "kpis": {"forecast_demand": round(agg["demand"]), "demand_last12": round(agg["demand_last12"]), "demand_growth": round(agg["demand"] / max(agg["demand_last12"], 1) - 1, 4),
                     "expected_supply": round(agg["supply"]), "unmet_demand": round(agg["shortage"]), "excess_supply": round(agg["surplus"]),
                     "training_seats": round(agg["seats"]), "shortage_cells": int(agg["shortage_cells"]), "surplus_cells": int(agg["surplus_cells"]), "cells": int(agg["cells"]),
                     "investment_driven_demand": round(agg["invest_effect"]), "alerts": alerts},
            "top_shortages": trades[:6], "top_surpluses": trades[::-1][:6], "trades": trades,
            "trend": [{"period": h["period"], "actual": round(h["v"])} for h in hist] + [{"period": f["period"], "p10": round(f["p10"]), "p50": round(f["p50"]), "p90": round(f["p90"])} for f in fc]}


def alerts(c, state=None, lgd=None, sector=None, kind=None, status=None, limit=200) -> list[dict]:
    sql = """SELECT a.*, d.state, d.district, t.title trade, t.sector, g.gap_ratio, g.demand_p50, g.supply, g.trust, g.drivers_json
             FROM alerts a JOIN districts d USING(lgd) JOIN trades t ON t.code=a.trade_code LEFT JOIN gaps g ON g.lgd=a.lgd AND g.trade_code=a.trade_code WHERE a.active=1"""
    args = []
    for col, val in [("d.state", state), ("a.lgd", lgd), ("t.sector", sector), ("a.kind", kind), ("a.status", status)]:
        if val:
            sql += f" AND {col}=?"
            args.append(val)
    sql += " ORDER BY CASE WHEN a.kind LIKE 'emerging%' THEN 0 ELSE 1 END, a.severity DESC, a.probability DESC LIMIT ?"
    out = rows(c, sql, args + [limit])
    for r in out:
        r["drivers"] = json.loads(r.pop("drivers_json") or "[]")
    return out


def series(c, trade: str, node: str = "IN") -> dict:
    """History (ULDI) + forecast fan + accountability ledger for a trade at national / state / district level."""
    if node == "IN":
        where, args = "", []
    elif node.startswith("ST:"):
        where, args = " AND d.state=?", [node[3:]]
    else:
        where, args = " AND u.lgd=?", [node]
    hist = rows(c, f"SELECT u.period, SUM(u.openings) v, AVG(u.trust) trust FROM uldi u JOIN districts d USING(lgd) WHERE u.trade_code=?{where} GROUP BY u.period ORDER BY u.period", [trade] + args)
    fc = rows(c, "SELECT period, p10, p50, p90, invest_effect FROM forecasts WHERE node=? AND trade_code=? ORDER BY period", (node, trade))
    ledger = rows(c, "SELECT origin, period, forecast, actual FROM ledger WHERE node=? AND trade_code=? ORDER BY origin, period", (node, trade)) if not node[0].isdigit() else []
    bt = rows(c, "SELECT model, wape, weight FROM backtests WHERE trade_code=? ORDER BY wape", (trade,))
    return {"node": node, "trade_code": trade,
            "history": [{"period": h["period"], "actual": round(h["v"], 1), "trust": round(h["trust"], 3)} for h in hist],
            "forecast": [{k: (round(v, 1) if isinstance(v, float) else v) for k, v in f.items()} for f in fc], "ledger": ledger, "backtest": bt}


def district_profile(c, lgd: str) -> dict | None:
    d = c.execute("SELECT * FROM districts WHERE lgd=?", (lgd,)).fetchone()
    if not d:
        return None
    gaps = gap_rows(c, lgd=lgd, limit=100)
    centres = rows(c, "SELECT * FROM centres WHERE lgd=?", (lgd,))
    invest = rows(c, "SELECT * FROM investments WHERE lgd=? AND hypothetical=0", (lgd,))
    out_m = rows(c, "SELECT m.dest_lgd, dd.district, dd.state, m.sector, m.share FROM migration m JOIN districts dd ON dd.lgd=m.dest_lgd WHERE m.origin_lgd=? ORDER BY m.share DESC LIMIT 12", (lgd,))
    in_m = rows(c, "SELECT m.origin_lgd, dd.district, dd.state, m.sector, m.share FROM migration m JOIN districts dd ON dd.lgd=m.origin_lgd WHERE m.dest_lgd=? ORDER BY m.share DESC LIMIT 12", (lgd,))
    tot_d = sum(g["demand_p50"] for g in gaps)
    tot_s = sum(g["supply"] for g in gaps)
    return {"district": dict(d), "gaps": gaps, "centres": centres, "investments": invest, "migration_out": out_m, "migration_in": in_m,
            "totals": {"demand": round(tot_d), "supply": round(tot_s), "gap_ratio": round((tot_s - tot_d) / max(tot_d, 1), 4), "seats": round(sum(g["seats"] for g in gaps)),
                       "trust": round(sum(g["trust"] for g in gaps) / max(1, len(gaps)), 3)}}


def mobility(c, sector=None, min_share: float = 0.02, limit: int = 250) -> list[dict]:
    sql = """SELECT m.origin_lgd, o.district origin, o.state origin_state, o.lat olat, o.lon olon, m.dest_lgd, d.district dest, d.state dest_state, d.lat dlat, d.lon dlon,
             m.sector, m.share, (SELECT SUM(g.local_certified) FROM gaps g JOIN trades t ON t.code=g.trade_code WHERE g.lgd=m.origin_lgd AND t.sector=m.sector) * m.share AS workers
             FROM migration m JOIN districts o ON o.lgd=m.origin_lgd JOIN districts d ON d.lgd=m.dest_lgd WHERE m.share >= ?"""
    args = [min_share]
    if sector:
        sql += " AND m.sector=?"
        args.append(sector)
    out = rows(c, sql + " ORDER BY workers DESC LIMIT ?", args + [limit])
    for r in out:
        r["workers"] = round(r["workers"] or 0)
    return out


def reference(c) -> dict:
    return {"states": [r["state"] for r in rows(c, "SELECT DISTINCT state FROM districts ORDER BY state")],
            "districts": rows(c, "SELECT lgd, state, district, lat, lon, aspirational FROM districts ORDER BY state, district"),
            "trades": rows(c, "SELECT * FROM trades ORDER BY sector, title"),
            "sectors": rows(c, "SELECT DISTINCT sector, sector_name FROM trades ORDER BY sector"),
            "statuses": STATUSES, "periods": {"history": [PERIODS[0], PERIODS[-1]], "forecast": [FUTURE[0], FUTURE[-1]], "gap_window": [GAP_WINDOW[0], GAP_WINDOW[-1]]}}


def sources(c) -> list[dict]:
    out = rows(c, """SELECT s.*, COUNT(sg.value) rows, MIN(sg.period) first_period, MAX(sg.period) last_period FROM sources s
                     LEFT JOIN signals sg ON sg.source_id = s.id GROUP BY s.id ORDER BY s.id""")
    extra = {"postings": "SELECT COUNT(*) FROM postings", "sidh": "SELECT COUNT(*) FROM supply",
             "official-epfo": "SELECT COUNT(*) FROM official_stats WHERE source='EPFO'", "official-plfs": "SELECT COUNT(*) FROM official_stats WHERE source='PLFS'",
             "benchmark": "SELECT COUNT(*) FROM benchmarks", "invest": "SELECT COUNT(*) FROM investments WHERE hypothetical=0"}
    weights = defaultdict(dict)
    for w in rows(c, "SELECT * FROM source_weights"):
        weights[w["source_key"]][w["sector"]] = {"weight": w["weight"], "coverage": w["coverage"], "error_var": w["error_var"]}
    for s in out:
        if s["key"] in extra:
            s["rows"] = c.execute(extra[s["key"]]).fetchone()[0]
        s["weights"] = weights.get(s["key"], {})
    return out


def official_context(c, state: str | None = None) -> dict:
    """Real published EPFO / PLFS figures next to the (synthetic, state-anchored) demand index."""
    states = [state] if state else [r["state"] for r in rows(c, "SELECT DISTINCT state FROM districts ORDER BY state")]
    epfo = rows(c, f"""SELECT period, state, value, definition, url FROM official_stats WHERE source='EPFO' AND indicator='net_payroll_latest'
                      AND state IN ({','.join('?' * len(states))}, 'All India') ORDER BY period""", states)
    plfs = rows(c, f"""SELECT period, state, indicator, value, definition, url FROM official_stats WHERE source='PLFS'
                      AND state IN ({','.join('?' * len(states))}, 'All India') ORDER BY period""", states)
    idx = rows(c, f"""SELECT u.period, d.state, SUM(u.openings) openings FROM uldi u JOIN districts d USING(lgd)
                     WHERE d.state IN ({','.join('?' * len(states))}) GROUP BY u.period, d.state ORDER BY u.period""", states)
    fy = rows(c, "SELECT period, state, value FROM official_stats WHERE source='EPFO' AND indicator='net_payroll_fy'")
    pilot = {r["state"]: r["value"] for r in fy if r["period"] == "FY2024-25" and r["state"] != "All India"}
    tot = sum(pilot.values()) or 1
    sim = {r["state"]: r["v"] for r in rows(c, """SELECT d.state, SUM(u.openings * CASE t.sector WHEN 'IT' THEN 0.85 WHEN 'EV' THEN 0.7 WHEN 'RE' THEN 0.6
                     WHEN 'HC' THEN 0.55 WHEN 'LG' THEN 0.45 ELSE 0.15 END) v FROM uldi u JOIN districts d USING(lgd) JOIN trades t ON t.code=u.trade_code GROUP BY d.state""")}
    stot = sum(sim.values()) or 1
    shares = [{"state": st, "official_epfo_share": round(pilot.get(st, 0) / tot, 4), "index_formal_share": round(sim.get(st, 0) / stot, 4)} for st in sorted(pilot)]
    return {"epfo": epfo, "plfs": plfs, "index": idx, "shares": shares,
            "note": "EPFO and PLFS values are real published figures (latest vintage; see each row's source). District x trade detail remains synthetic, "
                    "with state sizes anchored to official EPFO net-payroll shares - so the share comparison agrees by construction and is not a validation."}
