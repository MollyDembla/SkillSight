"""Deterministic analytics; no inference of unsupported workforce gaps."""
from __future__ import annotations
import math
from collections import defaultdict


def linear_forecast(rows: list[dict], horizon: int = 3) -> dict:
    if not 1 <= horizon <= 12:
        raise ValueError("Forecast horizon must be between 1 and 12 months.")
    series = defaultdict(int)
    for r in rows:
        series[r["period"]] += int(r["demand_count"])
    ordered = sorted(series.items())
    if len(ordered) < 3:
        return {"status": "insufficient_history", "method": "linear_trend", "history_periods": len(ordered), "points": [], "note": "At least three monthly observations are required; no forecast is shown."}
    vals = [v for _, v in ordered]
    # Index-based least squares trend; deterministic, explicit baseline.
    n = len(vals); xm = (n - 1) / 2; ym = sum(vals) / n
    denom = sum((i-xm)**2 for i in range(n))
    slope = sum((i-xm)*(y-ym) for i,y in enumerate(vals)) / denom if denom else 0.0
    points = []
    year, month = map(int, ordered[-1][0].split("-"))
    for step in range(1, horizon+1):
        month += 1
        if month > 12: year += 1; month = 1
        points.append({"period": f"{year:04d}-{month:02d}", "value": max(0, round(ym+slope*(n-1+step)))})
    return {"status": "baseline", "method": "ordinary_least_squares_linear_trend", "history_periods": n, "slope_per_month": round(slope, 3), "points": points, "note": "Trend baseline only; no accuracy or confidence claim is made."}


def optimize_allocations(items: list[dict], budget: int, district_capacity: int) -> dict:
    if budget < 0 or district_capacity < 0:
        raise ValueError("Budget and capacity must be nonnegative.")
    clean=[]
    for x in items:
        cost=int(x["cost_per_seat"]); cap=int(x["max_seats"]); demand=int(x["demand"])
        if cost <= 0 or min(cap,demand) < 0: raise ValueError("Costs must be positive; demand and caps nonnegative.")
        clean.append({**x,"cost_per_seat":cost,"max_seats":min(cap,demand),"demand":demand})
    # Exact dynamic program, integer seats, budget and aggregate capacity respected.
    # Maximize covered demand; tie-break by lower spend.
    dp={(0,0):(0,[])}
    for ix,x in enumerate(clean):
        nxt={}
        for (spent,seats),(score,alloc) in dp.items():
            for q in range(x["max_seats"]+1):
                ns=spent+q*x["cost_per_seat"]; nq=seats+q
                if ns>budget or nq>district_capacity: continue
                key=(ns,nq); cand=(score+q,alloc+[q])
                if key not in nxt or cand[0]>nxt[key][0]: nxt[key]=cand
        dp=nxt
    if not dp: return {"status":"infeasible","reason":"No allocation satisfies the supplied constraints."}
    (spent,seats),(score,alloc)=max(dp.items(),key=lambda kv:(kv[1][0],-kv[0][0],-kv[0][1]))
    return {"status":"feasible","total_seats":seats,"total_cost":spent,"budget":budget,"capacity":district_capacity,"covered_demand_proxy":score,"allocations":[{"occupation_code":x["occupation_code"],"occupation_title":x["occupation_title"],"seats":q,"cost":q*x["cost_per_seat"],"demand_proxy":x["demand"]} for x,q in zip(clean,alloc)]}
